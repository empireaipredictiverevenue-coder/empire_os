#!/usr/bin/env bash
set +e
cd /srv/empire_os || exit 1

echo "=== CODING TEAM RECOVERY + RESUME ==="
echo "HEAD=$(git rev-parse --short HEAD)"

echo
echo "=== PROVE CODER BACKENDS ==="
bash scripts/retest_aider_builder.sh
RETEST_RC=$?

echo
echo "=== REQUIRE PROVEN MUTATION BACKEND ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python - <<'PY'
from pathlib import Path
from empire_os.builder_capabilities import builder_capability_ready

path = Path(
    "/srv/empire_os/runtime/execution_plane/builder_capabilities.json"
)
aider = builder_capability_ready(
    "empire_coder", "aider_mutation", path=path
)
native = builder_capability_ready(
    "empire_coder", "structured_patch_mutation", path=path
)
print({
    "aider_mutation": aider,
    "structured_patch_mutation": native,
})
raise SystemExit(0 if (aider or native) else 2)
PY
CAP_RC=$?
if [ "$CAP_RC" -ne 0 ]; then
  echo "BACKLOG_RESUME=BLOCKED_NO_PROVEN_MUTATION_BACKEND"
  exit "$CAP_RC"
fi

echo
echo "=== HERMES RECOVERY REGRESSION TESTS ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python -m pytest -q \
  tests/test_hermes_control.py \
  tests/test_hermes_worker_isolation.py \
  tests/test_predictive_coding_team_recovery_status.py \
  --tb=short
HERMES_TEST_RC=$?
echo "HERMES_TEST_RC=$HERMES_TEST_RC"
if [ "$HERMES_TEST_RC" -ne 0 ]; then
  echo "BACKLOG_RESUME=BLOCKED_HERMES_REGRESSION"
  exit "$HERMES_TEST_RC"
fi

echo
echo "=== REFRESH HERMES CONTROL STATUS ==="
git fetch origin ops/hermes-control:refs/remotes/origin/ops/hermes-control
FETCH_RC=$?
echo "HERMES_FETCH_RC=$FETCH_RC"

echo
echo "=== RESUME ONLY INCOMPLETE CANONICAL TASKS ==="
PYTHONPATH=/srv/empire_os   ./.venv/bin/python scripts/resume_predictive_coding_backlog.py
QUEUE_RC=$?
echo "QUEUE_RC=$QUEUE_RC"

echo
echo "=== REPUBLISH FAILED HERMES TASKS AS RECOVERY JOBS ==="
PYTHONPATH=/srv/empire_os \
  ./.venv/bin/python scripts/retry_failed_predictive_hermes.py
HERMES_RECOVERY_RC=$?
echo "HERMES_RECOVERY_RC=$HERMES_RECOVERY_RC"

echo
echo "=== REFRESH HERMES CONTROL AFTER RECOVERY PUBLISH ==="
git fetch origin \
  ops/hermes-control:refs/remotes/origin/ops/hermes-control
RECOVERY_FETCH_RC=$?
echo "RECOVERY_FETCH_RC=$RECOVERY_FETCH_RC"

echo
echo "=== HERMES GOVERNED BUILDER ==="
PYTHONPATH=/srv/empire_os   ./.venv/bin/python scripts/run_hermes_control_worker.py --max-jobs 3
HERMES_RC=$?
echo "HERMES_RC=$HERMES_RC"

echo
echo "=== EMPIRE CODER VERIFICATION QUEUE ==="
CODER_RC=0
for _ in 1 2 3 4; do
  PYTHONPATH=/srv/empire_os     ./.venv/bin/python scripts/empire_coder_worker.py --once
  RC=$?
  if [ "$RC" -ne 0 ]; then
    CODER_RC="$RC"
  fi
done
echo "CODER_RC=$CODER_RC"

echo
echo "=== SWARM V6 INDEPENDENT VERIFY ==="
PYTHONPATH=/srv/empire_os   ./.venv/bin/python scripts/run_swarm_v6.py --max-workers 3
SWARM_RC=$?
echo "SWARM_RC=$SWARM_RC"

echo
echo "=== REFRESH HERMES RESULT REF ==="
git fetch origin   ops/hermes-control:refs/remotes/origin/ops/hermes-control
POST_FETCH_RC=$?
echo "POST_FETCH_RC=$POST_FETCH_RC"

echo
echo "=== FINAL CODING TEAM STATUS ==="
PYTHONPATH=/srv/empire_os ./.venv/bin/python - <<'PY'
import json
from empire_os.predictive_coding_team_status import (
    build_predictive_coding_team_status,
)
print(json.dumps(
    build_predictive_coding_team_status("/srv/empire_os"),
    indent=2,
    sort_keys=True,
))
PY

echo
echo "=== DIFF ==="
git diff --check
DIFF_RC=$?
echo "DIFF_RC=$DIFF_RC"

echo
echo "=== RECOVERY RESULT ==="
echo "retest=$RETEST_RC capability=$CAP_RC hermes_tests=$HERMES_TEST_RC queue=$QUEUE_RC hermes_recovery=$HERMES_RECOVERY_RC hermes=$HERMES_RC coder=$CODER_RC swarm=$SWARM_RC diff=$DIFF_RC"
