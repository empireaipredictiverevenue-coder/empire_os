#!/usr/bin/env bash
set -euo pipefail

cd /srv/empire_os
ENV_FILE=/etc/empire_recall.env

echo "=== RECALL SHADOW ACTIVATION PREFLIGHT ==="
echo "activation_performed=false"

PUBLIC_GATEWAY_READY=false
WEBHOOK_UNIT_READY=false
WORKER_UNIT_READY=false
TUNNEL_ROUTE_READY=false

if /srv/empire_os/.venv/bin/python - <<'PY' >/dev/null 2>&1
from empire_os.public_gateway import app

ready = any(
    getattr(route, "path", None) == "/v1/providers/recall/realtime"
    and "POST" in (getattr(route, "methods", set()) or set())
    for route in app.routes
)
raise SystemExit(0 if ready else 1)
PY
then
  PUBLIC_GATEWAY_READY=true
fi

if [[ -f deploy/systemd/empire-recall-webhook.service ]] &&
   systemd-analyze verify deploy/systemd/empire-recall-webhook.service >/dev/null 2>&1; then
  WEBHOOK_UNIT_READY=true
fi

if [[ -f deploy/systemd/empire-recall-shadow-worker.service ]] &&
   systemd-analyze verify deploy/systemd/empire-recall-shadow-worker.service >/dev/null 2>&1; then
  WORKER_UNIT_READY=true
fi

HTTP_CODE="$(
  curl -sS -o /dev/null -w '%{http_code}' --max-time 5     https://empire-ai.co.uk/ || true
)"
if [[ -n "${HTTP_CODE}" && "${HTTP_CODE}" != "000" ]]; then
  TUNNEL_ROUTE_READY=true
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "BLOCKED: ${ENV_FILE} missing"
  exit 3
fi

set -a
# shellcheck disable=SC1090
. "${ENV_FILE}"
set +a

export PUBLIC_GATEWAY_READY WEBHOOK_UNIT_READY WORKER_UNIT_READY TUNNEL_ROUTE_READY

/srv/empire_os/.venv/bin/python - <<'PY'
import os
from empire_os.recall_shadow_readiness import assess_recall_shadow_readiness

def flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() == "true"

result = assess_recall_shadow_readiness(
    config=os.environ,
    public_gateway_route_ready=flag("PUBLIC_GATEWAY_READY"),
    webhook_unit_ready=flag("WEBHOOK_UNIT_READY"),
    worker_unit_ready=flag("WORKER_UNIT_READY"),
    tunnel_route_ready=flag("TUNNEL_ROUTE_READY"),
)
print("ready_for_activation=" + str(result.ready_for_activation).lower())
print("region=" + str(result.region))
print("public_gateway_route_ready=" + str(result.public_gateway_route_ready).lower())
print("webhook_unit_ready=" + str(result.webhook_unit_ready).lower())
print("worker_unit_ready=" + str(result.worker_unit_ready).lower())
print("tunnel_route_ready=" + str(result.tunnel_route_ready).lower())
print("secrets_printed=false")
if not result.ready_for_activation:
    print("blockers=" + ",".join(result.blockers))
    raise SystemExit(4)
PY

echo "=== FOCUSED VERIFY ==="
/srv/empire_os/.venv/bin/python -m pytest -q   tests/test_recall_shadow_readiness.py   tests/test_digital_avatar_runtime_read.py   tests/test_recall_webhook_verification.py   tests/test_recall_webhook_api.py   tests/test_recall_webhook_service.py   tests/test_recall_shadow_worker_service.py   tests/test_digital_avatar_api.py   tests/test_public_gateway.py

/srv/empire_os/.venv/bin/python -m py_compile   empire_os/recall_shadow_readiness.py   empire_os/digital_avatar_runtime_read.py   empire_os/recall_webhook_service.py   empire_os/recall_shadow_worker_service.py   empire_os/public_gateway.py

git diff --check

echo "preflight_complete=true"
echo "activation_performed=false"
echo "NEXT_GATE=explicit founder-approved service activation and signed-event live smoke"
