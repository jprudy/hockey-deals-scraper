from __future__ import annotations

import json
import os
import subprocess
import sys
from statistics import median
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from automation.monitoring.notify_webhook import send_webhook_message


ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "automation" / "logs" / "alerts_state.json"


def log(message: str) -> None:
    print(f"[monitor] {message}", flush=True)


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"sent_alert_keys": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"sent_alert_keys": []}


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sent = state.get("sent_alert_keys", [])
    if not isinstance(sent, list):
        sent = []
    # keep state bounded
    state["sent_alert_keys"] = sent[-500:]
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def fetch_pipeline_health_snapshot() -> Dict[str, Any]:
    code = """
import { createPrismaClient } from "./automation/importer/prisma_client";

async function main() {
  const prisma = createPrismaClient();
  try {
    const select = {
      runId: true,
      status: true,
      rowsScrapedTotal: true,
      rowsImportedTotal: true,
      insertedCount: true,
      updatedCount: true,
      startedAt: true,
      endedAt: true,
      errorSummary: true,
      intakeJobs: {
        select: {
          intakeType: true,
          sourceStore: true,
          status: true,
          rowsProduced: true,
          rowsAccepted: true,
        },
      },
    };

    const recentRuns = await prisma.pipelineRun.findMany({
      orderBy: { startedAt: "desc" },
      take: 50,
      select,
    });

    function isValidCompletedSuccess(run) {
      if (!run || run.status !== "SUCCESS") return false;
      const s = run.errorSummary;
      if (!s || typeof s !== "object" || s.pipelineCompleted !== true) return false;
      const m = s.monitor;
      if (!m || typeof m !== "object" || Object.keys(m).length === 0) return false;
      return (
        m.rows_before_dedupe != null ||
        m.rows_after_dedupe != null ||
        m.normalized_rows != null
      );
    }

    const latest = recentRuns.find(isValidCompletedSuccess) || null;

    const recentSuccesses = latest
      ? await prisma.pipelineRun.findMany({
          where: {
            status: "SUCCESS",
            runId: { not: latest.runId },
          },
          orderBy: { startedAt: "desc" },
          take: 12,
          select,
        })
      : [];

    console.log(
      JSON.stringify({
        latest,
        recentSuccesses,
        recentRunsScanned: recentRuns.length,
      })
    );
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
""".strip()

    cmd = ["npx", "tsx", "--eval", code]
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"failed to fetch pipeline snapshot rc={completed.returncode} stderr={completed.stderr.strip()}"
        )
    output = completed.stdout.strip()
    if not output:
        raise RuntimeError("empty snapshot response")
    return json.loads(output)


