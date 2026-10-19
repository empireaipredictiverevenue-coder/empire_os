#!/usr/bin/env bash
# Empire Analytics v1: approved private-only frontend switch with fail-closed rollback.
set -Eeuo pipefail
[[ "$#" == 1 ]] || { echo 'Usage: --preflight | --apply-founder-approved-private-analytics-v1' >&2;exit 2; }
[[ "$1" == --preflight || "$1" == --apply-founder-approved-private-analytics-v1 ]] || { echo 'INVALID_ACTION' >&2;exit 2; }
MODE="$1"
ROOT=/srv/empire_os
UNIT=empire-founder-console.service
TARGET=/home/ubuntu/empire_worktrees/empire_analytics_platform_branded_candidate_20261019
PRIOR=/home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019
BASE=/etc/systemd/system/empire-founder-console.service.d
DROP="$BASE/99-private-empire-analytics-release.conf"
REQUIRED="$BASE/70-private-solar-review-release.conf $BASE/80-private-reply-triage-release.conf $BASE/90-private-historical-evidence-release.conf $BASE/95-commercial-loop-release.conf $BASE/96-private-seo-department-release.conf $BASE/97-commercial-operations-v2.conf $BASE/98-private-gsc-trend-release.conf"
OLD_ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /founder/commercial-pipeline /revenue /department)
NEW_ROUTES=("${OLD_ROUTES[@]}" /department/evidence)
fail(){ echo "ANALYTICS_RELEASE_HELD:$1" >&2; exit 4; }
code(){ curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$1" 2>/dev/null || true; }
public_closed(){
 local p
 for p in /department /department/evidence /v1/search/department/review;do
  [[ "$(curl -sS -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36' --max-time 10 -o /dev/null -w '%{http_code}' "https://empire-ai.co.uk$p" 2>/dev/null || true)" == 404 ]] || return 1
 done
}
owner_guard(){
 [[ "$(systemctl is-active "$UNIT")" == active ]] || fail PREVIOUS_FOUNDER_SERVICE_NOT_ACTIVE
 [[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$PRIOR" ]] || fail ACTIVE_FOUNDER_OWNER_CHANGED
 [[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$REQUIRED" ]] || fail OWNER_SYSTEMD_STACK_CHANGED
 [[ "$(systemctl show "$UNIT" -p ExecStart --value)" == *"-H 127.0.0.1 -p 3001"* ]] || fail NON_PRIVATE_FOUNDER_BIND
 [[ ! -e "$DROP" && ! -L "$DROP" ]] || fail ANALYTICS_DROPIN_ALREADY_EXISTS
 [[ "$(systemctl is-active empire-search-intelligence-api.service)" == active ]] || fail SEARCH_API_NOT_ACTIVE
}
cd "$ROOT"
report="$("$ROOT/.venv/bin/python" -m scripts.review_empire_analytics_private_release_20261019 --read-only)" || fail PREVIEW_PREFLIGHT_HELD
printf '%s\n' "$report"
printf '%s\n' "$report" | "$ROOT/.venv/bin/python" -c 'import json,sys;d=json.load(sys.stdin);assert d["status"]=="FROZEN_BRANDED_ANALYTICS_READY_FOR_FOUNDER_RELEASE" and d["frozen_brand_and_source_verified"] is True and d["existing_founder_owner_preserved"] is True and d["ten_existing_routes_healthy"] is True and d["backend_first_party_evidence_ready"] is True and d["public_department_routes_closed"] is True and d["visitor_analytics_connected"] is False and d["production_changed"] is False' || fail SOURCE_PROOF_CONTRADICTION
owner_guard
for p in "${OLD_ROUTES[@]}";do [[ "$(code "http://127.0.0.1:3001$p")" == 200 ]] || fail PRIOR_ROUTE_UNAVAILABLE;done
[[ "$(code http://127.0.0.1:3001/department/evidence)" == 404 ]] || fail ARCHIVED_EVIDENCE_ALREADY_ACTIVE
public_closed || fail PUBLIC_ACCESS_CHANGED
echo 'EMPIRE_ANALYTICS_PRIVATE_PREFLIGHT_PASS: canonical brand, source provenance, existing console, 10 routes, public 404'
if [[ "$MODE" == --preflight ]];then
 echo 'EMPIRE_ANALYTICS_STAGED_NOT_DEPLOYED'
 exit 0
fi

[[ "$(id -u)" -eq 0 ]] || fail ROOT_REQUIRED
[[ -d "$BASE" && ! -L "$BASE" ]] || fail SYSTEMD_DROPIN_DIR_NOT_VERIFIED
exec 9>/run/lock/empire-analytics-founder-release.lock
flock -n 9 || fail RELEASE_ALREADY_IN_PROGRESS
owner_guard
# The privileged operator holds the exact immutable release hashes and source.
"$ROOT/.venv/bin/python" -c 'from scripts.review_empire_analytics_private_release_20261019 import release_frozen;assert release_frozen()' || fail RELEASE_HASH_DRIFT

switched=0
tmp=''
cleanup(){
 local result="$?"
 trap - EXIT
 [[ -z "$tmp" ]] || rm -f -- "$tmp"
 if [[ "$switched" == 1 && "$result" != 0 ]];then
  echo 'EMPIRE_ANALYTICS_RESTORING_PREVIOUS_FOUNDER_RELEASE' >&2
  rm -f -- "$DROP"
  systemctl daemon-reload || true
  systemctl restart "$UNIT" || true
  echo 'EMPIRE_ANALYTICS_ROLLBACK_ATTEMPTED' >&2
 fi
 exit "$result"
}
trap cleanup EXIT
trap 'exit 98' INT TERM
umask 077
tmp="$(mktemp "$BASE/.99-private-empire-analytics.XXXXXX")"
printf '[Service]\nWorkingDirectory=%s\n' "$TARGET" > "$tmp"
chmod 0644 "$tmp"
# Exclusive creation. No replacing an existing higher-priority overlay.
ln -- "$tmp" "$DROP" || fail RELEASE_CONCURRENT_OWNER_RACE
switched=1
rm -f -- "$tmp"
tmp=''
systemctl daemon-reload
systemctl restart "$UNIT"

ready=0
for attempt in $(seq 1 50);do
 if [[ "$(code http://127.0.0.1:3001/department)" == 200 ]];then ready=1;break;fi
 sleep 1
done
[[ "$ready" == 1 ]] || fail ANALYTICS_DASHBOARD_START_TIMEOUT
[[ "$(systemctl is-active "$UNIT")" == active ]] || fail FOUNDER_UNIT_NO_LONGER_ACTIVE
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$TARGET" ]] || fail WRONG_WORKTREE_ACTIVE
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$REQUIRED $DROP" ]] || fail UNEXPECTED_OVERRIDES
for p in "${NEW_ROUTES[@]}";do [[ "$(code "http://127.0.0.1:3001$p")" == 200 ]] || fail PRIVATE_ROUTE_REGRESSION;done
# Assert semantic DOM evidence, not exact raw-HTML substrings: the H1 is
# split by a styled span, while HTML entities need decoding. This validator
# explicitly rejects script/hydration-only markers and the held-data state.
curl -fsS --max-time 18 http://127.0.0.1:3001/department |
 "$ROOT/.venv/bin/python" -m scripts.verify_private_empire_analytics_html_20261019 --verify-stdin || fail BRANDED_METRICS_NOT_RENDERED
curl -fsS --max-time 15 http://127.0.0.1:3001/department/evidence |
 "$ROOT/.venv/bin/python" -c 'import sys;s=sys.stdin.read().lower();assert "unified seo evidence" in s and "404 editorial priorities" in s' || fail ARCHIVED_EVIDENCE_NOT_RENDERED
[[ "$(code http://127.0.0.1:8771/health)" == 200 ]] || fail SEARCH_API_REGRESSION
public_closed || fail PUBLIC_SEO_EXPOSURE_CHANGED

switched=0
echo 'EMPIRE_ANALYTICS_PRIVATE_RELEASE_VERIFIED'
echo 'routes=11 brand=empire_ai_published metrics=first_party_gsc commercial_ops_v2=preserved site_publication=none tracking=not_activated'
echo "rollback=sudo rm -f $DROP && sudo systemctl daemon-reload && sudo systemctl restart $UNIT"
