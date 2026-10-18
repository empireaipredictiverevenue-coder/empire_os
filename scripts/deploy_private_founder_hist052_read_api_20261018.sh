#!/usr/bin/env bash
# Add only the missing historical-status GET to the CURRENT active 8766 API.
# Keep the other agent's release (bridge-sources-history-75912015) intact.
# This does NOT apply EmpireDB 052 or insert evidence receipts.
set -euo pipefail
MODE="${1:-}"
case "$MODE" in
  --preflight|--apply-approved-additive-private-read-api) ;;
  *) echo 'Usage: --preflight | --apply-approved-additive-private-read-api' >&2;exit 2;;
esac
[[ "${2:-}" == "" ]] || { echo 'Usage: one argument only' >&2;exit 2; }
die(){ echo "HOLD_$1" >&2;exit 4; }

ROOT=/srv/empire_os
UNIT=empire-founder-dashboard-api.service
SRC=/opt/empire-ai/founder-read-releases/bridge-sources-history-75912015
DST=/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018
DROP_DIR=/etc/systemd/system/$UNIT.d
DROP="$DROP_DIR/95-private-historical-evidence-read-api.conf"
ROUTER=empire_os/founder_mailbox_api.py
MODULE=empire_os/workspace_solar_historical_status.py
OLD_SHA=c50644c4adcfa131a9469094953bd6577c5467cf1f3003d47a492f7e9d250864
NEW_SHA=65cddee4523cade2e299f0ca63c98cf0bf877dfad429feae62834c7ce3f18d0a
STATUS_SHA=1dd74abed08b01d0951fdb68f1bbd7b9ffce0fd0de3d07b42bc504e090e83950
HIST=http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-historical-evidence-status
PSQL_CURRENT=http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-canonical-intent-review
REPLY=http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-reply-review

check_sha(){
 local file="$1" expected="$2" got
 [[ -f "$file" && ! -L "$file" ]] || die RELEASE_FILE_MISSING_OR_SYMLINK
 got="$(sha256sum "$file")"
 [[ "${got%% *}" == "$expected" ]] || die UNEXPECTED_CONCURRENT_SOURCE_CHANGE
}
check_sha "$SRC/$ROUTER" "$OLD_SHA"
check_sha "$DST/$ROUTER" "$NEW_SHA"
check_sha "$DST/$MODULE" "$STATUS_SHA"
check_sha "$ROOT/$MODULE" "$STATUS_SHA"
changes="$(rsync -rcn --itemize-changes --exclude='__pycache__' --exclude='*.pyc' --exclude="$ROUTER" --exclude="$MODULE" "$SRC/" "$DST/")"
[[ -z "$changes" ]] || die OTHER_AGENT_RELEASE_SOURCE_DRIFT
[[ ! -e "$DROP" && ! -L "$DROP" ]] || die NEW_OVERRIDE_ALREADY_PRESENT
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || die CURRENT_READ_API_NOT_RUNNING
exec_line="$(systemctl show "$UNIT" -p ExecStart --value)"
[[ "$exec_line" == *"--app-dir $SRC empire_os.founder_dashboard_service:app --host 127.0.0.1 --port 8766"* ]] ||
  die UNEXPECTED_ACTIVE_READ_RELEASE
dropins="$(systemctl show "$UNIT" -p DropInPaths --value)"
[[ "$dropins" == *"/90-commercial-pipeline-release.conf" && "$dropins" != *"/95-private-historical-evidence-read-api.conf"* ]] ||
  die EXISTING_OVERRIDE_CHANGED
for service in empire-founder-console.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer;do
 [[ "$(systemctl is-active "$service")" == active ]] || die RELATED_RUNTIME_NOT_ACTIVE
done
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' http://127.0.0.1:8766/health)" == 200 ]] || die FOUNDER_HEALTH_FAILED
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$REPLY")" == 200 ]] || die GMAIL_REVIEW_REGRESSION
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$PSQL_CURRENT")" == 200 ]] || die CANONICAL_REVIEW_UNAVAILABLE
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$HIST")" == 404 ]] || die EXPECTED_MISSING_ROUTE_ALREADY_CHANGED
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PRIVATE_FOUNDER_ROUTE_EXPOSED
echo 'PRECHECK_PASS: current bridge release preserved, two-file additive patch, three prior reader gates, public 404'
if [[ "$MODE" == --preflight ]];then
 echo 'FOUNDER_HISTORICAL_READ_API_STAGED_NOT_DEPLOYED'
 exit 0
fi
[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED
tmp=''
activated=0
cleanup(){
 local rc="$?"
 [[ -z "$tmp" ]] || rm -f "$tmp"
 if [[ "$activated" == 1 && "$rc" != 0 ]];then
  echo 'PRIVATE_HISTORICAL_READ_API_ROLLBACK_TO_EXISTING_BRIDGE' >&2
  rm -f "$DROP"
  systemctl daemon-reload
  systemctl restart "$UNIT" || true
 fi
}
trap cleanup EXIT
trap 'exit 98' INT TERM
umask 077
tmp="$(mktemp "$DROP_DIR/.95-historical-read.XXXXXXXX")"
printf '[Service]\nExecStart=\nExecStart=/srv/empire_os/.venv/bin/uvicorn --app-dir %s empire_os.founder_dashboard_service:app --host 127.0.0.1 --port 8766\n' "$DST" > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$DROP"
tmp=''
activated=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for attempt in $(seq 1 20);do
 if curl -fsS --max-time 5 "$HIST" -o /tmp/empire-hist052-founder-api-release-review.json 2>/dev/null;then
  ready=1
  break
 fi
 sleep 1
done
[[ "$ready" == 1 ]] || die NEW_PRIVATE_READ_SERVICE_NOT_READY
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/empire-hist052-founder-api-release-review.json')
d=json.loads(p.read_text())
assert d['status']=='PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD'
assert d['private_custody_receipts_verified']==6
assert d['database_historical_receipts_verified']==0
assert d['database_historical_receipt_table_active'] is False
assert d['crm_records_created']==0 and d['outbound_sent'] is False
print('VERIFIED_SIX_PRIVATE_CUSTODY_AND_ZERO_DATABASE_ADMISSIONS')
PY
rm -f /tmp/empire-hist052-founder-api-release-review.json
for route in /health /v1/founder-mailbox/workspace-solar-reply-review /v1/founder-mailbox/workspace-solar-canonical-intent-review;do
 [[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:8766$route")" == 200 ]] || die PRESERVED_API_ROUTE_REGRESSION
done
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die UNEXPECTED_PUBLIC_EXPOSURE
[[ "$(systemctl is-active "$UNIT")" == active ]] || die NEW_READ_SERVICE_INACTIVE
activated=0
echo 'FOUNDER_HISTORICAL_READ_API_ADDITIVE_RELEASE_VERIFIED'
echo 'historical_status=read_only restored_to_existing_bridge=true crm_writes=no email_sent=no'
echo "rollback=rm -f $DROP && systemctl daemon-reload && systemctl restart $UNIT"
