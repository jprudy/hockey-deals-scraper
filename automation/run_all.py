from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from automation.pipeline.csv_writer import write_csv
from automation.pipeline.dedupe import deduplicate_rows
from automation.pipeline.manifest import init_manifest, write_json
from automation.pipeline.run_history import finalize_run, start_run, update_intake_job
from automation.pipeline.schema import IMPORT_SOURCE, validate_and_normalize_row
from automation.scrapers.base import REQUIRED_SCRAPER_FIELDS, ScraperDefinition
from automation.scrapers.sourceforsports.adapter import run as run_sourceforsports
from automation.scrapers.sportexcellence.adapter import run as run_sportexcellence
from automation.scrapers.thehockeyshop.adapter import run as run_thehockeyshop


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
LOG_ROOT = ROOT / "logs"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_id_from_now() -> str:
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HockeyDeals Phase 5 MVP pipeline.")
    parser.add_argument("--run-id", default=None, help="Optional run id override")
    parser.add_argument("--skip-import", action="store_true", help="Only run scrape + CSV stage")
    return parser.parse_args()


def normalize_rows(rows: List[Dict[str, str]], run_id: str, output_path: Path) -> Dict[str, int]:
    normalized_rows: List[Dict[str, str]] = []
    errors = 0
    for raw in rows:
        raw["import_source"] = raw.get("import_source") or IMPORT_SOURCE
        validated = validate_and_normalize_row(raw, run_id=run_id)
        if validated.ok:
            normalized_rows.append(validated.row)
        else:
            errors += 1
    count = write_csv(output_path, normalized_rows)
    return {"normalized_rows": count, "validation_errors": errors}


