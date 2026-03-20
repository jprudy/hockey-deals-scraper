#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/root/hockeydeals-v2"
PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
PIP_BIN="$PROJECT_ROOT/venv/bin/pip"
EXPECTED_BRANCH="main"

log() {
  echo "[deploy] $1"
}

fail() {
  echo "[deploy] ERROR: $1"
  exit 1
}

log "starting deploy update"

[[ -d "$PROJECT_ROOT" ]] || fail "project directory not found: $PROJECT_ROOT"
[[ -x "$PYTHON_BIN" ]] || fail "python runtime not found: $PYTHON_BIN"
[[ -x "$PIP_BIN" ]] || fail "pip runtime not found: $PIP_BIN"

cd "$PROJECT_ROOT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a git repo: $PROJECT_ROOT"

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$EXPECTED_BRANCH" ]]; then
  fail "expected branch '$EXPECTED_BRANCH' but found '$current_branch'"
fi

if [[ -n "$(git status --porcelain)" ]]; then
  fail "working tree is dirty; commit/stash/discard changes before deploy"
fi

log "pulling latest from origin/$EXPECTED_BRANCH"
git fetch origin "$EXPECTED_BRANCH"
git pull --ff-only origin "$EXPECTED_BRANCH"

if [[ -f "requirements-prod.txt" ]]; then
  log "refreshing python dependencies from requirements-prod.txt"
  "$PIP_BIN" install -r requirements-prod.txt
elif [[ -f "requirements.txt" ]]; then
  log "refreshing python dependencies from requirements.txt"
  "$PIP_BIN" install -r requirements.txt
else
  log "no requirements file found; skipping python dependency refresh"
fi

log "refreshing node dependencies"
npm install

log "generating prisma client"
npx prisma generate

log "ensuring automation/logs exists"
mkdir -p automation/logs

log "running smoke validation"
bash scripts/smoke_pipeline.sh

log "deploy update complete"
