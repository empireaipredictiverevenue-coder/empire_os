#!/usr/bin/env bash
# Owner-safe, single-route addition to live founder CRM; no database/CRM writes.
# Never deploy the stale /srv/empire_os/empire_os/revenue_crm_api.py wholesale.
set -euo pipefail
MODE="${1:-}"
case "$MODE" in
  --preflight|--apply-founder-approved-private-crm-name-preview) ;;
  *) echo 'Usage: --preflight | --apply-founder-approved-private-crm-name-preview' >&2;exit 2;;
esac
[[ "${2:-}" == "" ]] || { echo 'Usage: one mode only' >&2;exit 2; }
die(){ echo "HOLD_$1" >&2;exit 4; }

UNIT=empire-revenue-crm-pilot.service
PRIOR=/opt/empire-ai/crm-pilot-releases/founder-queue-20261018v1
STAGE=/home/ubuntu/empire_worktrees/empire_crm_solar_tenant_name_preview_20261019
TARGET=/opt/empire-ai/crm-pilot-releases/founder-queue-solar-name-20261019v1
OVERRIDE=/etc/systemd/system/empire-revenue-crm-pilot.service.d/60-solar-tenant-prospect-name-preview.conf
EXISTING=/etc/systemd/system/empire-revenue-crm-pilot.service.d/50-founder-release-20261018.conf
API=empire_os/revenue_crm_api.py
HELPER=empire_os/workspace_solar_crm_tenant_prospect_match.py
OLD_SHA=2cf8a796201d2bd914fb8ee206974606857fd6a4393e6b3234fadd2bba651e49
NEW_SHA=9ca7e8bc10b68208a5ce3e1444ce64260e1d8fc4152c99c18cb83570d1208507
HELPER_SHA=6de1291fe18b239a21cb96e5894084f463f85ca98e0f5016b337ccb2e0b0c469
NEW_ROUTE=/v1/revenue-crm/workspace-solar/prospect-name-matches/preview
BASE=http://127.0.0.1:8783

require_sha(){
 local file="$1" sha="$2" out
 [[ -f "$file" && ! -L "$file" ]] || die SOURCE_MISSING_OR_SYMLINK
 out="$(sha256sum "$file")"
 [[ "${out%% *}" == "$sha" ]] || die UNEXPECTED_SOURCE_DRIFT
}
require_sha "$PRIOR/$API" "$OLD_SHA"
require_sha "$STAGE/$API" "$NEW_SHA"
require_sha "$STAGE/$HELPER" "$HELPER_SHA"
require_sha "/srv/empire_os/$HELPER" "$HELPER_SHA"
[[ ! -e "$PRIOR/$HELPER" ]] || die CONCURRENT_EXISTING_CRM_FEATURE
[[ -f "$PRIOR/empire_os/revenue_crm_pilot_asgi.py" ]] || die BASELINE_SERVICE_MODULE_MISSING
diffs="$(rsync -rcn --itemize-changes --exclude='__pycache__' --exclude='*.pyc' \
 --exclude='revenue_crm_api.py' --exclude='workspace_solar_crm_tenant_prospect_match.py' \
 "$PRIOR/empire_os/" "$STAGE/empire_os/")"
[[ -z "$diffs" ]] || die OTHER_AGENT_CRM_PACKAGE_DRIFT
[[ ! -e "$OVERRIDE" && ! -L "$OVERRIDE" && ! -e "$TARGET" ]] || die ALREADY_APPLIED_OR_DESTINATION_OCCUPIED
# Validate frozen 28-route candidate without opening any live CRM credentials.
# Run outside /srv working directory so import resolves only the staged
# active-revision snapshot, never the older canonical router.
(
 cd /tmp
 PYTHONPATH="$STAGE" /srv/empire_os/.venv/bin/python -B - <<'PY'
from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.workspace_solar_crm_tenant_prospect_match import SCHEMA
paths=[route.path for route in create_revenue_crm_router().routes]
assert len(paths)==28 and len(set(paths))==28, "CANDIDATE_CRM_ROUTE_COUNT_DRIFT"
needed=(
 "/v1/revenue-crm/workspace-solar/prospect-name-matches/preview",
 "/v1/revenue-crm/prospects",
 "/v1/revenue-crm/partner-conversations/review",
 "/v1/revenue-crm/commercial-loop/review",
 "/v1/revenue-crm/journeys/acquisition-scorecard",
)
assert all(path in paths for path in needed), "CANDIDATE_CRM_ROUTE_OWNERSHIP_DRIFT"
assert SCHEMA=="empire.workspace_solar_tenant_prospect_name_preview.v1"
print("FROZEN_28_ROUTE_CRM_PACKAGE_VERIFIED")
PY
) || die FROZEN_CANDIDATE_IMPORT_OR_ROUTES_INVALID
[[ -f "$EXISTING" && ! -L "$EXISTING" ]] || die FOUNDER_RELEASE_OVERRIDE_MISSING
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || die CRM_NOT_ACTIVE
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$PRIOR" ]] || die ACTIVE_CRM_OWNER_RELEASE_CHANGED
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$EXISTING" ]] || die CRM_DROPINS_DRIFT
for unit in empire-founder-console.service empire-founder-dashboard-api.service empire-buyer-acquisition-team.timer;do
 [[ "$(systemctl is-active "$unit")" == active ]] || die OTHER_SERVICE_UNHEALTHY
