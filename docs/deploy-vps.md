# HockeyDeals VPS Deployment Runbook

This runbook is the operational source for production deployment.

- Local development: Cursor
- Source of truth: GitHub
- Runtime: VPS (`/root/hockeydeals-v2`)
- Database: Neon
- Scheduler: cron

## One-Time VPS Setup (Summary)

1. Install system packages: `git`, `curl`, `unzip`, `build-essential`, `python3`, `python3-venv`, `python3-pip`, `nodejs`, `npm`.
2. Clone repo to `/root/hockeydeals-v2`.
3. Create Python venv at `/root/hockeydeals-v2/venv`.
4. Install Python dependencies required by the pipeline (including Playwright package).
5. Run `npm install` in `/root/hockeydeals-v2`.
6. Configure `/root/hockeydeals-v2/.env` with production Neon `DATABASE_URL`.
7. Run `npx prisma generate`.
8. Install Playwright browsers and Linux deps.
9. Ensure logs directory exists:
   - `mkdir -p /root/hockeydeals-v2/automation/logs`
10. Verify manual run:
    - `cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/run_all.py`
11. Configure cron:
    - `0 */12 * * * cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/run_all.py >> automation/logs/cron.log 2>&1`
12. Ensure scripts are executable:
    - `chmod +x /root/hockeydeals-v2/scripts/*.sh`
13. Configure monitoring env vars in `/root/hockeydeals-v2/.env`:
    - `ALERT_WEBHOOK_URL=...`
    - `ALERT_ROW_DROP_THRESHOLD_PCT=50`

## Standard Update Workflow (After Push to GitHub)

From VPS:

1. `cd /root/hockeydeals-v2`
2. `bash scripts/deploy_update.sh`
3. Review output and verify success.

That script handles:

- branch safety (`main`)
- git pull
- dependency refresh (Python when dependency files exist, Node always)
- Prisma client generation
- log dir check
- smoke validation via `scripts/smoke_pipeline.sh`

## Dependency Refresh Rules

- Python deps:
  - If `requirements.txt` exists, install from it.
  - If `requirements-prod.txt` exists, install from it.
  - If no Python dependency manifest exists, script skips Python refresh and prints a warning.
- Node deps:
  - Always run `npm install` to keep lockfile-resolved dependencies consistent on VPS.

## Prisma Generate

Always run after pulling updates:

- `npx prisma generate`

Reason: keep generated Prisma client in sync with schema and app/importer code.

## Smoke Test Command

Use the deploy smoke script:

- `bash scripts/smoke_pipeline.sh`

Current smoke behavior:

- runs `automation/run_all.py --skip-import` using VPS venv
- validates scraper + normalize + run orchestration without writing deal upserts to production tables

## Cron Verification

Confirm cron entry:

- `crontab -l`

Expected entry:

- `0 */12 * * * cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/run_all.py >> automation/logs/cron.log 2>&1`
- Recommended with health checks:
  - `0 */12 * * * cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/run_all.py >> automation/logs/cron.log 2>&1; cd /root/hockeydeals-v2 && bash scripts/check_pipeline_health.sh >> automation/logs/cron.log 2>&1`

## Log Verification

Pipeline scheduler log:

- `/root/hockeydeals-v2/automation/logs/cron.log`
- Alert dedupe state:
  - `/root/hockeydeals-v2/automation/logs/alerts_state.json`

Live tail:

- `tail -f /root/hockeydeals-v2/automation/logs/cron.log`

## Monitoring Manual Test

Run monitor script directly:

- `cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/monitoring/check_pipeline_health.py`

Per-run artifacts:

- `/root/hockeydeals-v2/automation/logs/<run_id>/`
- `/root/hockeydeals-v2/automation/output/<run_id>/`

## Rollback Commands

Quick rollback to previous commit:

1. `cd /root/hockeydeals-v2`
2. `git checkout main`
3. `git reset --hard HEAD~1`
4. `npm install`
5. `npx prisma generate`
6. `mkdir -p automation/logs`
7. `bash scripts/smoke_pipeline.sh`

If rollback is validated, continue running with existing cron entry.
