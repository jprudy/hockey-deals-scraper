from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[2]


def _bridge(action: str, payload: Dict[str, Any]) -> None:
    tsx_bin = ROOT / "node_modules" / ".bin" / ("tsx.cmd" if __import__("os").name == "nt" else "tsx")
    if tsx_bin.exists():
        command = [
            str(tsx_bin),
            "automation/importer/pipeline_run_bridge.ts",
            "--action",
            action,
            "--payload",
            json.dumps(payload),
        ]
    else:
        command = [
            "npx",
            "tsx",
            "automation/importer/pipeline_run_bridge.ts",
            "--action",
            action,
            "--payload",
            json.dumps(payload),
        ]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"Pipeline run bridge failed ({action}): {stderr}")


def start_run(run_id: str, started_at_iso: str) -> None:
    _bridge(
        "start_run",
        {
            "runId": run_id,
            "startedAt": started_at_iso,
            "intakeType": "SCRAPED",
            "sourceStore": "thehockeyshop",
        },
    )


def update_intake_job(
    run_id: str,
    status: str,
    rows_produced: int = 0,
    rows_accepted: int = 0,
    log_path: Optional[str] = None,
    output_path: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    _bridge(
        "update_intake_job",
        {
            "runId": run_id,
            "intakeType": "SCRAPED",
            "sourceStore": "thehockeyshop",
            "status": status,
            "rowsProduced": rows_produced,
            "rowsAccepted": rows_accepted,
            "logPath": log_path,
            "outputPath": output_path,
            "errorMessage": error_message,
        },
    )


def finalize_run(
    run_id: str,
    status: str,
    ended_at_iso: str,
    rows_scraped_total: int,
    rows_imported_total: int,
    inserted_count: int,
    updated_count: int,
    locked_skipped_count: int,
    stale_expired_count: int,
    error_count: int,
    error_summary: Dict[str, Any],
) -> None:
    _bridge(
        "finalize_run",
        {
            "runId": run_id,
            "status": status,
            "endedAt": ended_at_iso,
            "rowsScrapedTotal": rows_scraped_total,
            "rowsImportedTotal": rows_imported_total,
            "insertedCount": inserted_count,
            "updatedCount": updated_count,
            "lockedSkippedCount": locked_skipped_count,
            "staleExpiredCount": stale_expired_count,
            "errorCount": error_count,
            "errorSummary": error_summary,
        },
    )
