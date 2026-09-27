#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
BRANCH=feature/revenue-intelligence-v2
REMOTE=origin
WORKTREE="$REPO/runtime/hermes_control/worker_code"

cd "$REPO"

echo "=== HERMES RESIDENT CODE SYNC ==="
git fetch "$REMOTE" "$BRANCH"

# The runtime worker code is disposable. Never mutate the production checkout.
git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
rm -rf "$WORKTREE"
git worktree prune --expire now

git worktree add --detach "$WORKTREE" "$REMOTE/$BRANCH" >/dev/null

WORKER_SHA="$(git -C "$WORKTREE" rev-parse --short HEAD)"
echo "worker_code_sha=$WORKER_SHA"

export PYTHONPATH="$WORKTREE"

exec "$REPO/.venv/bin/python"   "$WORKTREE/scripts/run_hermes_control_worker.py"   --repo-root "$REPO"   --control-branch ops/hermes-control   --max-jobs 1
