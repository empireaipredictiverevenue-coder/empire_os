#!/usr/bin/env bash
set -euo pipefail

REPO=/srv/empire_os
CURRENT_BRANCH="$(git -C "$REPO" branch --show-current)"
BRANCH="${EMPIRE_HERMES_WORKER_CODE_BRANCH:-$CURRENT_BRANCH}"

case "$BRANCH" in
  feature/revenue-intelligence-v2|agent/data-cloud-wave4) ;;
  *)
    echo "unsupported Hermes worker code branch: $BRANCH" >&2
    exit 2
    ;;
esac
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

echo "=== CODER PLAN RECONCILE PRE ==="
"$REPO/.venv/bin/python" "$WORKTREE/scripts/run_coder_plan_delegation.py" \
  --repo-root "$REPO" --phase reconcile || \
  echo "coder_plan_reconcile_pre=failed_nonblocking" >&2

echo "=== CODER PLAN DELEGATE ==="
"$REPO/.venv/bin/python" "$WORKTREE/scripts/run_coder_plan_delegation.py" \
  --repo-root "$REPO" --phase delegate --max-jobs 1 || \
  echo "coder_plan_delegate=failed_nonblocking" >&2

worker_rc=0
"$REPO/.venv/bin/python" "$WORKTREE/scripts/run_hermes_control_worker.py" \
  --repo-root "$REPO" --control-branch ops/hermes-control --max-jobs 1 || \
  worker_rc=$?

echo "=== CODER PLAN RECONCILE POST ==="
"$REPO/.venv/bin/python" "$WORKTREE/scripts/run_coder_plan_delegation.py" \
  --repo-root "$REPO" --phase reconcile || \
  echo "coder_plan_reconcile_post=failed_nonblocking" >&2

exit "$worker_rc"
