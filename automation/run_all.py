from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from automation.pipeline.csv_writer import write_csv
from automation.pipeline.manifest import init_manifest, write_json
from automation.pipeline.run_history import finalize_run, start_run, update_intake_job
from automation.pipeline.schema import IMPORT_SOURCE, SOURCE_STORE, validate_and_normalize_row


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


def run_scraper(run_dir: Path, log_dir: Path, run_id: str) -> Dict[str, str]:
    scraper_log_path = log_dir / "scraper_thehockeyshop.log"
    raw_csv_path = run_dir / "csv" / "raw_thehockeyshop.csv"

    env = os.environ.copy()
    env["RUN_ID"] = run_id
    env["OUTPUT_CSV_PATH"] = str(raw_csv_path)

    command_override = env.get("THS_SCRAPER_COMMAND")
    if command_override:
        command = shlex.split(command_override, posix=(os.name != "nt"))
    else:
        command = [sys.executable, "automation/scrapers/thehockeyshop/scrape.py"]

    with scraper_log_path.open("w", encoding="utf-8") as log_handle:
        result = subprocess.run(
            command,
            cwd=ROOT.parent,
            shell=False,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            check=False,
        )

    return {
        "status": "success" if result.returncode == 0 else "failed",
        "return_code": result.returncode,
        "log_file": str(scraper_log_path),
        "raw_csv_path": str(raw_csv_path),
    }


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        # subtract header
        return max(sum(1 for _ in reader) - 1, 0)


def normalize_csv(raw_csv_path: Path, run_id: str, output_path: Path) -> Dict[str, int]:
    rows: List[Dict[str, str]] = []
    errors = 0
    with raw_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            # Phase 5A contract defaults for THS intake.
            raw["import_source"] = raw.get("import_source") or IMPORT_SOURCE
            raw["source_store"] = raw.get("source_store") or SOURCE_STORE
            validated = validate_and_normalize_row(raw, run_id=run_id)
            if validated.ok:
                rows.append(validated.row)
            else:
                errors += 1
    count = write_csv(output_path, rows)
    return {"normalized_rows": count, "validation_errors": errors}


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

    start_run_ok = safe_run_history_call("start_run", start_run, run_id=run_id, started_at_iso=started_at)
    if start_run_ok:
        log_event("pipeline_run record created")
    else:
        log_event("warning pipeline_run record not created")

    scraper = run_scraper(run_dir=run_dir, log_dir=log_dir, run_id=run_id)
    log_event(f"scraper completed status={scraper['status']} return_code={scraper['return_code']}")
    manifest["intake_jobs"][f"{IMPORT_SOURCE}:{SOURCE_STORE}"] = scraper

    if scraper["status"] != "success":
        raw_rows = count_csv_rows(Path(str(scraper["raw_csv_path"])))
        safe_run_history_call(
            "update_intake_job_failed",
            update_intake_job,
            run_id=run_id,
            status="FAILED",
            rows_produced=raw_rows,
            rows_accepted=0,
            log_path=str(scraper["log_file"]),
            output_path=str(scraper["raw_csv_path"]),
            error_message="scraper_failed",
        )
        manifest["status"] = "failed"
        manifest["errors"].append("thehockeyshop_scraper_failed")
        errors.extend(manifest["errors"])
        manifest["ended_at"] = utc_now().replace(microsecond=0).isoformat()
        write_json(manifest_path, manifest)
        safe_run_history_call(
            "finalize_run_failed",
            finalize_run,
            run_id=run_id,
            status="FAILED",
            ended_at_iso=manifest["ended_at"],
            rows_scraped_total=raw_rows,
            rows_imported_total=0,
            inserted_count=0,
            updated_count=0,
            locked_skipped_count=0,
            stale_expired_count=0,
            error_count=len(errors),
            error_summary={"errors": errors},
        )
        log_event(f"end status=failed rows_read={raw_rows} inserted=0 updated=0 errors={len(errors)}")
        return 1

    raw_csv = Path(str(scraper["raw_csv_path"]))
    raw_rows = count_csv_rows(raw_csv)
    normalized_csv = run_dir / "normalized" / "deals_scraped_thehockeyshop.csv"
    normalized_csv.parent.mkdir(parents=True, exist_ok=True)
    normalized_stats = normalize_csv(raw_csv_path=raw_csv, run_id=run_id, output_path=normalized_csv)
    log_event(
        "normalize completed "
        f"raw_rows={raw_rows} normalized_rows={int(normalized_stats.get('normalized_rows', 0))} "
        f"validation_errors={int(normalized_stats.get('validation_errors', 0))}"
    )
    manifest["intake_jobs"][f"{IMPORT_SOURCE}:{SOURCE_STORE}"].update(normalized_stats)
    safe_run_history_call(
        "update_intake_job_success",
        update_intake_job,
        run_id=run_id,
        status="SUCCESS",
        rows_produced=raw_rows,
        rows_accepted=int(normalized_stats.get("normalized_rows", 0)),
        log_path=str(scraper["log_file"]),
        output_path=str(normalized_csv),
    )
    manifest["artifacts"]["normalized_csv"] = str(normalized_csv)

    if args.skip_import:
        manifest["status"] = "success"
        manifest["importer"] = {"status": "skipped"}
        manifest["ended_at"] = utc_now().replace(microsecond=0).isoformat()
        write_json(manifest_path, manifest)
        safe_run_history_call(
            "finalize_run_success_skip_import",
            finalize_run,
            run_id=run_id,
            status="SUCCESS",
            ended_at_iso=manifest["ended_at"],
            rows_scraped_total=raw_rows,
            rows_imported_total=int(normalized_stats.get("normalized_rows", 0)),
            inserted_count=0,
            updated_count=0,
            locked_skipped_count=0,
            stale_expired_count=0,
            error_count=0,
            error_summary={},
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
    manifest["ended_at"] = utc_now().replace(microsecond=0).isoformat()
    write_json(manifest_path, manifest)

    importer_summary = importer.get("summary", {}) if isinstance(importer.get("summary"), dict) else {}
    safe_run_history_call(
        "finalize_run_success_or_failed",
        finalize_run,
        run_id=run_id,
        status="SUCCESS" if manifest["status"] == "success" else "FAILED",
        ended_at_iso=manifest["ended_at"],
        rows_scraped_total=raw_rows,
        rows_imported_total=int(importer_summary.get("rows_read", normalized_stats.get("normalized_rows", 0))),
        inserted_count=int(importer_summary.get("inserted", 0)),
        updated_count=int(importer_summary.get("updated_unlocked", 0)),
        locked_skipped_count=int(importer_summary.get("locked_seen_only", 0)),
        stale_expired_count=int(importer_summary.get("inactivated", 0)),
        error_count=int(importer_summary.get("errors", 0)) + len(errors),
        error_summary={"errors": errors},
    )
    log_event(
        "end "
        f"status={manifest['status']} "
        f"rows_read={int(importer_summary.get('rows_read', normalized_stats.get('normalized_rows', 0)))} "
        f"inserted={int(importer_summary.get('inserted', 0))} "
        f"updated={int(importer_summary.get('updated_unlocked', 0))} "
        f"errors={int(importer_summary.get('errors', 0)) + len(errors)}"
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
