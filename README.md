# HockeyDeals.ca (hockeydeals-v2)

HockeyDeals is a Canadian hockey deal aggregation platform.

Current production model:

- Cursor = local development only
- GitHub = source of truth
- VPS = only runtime environment
- Neon = production database
- cron = automation scheduler

## Local Development (Cursor)

Use local machine for coding and validation only.

```bash
npm install
npm run dev
```

Python automation is developed locally but production execution is VPS-only.

## Production Runtime (VPS)

Project path on VPS:

- `/root/hockeydeals-v2`

Pipeline entrypoint:

- `/root/hockeydeals-v2/automation/run_all.py`

Python runtime:

- `/root/hockeydeals-v2/venv/bin/python`

## Deploy / Update Workflow

After pushing code to GitHub `main`, deploy from VPS:

```bash
cd /root/hockeydeals-v2
chmod +x /root/hockeydeals-v2/scripts/*.sh
bash scripts/deploy_update.sh
```

The deploy script:

- validates branch and clean working tree
- pulls latest `main`
- refreshes dependencies
- runs `npx prisma generate`
- ensures `automation/logs` exists
- runs a safe smoke test

Full runbook:

- `docs/deploy-vps.md`

## Cron Schedule

Expected cron entry:

```cron
0 */12 * * * cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/run_all.py >> automation/logs/cron.log 2>&1
```

## Logs and Verification

Main scheduler log:

- `/root/hockeydeals-v2/automation/logs/cron.log`

Per-run logs/artifacts:

- `/root/hockeydeals-v2/automation/logs/<run_id>/`
- `/root/hockeydeals-v2/automation/output/<run_id>/`

Quick checks:

```bash
tail -f /root/hockeydeals-v2/automation/logs/cron.log
crontab -l
```

## Monitoring

Minimal webhook-first monitoring is available for pipeline health checks.

Checks:

- failed latest run
- zero-row scrape
- large row drop vs previous successful run

Required env vars on VPS:

- `ALERT_WEBHOOK_URL` (Discord webhook URL)
- `ALERT_ROW_DROP_THRESHOLD_PCT` (optional, default `50`)

Manual health-check command:

```bash
cd /root/hockeydeals-v2 && /root/hockeydeals-v2/venv/bin/python automation/monitoring/check_pipeline_health.py
```
