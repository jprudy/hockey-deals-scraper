#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/root/hockeydeals-v2"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"

echo "[smoke] starting pipeline smoke test (--skip-import)"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[smoke] ERROR: missing python runtime at $PYTHON_BIN"
  exit 1
fi

cd "$PROJECT_ROOT"

# Safe smoke validation:
# - exercises run orchestration, scraper, and normalization paths
# - avoids importer upserts into production deals by using --skip-import
"$PYTHON_BIN" automation/run_all.py --skip-import

echo "[smoke] success: run_all.py --skip-import completed"
