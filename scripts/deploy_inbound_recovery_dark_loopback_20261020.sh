#!/usr/bin/env bash
# Dark staging ONLY: customer OAuth disabled; no public ingress.
set -euo pipefail
umask 077
root=/home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
unit_source="$root/deploy/systemd/empire-inbound-recovery-staging.service"
unit_dest=/etc/systemd/system/empire-inbound-recovery-staging.service
service=empire-inbound-recovery-staging.service

if [[ $# -ne 1 && $# -ne 2 ]]; then
    echo "DARK_STAGING=BLOCKED_ARGUMENTS"
    exit 3
fi
mode="$1"
if [[ "$mode" != "--preflight" && "$mode" != "--apply" ]]; then
    echo "DARK_STAGING=BLOCKED_MODE"
    exit 3
fi
if [[ "$EUID" -ne 0 ]] || [[ "$mode" == "--preflight" && $# -ne 1 ]] ||
   [[ "$mode" == "--apply" && ( $# -ne 2 || "$2" != "--founder-approved-dark-loopback-only" ) ]]; then
    echo "DARK_STAGING=BLOCKED_PRIVILEGE_OR_EXACT_APPROVAL"
    exit 3
fi
cd "$root"
if [[ ! -f "$unit_source" || -L "$unit_source" ]]; then
    echo "DARK_STAGING=BLOCKED_MISSING_UNIT"
    exit 2
fi
for file in deploy/systemd/empire-inbound-recovery-staging.service \
  scripts/deploy_inbound_recovery_dark_loopback_20261020.sh \
  empire_os/inbound_calendar_connection_service.py \
  empire_os/inbound_calendar_connection_api.py; do
    if [[ -n "$(git status --porcelain -- "$file")" ]] ||
       [[ "$(git hash-object "$file")" != "$(git rev-parse "HEAD:$file")" ]]; then
        echo "DARK_STAGING=BLOCKED_UNCOMMITTED_SOURCE"
        exit 2
    fi
done
if [[ -e "$unit_dest" || -L "$unit_dest" ]] || systemctl -q is-active "$service"; then
    echo "DARK_STAGING=BLOCKED_ALREADY_INSTALLED"
    exit 2
fi
if ss -H -lnt '( sport = :8794 )' | grep -q .; then
    echo "DARK_STAGING=BLOCKED_PORT_USED"
    exit 2
fi
if ! grep -Fq -- '--host 127.0.0.1 --port 8794 --no-proxy-headers --no-access-log' "$unit_source" ||
   grep -Fq -- '--host 0.0.0.0' "$unit_source" ||
   ! systemd-analyze verify "$unit_source" >/dev/null 2>&1; then
    echo "DARK_STAGING=BLOCKED_UNIT_NOT_SAFE"
    exit 2
fi
if [[ "$mode" == "--preflight" ]]; then
    echo "DARK_STAGING=PREFLIGHT_PASS_NOT_INSTALLED"
    exit 0
fi
install -o root -g root -m 0644 "$unit_source" "$unit_dest"
systemctl daemon-reload
cleanup_failure() {
    systemctl stop "$service" >/dev/null 2>&1 || true
    rm -f "$unit_dest"
    systemctl daemon-reload
    echo "DARK_STAGING=FAILED_SERVICE_STOPPED"
}
if ! systemctl start "$service"; then
    cleanup_failure
    exit 4
fi
health=""
for i in 1 2 3 4 5 6 7 8 9 10; do
    health="$(curl --noproxy '*' -sS --max-time 2 -o /dev/null \
        -w '%{http_code}' 'http://127.0.0.1:8794/health' 2>/dev/null || true)"
    [[ "$health" == "200" ]] && break
    sleep 0.3
done
get_code() {
    curl --noproxy '*' -sS --max-time 2 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true
}
start_code="$(curl --noproxy '*' -sS --max-time 2 -o /dev/null -w '%{http_code}' \
    -X POST -H 'content-type: application/json' \
    -d '{"calendar_id":"fixture@example.invalid","customer_approved_read_only":true}' \
    'http://127.0.0.1:8794/v1/inbound-recovery/calendar-connect/start' 2>/dev/null || true)"
callback_code="$(get_code 'http://127.0.0.1:8794/v1/inbound-recovery/calendar-connect/callback')"
status_code="$(get_code 'http://127.0.0.1:8794/v1/inbound-recovery/calendar-connect/status')"
docs_code="$(get_code 'http://127.0.0.1:8794/openapi.json')"
socket="$(ss -H -lnt '( sport = :8794 )')"
if [[ "$health" != "200" || "$start_code" != "404" ||
      "$callback_code" != "404" || "$status_code" != "404" ||
      "$docs_code" != "404" ]] ||
   ! grep -Fq '127.0.0.1:8794' <<<"$socket" ||
   [[ "$(wc -l <<<"$socket")" -ne 1 ]] ||
   ! systemctl -q is-active "$service"; then
    cleanup_failure
    exit 4
fi
echo "DARK_STAGING=DEPLOYED_LOOPBACK_ONLY"
echo "DARK_STAGING_HEALTH=200"
echo "DARK_STAGING_OAUTH_START=404"
echo "DARK_STAGING_OAUTH_CALLBACK=404"
echo "DARK_STAGING_STATUS=404"
echo "DARK_STAGING_DOCS=404"
echo "DARK_STAGING_MANUS_DISPATCH=NO"
echo "DARK_STAGING_EXTERNAL_ACTIONS=NO"
echo "DARK_STAGING_REBOOT_ENABLE=NO"
