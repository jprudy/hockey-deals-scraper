#!/usr/bin/env bash
set -uo pipefail

PROJECT_ROOT="/root/hockeydeals-v2"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"

echo "[monitor] starting pipeline health check"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[monitor] WARNING: missing python runtime at $PYTHON_BIN"
  exit 0
fi

cd "$PROJECT_ROOT"
"$PYTHON_BIN" automation/monitoring/check_pipeline_health.py || echo "[monitor] WARNING: health check script returned non-zero"

echo "[monitor] health check completed"