def main() -> int:
    try:
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
        threshold_pct = int(os.environ.get("ALERT_ROW_DROP_THRESHOLD_PCT", "50"))
        source_threshold_pct = int(os.environ.get("ALERT_SOURCE_ROW_DROP_THRESHOLD_PCT", str(threshold_pct)))
        dedupe_anomaly_points = float(os.environ.get("ALERT_DEDUPE_PCT_ANOMALY_POINTS", "20"))
        import_activity_min_pct = int(os.environ.get("ALERT_IMPORT_ACTIVITY_MIN_PCT", "15"))
        import_activity_min_rows = int(os.environ.get("ALERT_IMPORT_ACTIVITY_MIN_ROWS", "25"))
        absolute_drop_min_rows = int(os.environ.get("ALERT_ABSOLUTE_DROP_MIN_ROWS", "100"))
        source_absolute_drop_min_rows = int(os.environ.get("ALERT_SOURCE_ABSOLUTE_DROP_MIN_ROWS", "40"))
        source_expected_floor_rows = int(os.environ.get("ALERT_SOURCE_EXPECTED_FLOOR_ROWS", "50"))
        min_baseline_runs = int(os.environ.get("ALERT_MIN_BASELINE_RUNS", "5"))

        if threshold_pct < 1 or threshold_pct > 99:
            log("warning invalid ALERT_ROW_DROP_THRESHOLD_PCT; using default 50")
            threshold_pct = 50
        if source_threshold_pct < 1 or source_threshold_pct > 99:
            log("warning invalid ALERT_SOURCE_ROW_DROP_THRESHOLD_PCT; using row drop threshold")
            source_threshold_pct = threshold_pct
        if dedupe_anomaly_points < 1:
            dedupe_anomaly_points = 20.0
        if import_activity_min_pct < 0 or import_activity_min_pct > 100:
            import_activity_min_pct = 15
        if import_activity_min_rows < 0:
            import_activity_min_rows = 25
        if absolute_drop_min_rows < 0:
            absolute_drop_min_rows = 100
        if source_absolute_drop_min_rows < 0:
            source_absolute_drop_min_rows = 40
        if source_expected_floor_rows < 0:
            source_expected_floor_rows = 50
        if min_baseline_runs < 2:
            min_baseline_runs = 5

        _ = os.environ.get("DATABASE_URL")
        snapshot = fetch_pipeline_health_snapshot()
        latest = snapshot.get("latest")
        recent_successes = snapshot.get("recentSuccesses") or []
        recent_runs_scanned = int(snapshot.get("recentRunsScanned") or 0)

        if not latest:
            log("no valid completed successful runs found")
            return 0

        run_id = str(latest.get("runId"))
        log(f"evaluating_run_id={run_id} selected_from={recent_runs_scanned} recent_runs")

        status = str(latest.get("status"))
        rows_scraped = int(latest.get("rowsScrapedTotal") or 0)
        rows_imported = int(latest.get("rowsImportedTotal") or 0)
        inserted = int(latest.get("insertedCount") or 0)
        updated = int(latest.get("updatedCount") or 0)
        intake_jobs = latest.get("intakeJobs") or []

        triggered: List[Dict[str, Any]] = []
        pipeline_completed = True

        def monitor_payload(run: Dict[str, Any]) -> Dict[str, Any]:
            summary = run.get("errorSummary")
            if not isinstance(summary, dict):
                return {}
            monitor = summary.get("monitor")
            return monitor if isinstance(monitor, dict) else {}

        def source_rows_from_run(run: Dict[str, Any]) -> Dict[str, int]:
            totals: Dict[str, int] = {}
            for job in run.get("intakeJobs") or []:
                source = str(job.get("sourceStore") or "unknown").strip().lower() or "unknown"
                accepted = int(job.get("rowsAccepted") or 0)
                produced = int(job.get("rowsProduced") or 0)
                totals[source] = totals.get(source, 0) + (accepted if accepted > 0 else produced)
            return totals

        def median_or_none(values: List[int]) -> Optional[float]:
            cleaned = [int(v) for v in values if int(v) >= 0]
            if not cleaned:
                return None
            return float(median(cleaned))

        latest_monitor = monitor_payload(latest)
        latest_rows_before = int(latest_monitor.get("rows_before_dedupe", rows_scraped) or 0)
        latest_rows_after = int(latest_monitor.get("rows_after_dedupe", rows_imported) or 0)
        latest_normalized_rows = int(latest_monitor.get("normalized_rows", rows_imported) or 0)
        latest_dedupe_pct = float(
            latest_monitor.get(
                "dedupe_pct",
                ((latest_rows_before - latest_rows_after) / latest_rows_before * 100.0) if latest_rows_before > 0 else 0.0,
            )
            or 0.0
        )
        latest_per_source_before = latest_monitor.get("per_source_before_dedupe")
        if not isinstance(latest_per_source_before, dict):
            latest_per_source_before = source_rows_from_run(latest)
        latest_per_source_after = latest_monitor.get("per_source_after_dedupe")
        if not isinstance(latest_per_source_after, dict):
            latest_per_source_after = {}

        if status != "SUCCESS":
            triggered.append(
                {
                    "rule": "run_failed",
                    "scope": "run",
                    "message": f"WARNING run_id={run_id} pipeline_status={status} pipeline_completed={pipeline_completed}",
                }
            )

        zero_scrape = rows_scraped == 0 or all(int(job.get("rowsProduced") or 0) == 0 for job in intake_jobs)
        if zero_scrape:
            triggered.append(
                {
                    "rule": "zero_row_scrape",
                    "scope": "run",
                    "message": (
                        f"WARNING run_id={run_id} zero-row scrape detected rows_scraped_total={rows_scraped} "
                        f"pipeline_completed={pipeline_completed}"
                    ),
                }
            )

        baseline_runs = [r for r in recent_successes if isinstance(r, dict)]

        def maybe_add_drop(rule: str, label: str, actual: int, baseline_values: List[int], scope: str = "run") -> None:
            expected = median_or_none(baseline_values)
            if expected is None or expected <= 0:
                return
            drop_pct = ((expected - actual) / expected) * 100.0
            abs_drop = expected - actual
            if drop_pct >= threshold_pct and abs_drop >= absolute_drop_min_rows:
                triggered.append(
                    {
                        "rule": rule,
                        "scope": scope,
                        "message": (
                            f"WARNING run_id={run_id} metric={label} actual={actual} expected~{expected:.1f} "
                            f"drop_pct={drop_pct:.1f}% abs_drop={abs_drop:.1f} "
                            f"threshold_pct={threshold_pct}% min_abs_drop={absolute_drop_min_rows} "
                            f"pipeline_completed={pipeline_completed}"
                        ),
                    }
                )

        if len(baseline_runs) >= min_baseline_runs:
            maybe_add_drop(
                rule="large_row_drop_before_dedupe",
                label="rows_before_dedupe",
                actual=latest_rows_before,
                baseline_values=[int(r.get("rowsScrapedTotal") or 0) for r in baseline_runs],
            )
            maybe_add_drop(
                rule="large_row_drop_after_dedupe",
                label="rows_after_dedupe",
                actual=latest_rows_after,
                baseline_values=[
                    int(monitor_payload(r).get("rows_after_dedupe", int(r.get("rowsImportedTotal") or 0)) or 0)
                    for r in baseline_runs
                ],
            )
            maybe_add_drop(
                rule="large_row_drop_normalized",
                label="normalized_rows",
                actual=latest_normalized_rows,
                baseline_values=[
                    int(monitor_payload(r).get("normalized_rows", int(r.get("rowsImportedTotal") or 0)) or 0)
                    for r in baseline_runs
                ],
            )

            baseline_dedupe: List[float] = []
            for run in baseline_runs:
                monitor = monitor_payload(run)
                if monitor and monitor.get("dedupe_pct") is not None:
                    baseline_dedupe.append(float(monitor.get("dedupe_pct") or 0.0))
                else:
                    before = int(run.get("rowsScrapedTotal") or 0)
                    after = int(run.get("rowsImportedTotal") or 0)
                    if before > 0:
                        baseline_dedupe.append(((before - after) / before) * 100.0)
            if baseline_dedupe:
                dedupe_expected = float(median(baseline_dedupe))
                dedupe_diff = latest_dedupe_pct - dedupe_expected
                if abs(dedupe_diff) >= dedupe_anomaly_points:
                    direction = "higher" if dedupe_diff > 0 else "lower"
                    triggered.append(
                        {
                            "rule": "dedupe_rate_anomaly",
                            "scope": "run",
                            "message": (
                                f"WARNING run_id={run_id} dedupe_pct={latest_dedupe_pct:.1f}% expected~{dedupe_expected:.1f}% "
                                f"delta={dedupe_diff:+.1f}pts ({direction}) rows_removed={max(0, latest_rows_before - latest_rows_after)} "
                                f"pipeline_completed={pipeline_completed}"
                            ),
                        }
                    )

            source_baseline: Dict[str, List[int]] = {}
            for run in baseline_runs:
                per_source = monitor_payload(run).get("per_source_before_dedupe")
                if not isinstance(per_source, dict):
                    per_source = source_rows_from_run(run)
                for source, value in per_source.items():
                    source_baseline.setdefault(str(source).strip().lower(), []).append(int(value or 0))

            expected_sources = {
                source
                for source, values in source_baseline.items()
                if len(values) >= 2 and (median_or_none(values) or 0) >= source_expected_floor_rows
            }
            seen_sources = {str(job.get("sourceStore") or "unknown").strip().lower() for job in intake_jobs}
            for missing in sorted(expected_sources - seen_sources):
                triggered.append(
                    {
                        "rule": f"missing_scraper:{missing}",
                        "scope": f"source:{missing}",
                        "message": f"WARNING run_id={run_id} missing_scraper={missing} pipeline_completed={pipeline_completed}",
                    }
                )

            for source, actual_raw in latest_per_source_before.items():
                source_name = str(source).strip().lower()
                expected = median_or_none(source_baseline.get(source_name, []))
                if expected is None or expected < source_expected_floor_rows:
                    continue
                actual = int(actual_raw or 0)
                drop_pct = ((expected - actual) / expected) * 100.0
                abs_drop = expected - actual
                if drop_pct >= source_threshold_pct and abs_drop >= source_absolute_drop_min_rows:
                    triggered.append(
                        {
                            "rule": f"source_low_rows:{source_name}",
                            "scope": f"source:{source_name}",
                            "message": (
                                f"WARNING run_id={run_id} source={source_name} actual_rows={actual} expected~{expected:.1f} "
                                f"drop_pct={drop_pct:.1f}% abs_drop={abs_drop:.1f} "
                                f"threshold_pct={source_threshold_pct}% min_abs_drop={source_absolute_drop_min_rows} "
                                f"pipeline_completed={pipeline_completed}"
                            ),
                        }
                    )
        else:
            log(
                f"baseline_skipped run_id={run_id} reason=insufficient_history "
                f"baseline_runs={len(baseline_runs)} required={min_baseline_runs}"
            )

        importer_activity = inserted + updated
        if status == "SUCCESS" and latest_normalized_rows > 0:
            activity_pct = (importer_activity / latest_normalized_rows) * 100.0
            if importer_activity <= import_activity_min_rows and activity_pct <= import_activity_min_pct:
                triggered.append(
                    {
                        "rule": "importer_low_activity",
                        "scope": "importer",
                        "message": (
                            f"WARNING run_id={run_id} importer_low_activity inserted={inserted} updated={updated} "
                            f"total_changes={importer_activity} normalized_rows={latest_normalized_rows} "
                            f"activity_pct={activity_pct:.1f}% expected_gt={import_activity_min_pct}% "
                            f"pipeline_completed={pipeline_completed}"
                        ),
                    }
                )

        log(
            "dedupe_visibility "
            f"run_id={run_id} rows_before={latest_rows_before} rows_after={latest_rows_after} "
            f"rows_removed={max(0, latest_rows_before - latest_rows_after)} dedupe_pct={latest_dedupe_pct:.1f}% "
            f"per_source_before={json.dumps(latest_per_source_before, sort_keys=True)} "
            f"per_source_after={json.dumps(latest_per_source_after, sort_keys=True)}"
        )

        if not triggered:
            log(
                f"healthy latest_run_id={run_id} status={status} "
                f"rows_before={latest_rows_before} rows_after={latest_rows_after} normalized={latest_normalized_rows}"
            )
            return 0

        state = load_state()
        sent_keys = set(state.get("sent_alert_keys", []))
        new_keys: List[str] = []

        for incident in triggered:
            key = f"{run_id}:{incident['rule']}:{incident.get('scope', 'run')}"
            if key in sent_keys:
                log(f"dedupe skip key={key}")
                continue
            new_keys.append(key)

            log(f"incident rule={incident['rule']} run_id={run_id}")
            if webhook_url:
                sent = send_webhook_message(webhook_url, f"[HockeyDeals Monitor WARNING] {incident['message']}")
                if sent:
                    log(f"alert_sent key={key}")
                else:
                    log(f"warning alert_send_failed key={key}")
            else:
                log("warning ALERT_WEBHOOK_URL is not set; alert not sent")

        if new_keys:
            state.setdefault("sent_alert_keys", [])
            state["sent_alert_keys"].extend(new_keys)
            save_state(state)

        return 0
    except Exception as exc:
        # Monitoring is warning-only and should never block surrounding automation.
        log(f"warning internal monitor crash error={exc!r}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
