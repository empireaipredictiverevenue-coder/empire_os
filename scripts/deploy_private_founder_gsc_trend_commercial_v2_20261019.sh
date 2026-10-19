#!/usr/bin/env bash
# Founder-approved private-only GSC charts on top of Commercial Operations v2.
# This script never mutates EmpireDB, public routing, marketing or payments.
set -Eeuo pipefail

[[ "$#" == 1 ]] || { echo 'Usage: --preflight | --apply-founder-approved-private-gsc-trend-commercial-v2' >&2; exit 2; }
[[ "$1" == "--preflight" || "$1" == "--apply-founder-approved-private-gsc-trend-commercial-v2" ]] || { echo 'UNKNOWN_ACTION: only exact private release permitted' >&2; exit 2; }
MODE="$1"
UNIT=empire-founder-console.service
ROOT=/srv/empire_os
PRIOR=/opt/empire-ai/founder-console-releases/commercial-ops-v2-49aba1fa
TARGET=/home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019
DROP_DIR=/etc/systemd/system/empire-founder-console.service.d
DROP="$DROP_DIR/98-private-gsc-trend-release.conf"
REQUIRED_DROPINS="$DROP_DIR/70-private-solar-review-release.conf $DROP_DIR/80-private-reply-triage-release.conf $DROP_DIR/90-private-historical-evidence-release.conf $DROP_DIR/95-commercial-loop-release.conf $DROP_DIR/96-private-seo-department-release.conf $DROP_DIR/97-commercial-operations-v2.conf"
WEB=http://127.0.0.1:3001
API=http://127.0.0.1:8771
PUBLIC=https://empire-ai.co.uk
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36'
OLD_ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /founder/commercial-pipeline /revenue /department)
fail(){ echo "GSC_CHART_RELEASE_HELD:$1" >&2; exit 4; }
route_code() { curl -sS --max-time 12 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true; }
public_closed() {
  [[ "$(curl -sS -A "$UA" --max-time 12 -o /dev/null -w '%{http_code}' "$PUBLIC/department" 2>/dev/null || true)" == 404 ]] &&
  [[ "$(curl -sS -A "$UA" --max-time 12 -o /dev/null -w '%{http_code}' "$PUBLIC/v1/search/department/review" 2>/dev/null || true)" == 404 ]]
}
service_guard() {
  [[ "$(systemctl is-active "$UNIT")" == active ]] || fail FOUNDER_SERVICE_NOT_ACTIVE
  [[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$PRIOR" ]] || fail ACTIVE_FOUNDER_OWNER_CHANGED
  [[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$REQUIRED_DROPINS" ]] || fail FOUNDER_RELEASE_STACK_CHANGED
  [[ "$(systemctl show "$UNIT" -p ExecStart --value)" == *"-H 127.0.0.1 -p 3001"* ]] || fail NON_LOOPBACK_FOUNDER_BIND
  [[ ! -e "$DROP" && ! -L "$DROP" ]] || fail PRIVATE_CHART_DROPIN_ALREADY_EXISTS
  [[ "$(systemctl is-active empire-search-intelligence-api.service)" == active ]] || fail SEARCH_INTELLIGENCE_NOT_ACTIVE
}
# An exact source and pinned-binary audit, not a broad readiness guess.
cd "$ROOT"
PRECHECK="$("$ROOT/.venv/bin/python" -m scripts.review_private_gsc_trend_commercial_v2_20261019 --read-only)" || fail PRIVATE_CHART_SOURCE_PREFLIGHT_FAILED
printf '%s\n' "$PRECHECK"
printf '%s\n' "$PRECHECK" | "$ROOT/.venv/bin/python" -c 'import sys,json; d=json.load(sys.stdin);assert d["status"]=="FROZEN_CANDIDATE_BACKEND_READY_REQUIRES_FOUNDER_RELEASE_APPROVAL" and d["exact_new_build_verified"] is True and d["active_prior_console_unchanged"] is True and d["ten_current_private_routes_healthy"] is True and d["daily_api_source_attested"] is True and d["public_website_seo_routes_404"] is True and d["production_changed"] is False' || fail PRIVATE_CHART_PREFLIGHT_CONTRADICTION

service_guard
for path in "${OLD_ROUTES[@]}"; do
  [[ "$(route_code "$WEB$path")" == 200 ]] || fail PRIOR_PRIVATE_ROUTE_UNAVAILABLE
done
public_closed || fail PUBLIC_DEPARTMENT_NOT_CLOSED
[[ "$(route_code "$API/v1/search/department/review")" == 200 ]] || fail DAILY_SEARCH_BACKEND_NOT_READY
[[ "$("$ROOT/.venv/bin/python" -c 'from pathlib import Path; from scripts.review_private_gsc_trend_commercial_v2_20261019 import source_frozen;print("yes" if source_frozen() else "no")')" == yes ]] || fail FROZEN_BUILD_CHANGED
echo 'FOUNDER_GSC_CHART_PREFLIGHT_PASS: commercial-v2 preserved, 10 routes, daily source, public 404, pinned build'
if [[ "$MODE" == --preflight ]]; then
  echo 'FOUNDER_GSC_CHART_STAGED_NOT_DEPLOYED'
  exit 0
fi

[[ "$(id -u)" -eq 0 ]] || fail SUDO_ROOT_REQUIRED
[[ -d "$DROP_DIR" && ! -L "$DROP_DIR" ]] || fail SERVICE_DROPIN_DIR_CHANGED
exec 9>/run/lock/empire-founder-gsc-chart-release.lock
flock -n 9 || fail FOUNDER_GSC_CHART_RELEASE_IN_PROGRESS
# Immediately re-check service ownership after acquiring release lock.
service_guard

switched=0
tmp=''
cleanup(){
  result=$?
  trap - EXIT
  [[ -z "$tmp" ]] || rm -f -- "$tmp"
  if [[ "$switched" == 1 && "$result" != 0 ]]; then
    echo 'GSC_CHART_ROLLBACK_START: restore preexisting Commercial Operations v2 console' >&2
    rm -f -- "$DROP"
    systemctl daemon-reload || true
    systemctl restart "$UNIT" || true
    echo 'GSC_CHART_ROLLBACK_ATTEMPTED' >&2
  fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 98' INT TERM
umask 077
tmp="$(mktemp "$DROP_DIR/.98-private-gsc-trend.XXXXXX")"
printf '[Service]\nWorkingDirectory=%s\n' "$TARGET" > "$tmp"
chmod 0644 "$tmp"
# Hard-link creation is atomic and EXCLUSIVE: refuse any owner race.
ln -- "$tmp" "$DROP" || fail PRIVATE_DROPIN_RACE_DETECTED
switched=1
rm -f -- "$tmp"
tmp=''
[[ -f "$DROP" ]] || fail PRIVATE_DROPIN_MISSING
systemctl daemon-reload
systemctl restart "$UNIT"

ready=0
for attempt in $(seq 1 45); do
  if [[ "$(route_code "$WEB/department")" == 200 ]]; then ready=1;break;fi
  sleep 1
done
[[ "$ready" == 1 ]] || fail GSC_DASHBOARD_DID_NOT_RECOVER
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$TARGET" ]] || fail ACTIVE_RELEASE_TARGET_MISMATCH
[[ "$(systemctl is-active "$UNIT")" == active ]] || fail NEW_FOUNDER_SERVICE_NOT_ACTIVE
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$REQUIRED_DROPINS $DROP" ]] || fail FOUNDER_RELEASE_OVERRIDES_UNEXPECTED
for path in "${OLD_ROUTES[@]}"; do
  [[ "$(route_code "$WEB$path")" == 200 ]] || fail PREVIOUS_FOUNDER_ROUTE_REGRESSION
done
# Validate rendered HTML semantics without depending on mutable click counts.
curl -fsS --max-time 15 "$WEB/department" |
  "$ROOT/.venv/bin/python" -c 'import sys;h=sys.stdin.read().lower();assert all(x in h for x in ("observed organic search trend","observed daily impressions","observed daily clicks","unified seo evidence","noindex"));assert "department evidence unavailable" not in h' || fail CHART_NOT_SERVER_RENDERED
public_closed || fail PUBLIC_SEO_ROUTE_EXPOSED
[[ "$(route_code "$API/health")" == 200 ]] || fail EXISTING_SEARCH_API_REGRESSION
switched=0
echo 'PRIVATE_FOUNDER_GSC_CHART_RELEASE_VERIFIED'
echo 'routes=10 chart_data=first_party_gsc mode=OBSERVE private_only=yes commercial_ops_v2=preserved public_site_unchanged=yes'
echo "rollback=sudo rm -f $DROP && sudo systemctl daemon-reload && sudo systemctl restart $UNIT"
