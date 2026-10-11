#!/usr/bin/env bash
# Exact founder-approved loopback pilot service activation. No public ingress.
# Root-only apply. Never creates a user, invitation, password or database role.
set -euo pipefail
umask 077

cd /srv/empire_os
expected_unit="deploy/systemd/empire-revenue-crm-pilot.service"
source_env="/var/lib/empire-crm-first-party/pilot-staged.env"
installed_env="/etc/empire/crm-pilot.env"
installed_unit="/etc/systemd/system/empire-revenue-crm-pilot.service"
service="empire-revenue-crm-pilot.service"
unit_backup_dir="/var/backups/empiredb/crm-founder-loopback-pilot-20261011"

if [[ "${1:-}" != "--preflight" && "${1:-}" != "--apply" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_FLAGS"
  exit 3
fi
if [[ "$EUID" -ne 0 ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_ROOT_REQUIRED"
  exit 3
fi
if [[ "${1:-}" == "--apply" && "${2:-}" != "--approved-founder-loopback-only" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_EXACT_APPROVAL_REQUIRED"
  exit 3
fi
if [[ "${1:-}" == "--preflight" && "$#" -ne 1 ]] ||
   [[ "${1:-}" == "--apply" && "$#" -ne 2 ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_EXTRA_ARGUMENTS"
  exit 3
fi

# Do not turn this into a generic systemd installer.
if [[ -e "$installed_env" || -L "$installed_env" || -e "$installed_unit" || -L "$installed_unit" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_UNIT_OR_ENV_ALREADY_PRESENT"
  exit 2
fi
if systemctl -q is-active "$service"; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_ALREADY_ACTIVE"
  exit 2
fi
if ss -H -lnt '( sport = :8783 )' | grep -q .; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_8783_OCCUPIED"
  exit 2
fi
if [[ ! -f "$expected_unit" || ! -f "$source_env" ]] ||
   [[ -L "$expected_unit" || -L "$source_env" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_EXPECTED_SOURCE_MISSING"
  exit 2
fi
if ! grep -Fq -- '--host 127.0.0.1 --port 8783 --no-proxy-headers' "$expected_unit" ||
   grep -Fq -- '--host 0.0.0.0' "$expected_unit"; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_NON_LOOPBACK_UNIT"
  exit 2
fi
if [[ "$(stat -c '%a %U' "$source_env")" != "600 ubuntu" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_PRIVATE_ENV_PERMISSION"
  exit 2
fi

# Verify reviewed, committed exact unit and operator (ignore unrelated dirty files).
if [[ -n "$(git -c safe.directory=/srv/empire_os status --porcelain -- "$expected_unit" scripts/deploy_founder_crm_loopback_service.sh)" ]] ||
   [[ "$(git -c safe.directory=/srv/empire_os hash-object "$expected_unit")" != "$(git -c safe.directory=/srv/empire_os rev-parse "HEAD:$expected_unit")" ]] ||
   [[ "$(git -c safe.directory=/srv/empire_os hash-object scripts/deploy_founder_crm_loopback_service.sh)" != "$(git -c safe.directory=/srv/empire_os rev-parse HEAD:scripts/deploy_founder_crm_loopback_service.sh)" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_UNREVIEWED_SOURCE"
  exit 2
fi

if ! runuser -u ubuntu -- /srv/empire_os/.venv/bin/python     scripts/stage_founder_crm_pilot_private.py --verify; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_PRIVATE_RUNTIME_OR_DB_PROOF"
  exit 2
fi
if systemd-analyze verify "$expected_unit" >/dev/null 2>&1; then
  echo "CRM_LOOPBACK_UNIT_SYSTEMD_VERIFY=PASS"
else
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_INVALID_UNIT"
  exit 2
fi

if [[ "$1" == "--preflight" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=PREFLIGHT_READY_NO_CHANGES"
  exit 0
fi

# No changes to existing services, mail configuration, shared Hub or HBA.
# This activation is START-ONLY; do not enable across reboot yet.
if [[ -e "$unit_backup_dir" ]]; then
  echo "CRM_LOOPBACK_DEPLOY=BLOCKED_PRIOR_ATTEMPT_RECONCILE"
  exit 2
fi
install -d -o root -g root -m 0700 "$unit_backup_dir"
install -o root -g root -m 0600 "$source_env" "$installed_env"
install -o root -g root -m 0644 "$expected_unit" "$installed_unit"
systemctl daemon-reload
if ! systemctl start "$service"; then
  echo "CRM_LOOPBACK_DEPLOY=SERVICE_START_FAILED_MANUAL_RECONCILIATION_REQUIRED"
  exit 4
fi

# Bounded startup readback, never print token, credentials or customer rows.
health_status=""
for _ in 1 2 3 4 5 6 7 8; do
  health_status="$(curl --noproxy '*' -sS --max-time 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8783/health 2>/dev/null || true)"
  [[ "$health_status" == "200" ]] && break
  sleep 0.4
done
reader_status="$(curl --noproxy '*' -sS --max-time 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8783/v1/revenue-crm/prospects 2>/dev/null || true)"
docs_status="$(curl --noproxy '*' -sS --max-time 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:8783/openapi.json 2>/dev/null || true)"
socket_rows="$(ss -H -lnt '( sport = :8783 )')"
if [[ "$health_status" != "200" || "$reader_status" != "401" || "$docs_status" != "404" ]] ||
   [[ "$(printf '%s\n' "$socket_rows" | grep -c '127.0.0.1:8783')" != "1" ]] ||
   [[ "$(printf '%s\n' "$socket_rows" | grep -c .)" != "1" ]] ||
   ! systemctl -q is-active "$service"; then
  systemctl stop "$service" || true
  echo "CRM_LOOPBACK_DEPLOY=FAILED_PROOF_SERVICE_STOPPED_RECONCILE"
  exit 4
fi
echo "CRM_LOOPBACK_PRIVATE_CONFIG=INSTALLED_ROOT_ONLY"
echo "CRM_LOOPBACK_SERVICE=ACTIVE"
echo "CRM_LOOPBACK_BOUND=127.0.0.1:8783_ONLY"
echo "CRM_LOOPBACK_HEALTH=200"
echo "CRM_LOOPBACK_UNAUTHENTICATED_CRM=401"
echo "CRM_LOOPBACK_API_DOCUMENTATION=404"
echo "CRM_LOOPBACK_PUBLIC_INGRESS_CREATED=NO"
echo "CRM_LOOPBACK_OUTBOUND_SENT=NO"
echo "CRM_LOOPBACK_AUTO_ENABLE_ON_REBOOT=NO"
echo "CRM_LOOPBACK_DEPLOY=APPROVED_PRIVATE_SERVICE_VERIFIED"
