#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/root/hockeydeals-v2"
EXPECTED_BRANCH="main"

log() {
  echo "[rollback] $1"
}

fail() {
  echo "[rollback] ERROR: $1"
  exit 1
}

log "starting rollback to previous commit"

[[ -d "$PROJECT_ROOT" ]] || fail "project directory not found: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a git repo: $PROJECT_ROOT"

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$EXPECTED_BRANCH" ]]; then
  fail "expected branch '$EXPECTED_BRANCH' but found '$current_branch'"
fi

if [[ -n "$(git status --porcelain)" ]]; then
  fail "working tree is dirty; cannot rollback safely"
fi

git reset --hard HEAD~1

npm install
npx prisma generate
mkdir -p automation/logs

log "rollback complete"
log "next steps:"
log "1) bash scripts/smoke_pipeline.sh"
log "2) tail -n 80 automation/logs/cron.log"
log "3) verify /admin/pipeline in production UI"