done
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$BASE/v1/revenue-crm/health")" == 200 ]] || die CRM_HEALTH_FAILED
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$BASE/v1/revenue-crm/prospects")" == 401 ]] || die CRM_AUTH_BOUNDARY_UNVERIFIED
[[ "$(curl -sS --max-time 7 -o /dev/null -w '%{http_code}' "$BASE$NEW_ROUTE")" == 404 ]] || die PREVIEW_ROUTE_ALREADY_CHANGED
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PUBLIC_FOUNDER_ROUTE_EXPOSED
echo 'PRECHECK_PASS: current founder CRM source exact, 28 candidate routes, signed auth required, no other agent source drift'
if [[ "$MODE" == --preflight ]];then
 echo 'PRIVATE_CRM_SOLAR_NAME_PREVIEW_STAGED_NOT_DEPLOYED'
 exit 0
fi

[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED
temp_override=''
baseline=''
activated=0
cleanup(){
 local rc="$?"
 [[ -z "$temp_override" ]] || rm -f "$temp_override"
 [[ -z "$baseline" ]] || rm -f "$baseline"
 if [[ "$activated" == 1 && "$rc" != 0 ]];then
  echo 'PRIVATE_CRM_SOLAR_NAME_PREVIEW_ROLLBACK_TO_FOUNDER_QUEUE' >&2
  rm -f "$OVERRIDE"
  systemctl daemon-reload
  systemctl restart "$UNIT" || true
 fi
}
trap cleanup EXIT
trap 'exit 98' INT TERM
umask 077
baseline="$(mktemp /tmp/empire-crm-route-manifest.XXXXXXXX)"
curl -fsS --max-time 9 "$BASE/openapi.json" > "$baseline" || die BASELINE_OPENAPI_UNAVAILABLE
python3 - "$baseline" "$NEW_ROUTE" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))['paths']
assert len(p)>=20 and sys.argv[2] not in p, 'UNEXPECTED_CRM_ROUTE_BASELINE'
for route in (
 "/v1/revenue-crm/health",
 "/v1/revenue-crm/prospects",
 "/v1/revenue-crm/journeys/acquisition-scorecard",
 "/v1/revenue-crm/partner-conversations/review",
 "/v1/revenue-crm/commercial-loop/review",
):
 assert route in p, route
print("CURRENT_LIVE_CRM_ROUTE_MANIFEST_CAPTURED",len(p))
PY
mkdir -p "$TARGET/empire_os"
# Do not copy private/root-only historical override files or credentials.
rsync -a --exclude='__pycache__' --exclude='*.pyc' "$PRIOR/empire_os/" "$TARGET/empire_os/"
install -m 0644 "$STAGE/$API" "$TARGET/$API"
install -m 0644 "$STAGE/$HELPER" "$TARGET/$HELPER"
chown -R root:root "$TARGET"
require_sha "$TARGET/$API" "$NEW_SHA"
require_sha "$TARGET/$HELPER" "$HELPER_SHA"
[[ "$(rsync -rcn --itemize-changes --exclude='__pycache__' --exclude='*.pyc' \
 --exclude='revenue_crm_api.py' --exclude='workspace_solar_crm_tenant_prospect_match.py' \
 "$PRIOR/empire_os/" "$TARGET/empire_os/")" == "" ]] || die RELEASE_OTHER_MODULE_DRIFT
temp_override="$(mktemp /etc/systemd/system/empire-revenue-crm-pilot.service.d/.60-solar-name.XXXXXXXX)"
printf '[Service]\nWorkingDirectory=%s\nEnvironment=PYTHONPATH=%s\n' "$TARGET" "$TARGET" > "$temp_override"
chmod 0644 "$temp_override"
mv "$temp_override" "$OVERRIDE"
temp_override=''
activated=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for n in $(seq 1 18);do
 code="$(curl -sS --max-time 4 -o /dev/null -w '%{http_code}' "$BASE$NEW_ROUTE" 2>/dev/null || true)"
 if [[ "$code" == 401 ]];then ready=1;break;fi
 sleep 1
done
[[ "$ready" == 1 ]] || die NEW_AUTHENTICATED_ROUTE_NOT_READY
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$TARGET" ]] || die WRONG_ACTIVE_CRM_RELEASE
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || die NEW_CRM_NOT_ACTIVE
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "$BASE/v1/revenue-crm/health")" == 200 ]] || die CRM_HEALTH_REGRESSION
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "$BASE/v1/revenue-crm/prospects")" == 401 ]] || die AUTH_REQUIRED_REGRESSION
python3 - "$baseline" "$BASE/openapi.json" "$NEW_ROUTE" <<'PY'
import json,sys,urllib.request
before=json.load(open(sys.argv[1],encoding='utf-8'))["paths"]
with urllib.request.urlopen(sys.argv[2],timeout=9) as resp:
 after=json.load(resp)["paths"]
new=sys.argv[3]
assert set(after)==set(before)|{new},'CRM_ROUTING_DRIFT'
for path,methods in before.items():
 assert after[path]==methods,'EXISTING_CRM_OPENAPI_SCHEMA_DRIFT'
assert set(after[new])=={"get"},'NAME_PREVIEW_MUST_BE_GET_ONLY'
print("FOUNDER_CRM_ALL_PRIOR_ROUTE_AND_SCHEMA_PARITY_VERIFIED",len(after))
PY
for unit in empire-founder-console.service empire-founder-dashboard-api.service empire-buyer-acquisition-team.timer;do
 [[ "$(systemctl is-active "$unit")" == active ]] || die SUPPORTING_SERVICE_REGRESSION
done
[[ "$(curl -sS --max-time 9 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PUBLIC_FOUNDER_ROUTE_EXPOSED
activated=0
echo 'PRIVATE_CRM_SOLAR_TENANT_NAME_PREVIEW_RELEASE_VERIFIED'
echo 'source=founder-queue-20261018v1 new_route=signed_tenant_read_only crm_writes=no outbound_sent=no'
echo "rollback=rm -f $OVERRIDE && systemctl daemon-reload && systemctl restart $UNIT"