def count_rows_by_source(rows: List[Dict[str, str]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        source = str(row.get("source_store") or row.get("source") or "unknown").strip().lower() or "unknown"
        counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def build_monitor_metrics(
    rows_before_dedupe: int,
    rows_after_dedupe: int,
    normalized_rows: int,
    source_before: Dict[str, int],
    source_after: Dict[str, int],
) -> Dict[str, Any]:
    rows_removed = max(0, rows_before_dedupe - rows_after_dedupe)
    dedupe_pct = round((rows_removed / rows_before_dedupe) * 100.0, 2) if rows_before_dedupe > 0 else 0.0
    return {
        "rows_before_dedupe": rows_before_dedupe,
        "rows_after_dedupe": rows_after_dedupe,
        "rows_removed_by_dedupe": rows_removed,
        "dedupe_pct": dedupe_pct,
        "normalized_rows": normalized_rows,
        "per_source_before_dedupe": source_before,
        "per_source_after_dedupe": source_after,
    }


def build_run_diagnostics(
    scraper_results: List[Dict[str, Any]],
    monitor_metrics: Dict[str, Any],
    importer_summary: Dict[str, Any],
    warning_flags: List[str],
    pipeline_completed: bool,
) -> Dict[str, Any]:
    return {
        "pipeline_completed": pipeline_completed,
        "scrapers": scraper_results,
        "dedupe": {
            "rows_before": int(monitor_metrics.get("rows_before_dedupe", 0)),
            "rows_after": int(monitor_metrics.get("rows_after_dedupe", 0)),
            "rows_removed": int(monitor_metrics.get("rows_removed_by_dedupe", 0)),
            "dedupe_pct": float(monitor_metrics.get("dedupe_pct", 0.0)),
        },
        "per_source_before_dedupe": monitor_metrics.get("per_source_before_dedupe", {}),
        "per_source_after_dedupe": monitor_metrics.get("per_source_after_dedupe", {}),
        "importer_activity": {
            "rows_read": int(importer_summary.get("rows_read", 0)),
            "inserted": int(importer_summary.get("inserted", 0)),
            "updated": int(importer_summary.get("updated_unlocked", 0)),
            "errors": int(importer_summary.get("errors", 0)),
        },
        "warning_flags": warning_flags,
    }


SCRAPERS: List[ScraperDefinition] = [
    ScraperDefinition(name="thehockeyshop", run=run_thehockeyshop),
    ScraperDefinition(name="sourceforsports", run=run_sourceforsports),
    ScraperDefinition(name="sportexcellence", run=run_sportexcellence),
]


def sanitize_scraper_rows(rows: List[Dict[str, str]], scraper_name: str) -> Tuple[List[Dict[str, str]], int]:
    valid: List[Dict[str, str]] = []
    invalid_count = 0
    required_non_empty = {"product_name", "price", "url", "source"}
    for row in rows:
        has_all_keys = all(field in row for field in REQUIRED_SCRAPER_FIELDS)
        has_required_values = all(str(row.get(field, "")).strip() for field in required_non_empty)
        if has_all_keys and has_required_values:
            valid.append(row)
        else:
            invalid_count += 1
    if invalid_count > 0:
        log_event(f"warning scraper={scraper_name} dropped_invalid_rows={invalid_count}")
    return valid, invalid_count


def run_scraper_with_retry(scraper: ScraperDefinition, run_id: str, run_dir: Path, log_dir: Path) -> Tuple[List[Dict[str, str]], Dict[str, object]]:
    attempts = 0
    max_attempts = 2  # one retry max
    last_meta: Dict[str, object] = {}
    while attempts < max_attempts:
        attempts += 1
        started = time.perf_counter()
        rows, meta = scraper.run(run_id, run_dir, log_dir)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        meta["duration_ms"] = elapsed_ms
        meta["attempt"] = attempts
        last_meta = meta
        if str(meta.get("status")) == "success":
            cleaned_rows, invalid_rows = sanitize_scraper_rows(rows, scraper.name)
            meta["invalid_rows"] = invalid_rows
            meta["rows_scraped"] = len(cleaned_rows)
            return cleaned_rows, meta
        log_event(
            f"warning scraper={scraper.name} attempt={attempts} status=failed "
            f"return_code={meta.get('return_code')} duration_ms={elapsed_ms}"
        )
    return [], last_meta


def run_importer(normalized_csv: Path, run_id: str, log_dir: Path) -> Dict[str, object]:
    importer_log = log_dir / "importer.log"
    importer_summary = log_dir / "summary.json"
    command = [
        sys.executable,
        "automation/importer/import_to_db.py",
        "--csv",
        str(normalized_csv),
        "--run-id",
        run_id,
        "--summary",
        str(importer_summary),
    ]

    with importer_log.open("w", encoding="utf-8") as log_handle:
        completed = subprocess.run(
            command,
            cwd=ROOT.parent,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
        )

    payload: Dict[str, object] = {
        "status": "success" if completed.returncode == 0 else "failed",
        "return_code": completed.returncode,
        "log_file": str(importer_log),
        "summary_file": str(importer_summary),
    }
    if importer_summary.exists():
        payload["summary"] = json.loads(importer_summary.read_text(encoding="utf-8"))
    return payload


def log_event(message: str) -> None:
    timestamp = utc_now().replace(microsecond=0).isoformat()
    print(f"[run_all] {timestamp} {message}", flush=True)


def safe_run_history_call(context: str, fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
        return True
    except Exception as exc:
        # Run-history persistence should never take down the data pipeline run.
        log_event(f"warning run_history_{context}_failed error={exc!r}")
        return False


def main() -> int:
    args = parse_args()
    run_id = args.run_id or run_id_from_now()
    started_at = utc_now().replace(microsecond=0).isoformat()
    log_event(f"start run_id={run_id} skip_import={args.skip_import}")

    run_dir = OUTPUT_ROOT / run_id
    log_dir = LOG_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "csv").mkdir(parents=True, exist_ok=True)
    (run_dir / "normalized").mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest").mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    manifest = init_manifest(run_id=run_id, started_at=started_at)
    manifest_path = run_dir / "manifest" / "run_manifest.json"
    errors: List[str] = []

    start_run_ok = safe_run_history_call(
        "start_run",
        start_run,
        run_id=run_id,
        started_at_iso=started_at,
        scrapers_total=len(SCRAPERS),
    )
    if start_run_ok:
        log_event("pipeline_run record created")
    else:
        log_event("warning pipeline_run record not created")

    all_rows: List[Dict[str, str]] = []
    scraper_successes = 0
    scraper_failures = 0
    warning_flags: List[str] = []
    scraper_diagnostics: List[Dict[str, Any]] = []
    for scraper in SCRAPERS:
        rows, meta = run_scraper_with_retry(scraper=scraper, run_id=run_id, run_dir=run_dir, log_dir=log_dir)
        scraper_status = str(meta.get("status", "failed"))
        source_store = str(meta.get("source", scraper.name))
        log_event(
            f"scraper={scraper.name} status={scraper_status} rows={len(rows)} "
            f"duration_ms={int(meta.get('duration_ms', 0))} attempts={int(meta.get('attempt', 1))}"
        )
        if int(meta.get("rows_filtered", 0)) > 0:
            log_event(f"warning scraper={scraper.name} rows_filtered={int(meta.get('rows_filtered', 0))}")
            warning_flags.append(f"{scraper.name}_rows_filtered")
        if scraper_status == "success" and len(rows) == 0:
            log_event(f"warning scraper={scraper.name} returned_zero_rows_after_cleaning")
            warning_flags.append(f"{scraper.name}_zero_rows")
        manifest["intake_jobs"][f"{IMPORT_SOURCE}:{source_store}"] = meta
        scraper_diagnostics.append(
            {
                "name": scraper.name,
                "source": source_store,
                "status": scraper_status,
                "rows": len(rows),
                "attempts": int(meta.get("attempt", 1)),
                "duration_ms": int(meta.get("duration_ms", 0)),
                "rows_filtered": int(meta.get("rows_filtered", 0)),
                "invalid_rows": int(meta.get("invalid_rows", 0)),
            }
        )
        if scraper_status == "success":
            scraper_successes += 1
            all_rows.extend(rows)
        else:
            scraper_failures += 1
            errors.append(f"{scraper.name}_scraper_failed")
            warning_flags.append(f"{scraper.name}_failed")

        safe_run_history_call(
            "update_intake_job",
            update_intake_job,
            run_id=run_id,
            status="SUCCESS" if scraper_status == "success" else "FAILED",
            rows_produced=int(meta.get("rows_scraped", 0)),
            rows_accepted=int(meta.get("rows_scraped", 0)) if scraper_status == "success" else 0,
            log_path=str(meta.get("log_file", "")),
            output_path=str(meta.get("raw_csv_path", "")),
            error_message=None if scraper_status == "success" else "scraper_failed",
            source_store=source_store,
        )

    total_rows_before_dedupe = len(all_rows)
    per_source_before_dedupe = count_rows_by_source(all_rows)
    deduped_rows = deduplicate_rows(all_rows)
    total_rows_after_dedupe = len(deduped_rows)
    per_source_after_dedupe = count_rows_by_source(deduped_rows)
    log_event(
        f"dedupe completed rows_before={total_rows_before_dedupe} rows_after={total_rows_after_dedupe}"
    )

    if not deduped_rows:
        log_event("warning all scrapers produced zero accepted rows")
        warning_flags.append("all_scrapers_zero_rows")

    normalized_csv = run_dir / "normalized" / "deals_scraped_all_sources.csv"
    normalized_csv.parent.mkdir(parents=True, exist_ok=True)
    normalized_stats = normalize_rows(rows=deduped_rows, run_id=run_id, output_path=normalized_csv)
    monitor_metrics = build_monitor_metrics(
        rows_before_dedupe=total_rows_before_dedupe,
        rows_after_dedupe=total_rows_after_dedupe,
        normalized_rows=int(normalized_stats.get("normalized_rows", 0)),
        source_before=per_source_before_dedupe,
        source_after=per_source_after_dedupe,
    )
    log_event(
        "normalize completed "
        f"rows_before_dedupe={total_rows_before_dedupe} rows_after_dedupe={total_rows_after_dedupe} "
        f"normalized_rows={int(normalized_stats.get('normalized_rows', 0))} "
        f"validation_errors={int(normalized_stats.get('validation_errors', 0))}"
    )
    manifest["artifacts"]["normalized_csv"] = str(normalized_csv)
    manifest["metrics"] = {"monitor": monitor_metrics}
    log_event(
        "final_summary_scrapers "
        + " ".join(
            [
                f"{entry['name']}[status={entry['status']},rows={entry['rows']},attempts={entry['attempts']},duration_ms={entry['duration_ms']}]"
                for entry in scraper_diagnostics
            ]
        )
    )
    log_event(
        "final_summary_dedupe "
        f"rows_before={int(monitor_metrics.get('rows_before_dedupe', 0))} "
        f"rows_after={int(monitor_metrics.get('rows_after_dedupe', 0))} "
        f"rows_removed={int(monitor_metrics.get('rows_removed_by_dedupe', 0))} "
        f"dedupe_pct={float(monitor_metrics.get('dedupe_pct', 0.0)):.2f}% "
        f"per_source_before={json.dumps(monitor_metrics.get('per_source_before_dedupe', {}), sort_keys=True)} "
        f"per_source_after={json.dumps(monitor_metrics.get('per_source_after_dedupe', {}), sort_keys=True)}"
    )

    if args.skip_import:
        manifest["status"] = "success"
        manifest["importer"] = {"status": "skipped"}
        manifest["diagnostics"] = build_run_diagnostics(
            scraper_results=scraper_diagnostics,
            monitor_metrics=monitor_metrics,
            importer_summary={},
            warning_flags=warning_flags,
            pipeline_completed=True,
        )
        manifest["ended_at"] = utc_now().replace(microsecond=0).isoformat()
        write_json(manifest_path, manifest)
        safe_run_history_call(
            "finalize_run_success_skip_import",
            finalize_run,
            run_id=run_id,
            status="SUCCESS",
            ended_at_iso=manifest["ended_at"],
            rows_scraped_total=total_rows_before_dedupe,
            rows_imported_total=int(normalized_stats.get("normalized_rows", 0)),
            inserted_count=0,
            updated_count=0,
            locked_skipped_count=0,
            stale_expired_count=0,
            error_count=0,
            error_summary={
                "errors": [],
                "monitor": monitor_metrics,
                "warningFlags": warning_flags,
                "pipelineCompleted": True,
            },
            scrapers_succeeded=scraper_successes,
            scrapers_failed=scraper_failures,
        )
        log_event(
            "end status=success(import_skipped) "
            f"rows_read={int(normalized_stats.get('normalized_rows', 0))} inserted=0 updated=0 errors=0"
        )
        return 0

    importer = run_importer(normalized_csv=normalized_csv, run_id=run_id, log_dir=log_dir)
    manifest["importer"] = importer
    log_event(f"importer completed status={importer['status']} return_code={importer['return_code']}")
    manifest["status"] = "success" if importer["status"] == "success" else "failed"
    if importer["status"] != "success":
        errors.append("importer_failed")
        warning_flags.append("importer_failed")
    importer_summary = importer.get("summary", {}) if isinstance(importer.get("summary"), dict) else {}
    manifest["ended_at"] = utc_now().replace(microsecond=0).isoformat()
    manifest["diagnostics"] = build_run_diagnostics(
        scraper_results=scraper_diagnostics,
        monitor_metrics=monitor_metrics,
        importer_summary=importer_summary,
        warning_flags=warning_flags,
        pipeline_completed=True,
    )
    write_json(manifest_path, manifest)
    safe_run_history_call(
        "finalize_run_success_or_failed",
        finalize_run,
        run_id=run_id,
        status=(
            "SUCCESS"
            if manifest["status"] == "success" and scraper_failures == 0
            else "PARTIAL_SUCCESS"
            if manifest["status"] == "success" and scraper_failures > 0
            else "FAILED"
        ),
        ended_at_iso=manifest["ended_at"],
        rows_scraped_total=total_rows_before_dedupe,
        rows_imported_total=int(importer_summary.get("rows_read", normalized_stats.get("normalized_rows", 0))),
        inserted_count=int(importer_summary.get("inserted", 0)),
        updated_count=int(importer_summary.get("updated_unlocked", 0)),
        locked_skipped_count=int(importer_summary.get("locked_seen_only", 0)),
        stale_expired_count=int(importer_summary.get("inactivated", 0)),
        error_count=int(importer_summary.get("errors", 0)) + len(errors),
        error_summary={
            "errors": errors,
            "monitor": monitor_metrics,
            "warningFlags": warning_flags,
            "pipelineCompleted": True,
            "diagnostics": manifest.get("diagnostics", {}),
        },
        scrapers_succeeded=scraper_successes,
        scrapers_failed=scraper_failures,
    )
    log_event(
        "end "
        f"status={manifest['status']} "
        f"rows_read={int(importer_summary.get('rows_read', normalized_stats.get('normalized_rows', 0)))} "
        f"inserted={int(importer_summary.get('inserted', 0))} "
        f"updated={int(importer_summary.get('updated_unlocked', 0))} "
        f"errors={int(importer_summary.get('errors', 0)) + len(errors)}"
    )
    log_event(
        "final_summary_importer "
        f"rows_read={int(importer_summary.get('rows_read', 0))} "
        f"inserted={int(importer_summary.get('inserted', 0))} "
        f"updated={int(importer_summary.get('updated_unlocked', 0))} "
        f"errors={int(importer_summary.get('errors', 0))} "
        f"warning_flags={json.dumps(warning_flags)}"
    )

    return 0 if manifest["status"] == "success" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        timestamp = utc_now().replace(microsecond=0).isoformat()
        print(f"[run_all] {timestamp} fatal_error={exc!r}", file=sys.stderr, flush=True)
        traceback.print_exc()
        sys.exit(1)
