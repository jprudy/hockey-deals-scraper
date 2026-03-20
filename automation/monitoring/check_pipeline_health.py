from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

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
    const latest = await prisma.pipelineRun.findFirst({
      orderBy: { startedAt: "desc" },
      select: {
        runId: true,
        status: true,
        rowsScrapedTotal: true,
        startedAt: true,
        intakeJobs: {
          select: {
            intakeType: true,
            sourceStore: true,
            status: true,
            rowsProduced: true,
            rowsAccepted: true,
          },
        },
      },
    });

    const previousSuccess = latest
      ? await prisma.pipelineRun.findFirst({
          where: {
            status: "SUCCESS",
            runId: { not: latest.runId },
          },
          orderBy: { startedAt: "desc" },
          select: {
            runId: true,
            rowsScrapedTotal: true,
            startedAt: true,
          },
        })
      : null;

    console.log(JSON.stringify({ latest, previousSuccess }));
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

        if threshold_pct < 1 or threshold_pct > 99:
            log("warning invalid ALERT_ROW_DROP_THRESHOLD_PCT; using default 50")
            threshold_pct = 50

        _ = os.environ.get("DATABASE_URL")
        snapshot = fetch_pipeline_health_snapshot()
        latest = snapshot.get("latest")
        previous_success = snapshot.get("previousSuccess")

        if not latest:
            log("no pipeline runs found; nothing to alert")
            return 0

        run_id = str(latest.get("runId"))
        status = str(latest.get("status"))
        rows_scraped = int(latest.get("rowsScrapedTotal") or 0)
        intake_jobs = latest.get("intakeJobs") or []

        triggered: List[Dict[str, Any]] = []

        if status != "SUCCESS":
            triggered.append(
                {
                    "rule": "run_failed",
                    "message": f"Pipeline run failed: run_id={run_id} status={status}",
                }
            )

        zero_scrape = rows_scraped == 0 or any(int(job.get("rowsProduced") or 0) == 0 for job in intake_jobs)
        if zero_scrape:
            triggered.append(
                {
                    "rule": "zero_row_scrape",
                    "message": f"Zero-row scrape detected: run_id={run_id} rows_scraped={rows_scraped}",
                }
            )

        if previous_success:
            prev_rows = int(previous_success.get("rowsScrapedTotal") or 0)
            if prev_rows > 0:
                drop_pct = ((prev_rows - rows_scraped) / prev_rows) * 100.0
                if drop_pct >= threshold_pct:
                    triggered.append(
                        {
                            "rule": "large_row_drop",
                            "message": (
                                f"Large row drop detected: run_id={run_id} rows_scraped={rows_scraped} "
                                f"previous_success_run_id={previous_success.get('runId')} previous_rows={prev_rows} "
                                f"drop_pct={drop_pct:.1f}% threshold_pct={threshold_pct}%"
                            ),
                        }
                    )

        if not triggered:
            log(f"healthy latest_run_id={run_id} status={status} rows_scraped={rows_scraped}")
            return 0

        state = load_state()
        sent_keys = set(state.get("sent_alert_keys", []))
        new_keys: List[str] = []

        for incident in triggered:
            key = f"{run_id}:{incident['rule']}"
            if key in sent_keys:
                log(f"dedupe skip key={key}")
                continue
            new_keys.append(key)

            log(f"incident rule={incident['rule']} run_id={run_id}")
            if webhook_url:
                sent = send_webhook_message(webhook_url, f"[HockeyDeals Monitor] {incident['message']}")
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
        log(f"fatal internal monitor crash error={exc!r}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
