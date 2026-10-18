#!/usr/bin/env bash
# Incremental, loopback-only SEO evidence panel atop the existing frozen
# Founder Console. No public route, new login, outbound, CRM, DB, or payment.
set -euo pipefail
UNIT=empire-founder-console.service
PRIOR=/opt/empire-ai/founder-console-releases/bridge-sources-history-75912015
TARGET=/home/ubuntu/empire_worktrees/empire_founder_seo_department_bridge_candidate_20261018
SOURCE=/srv/empire_os/apps/search-command-centre
BASE=/etc/systemd/system/$UNIT.d
PRIOR_A=$BASE/70-private-solar-review-release.conf
PRIOR_B=$BASE/80-private-reply-triage-release.conf
PRIOR_C=$BASE/90-private-historical-evidence-release.conf
PRIOR_D=$BASE/95-commercial-loop-release.conf
DROP=$BASE/96-private-seo-department-release.conf
OLD_ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /founder/commercial-pipeline /revenue)
fail(){ echo "HOLD_$1" >&2;exit 4; }
[[ "${1:-}" == --preflight || "${1:-}" == --apply-founder-approved-private-seo-release ]] || { echo 'Usage: --preflight | --apply-founder-approved-private-seo-release' >&2;exit 2; }
[[ "${2:-}" == "" ]] || { echo 'Only one argument allowed' >&2;exit 2; }
MODE=$1

# Validate the EXACT deployed previous release source and incremental
# replacement, not the main checkout's other unfinished agent edits.
python3 - "$PRIOR" "$TARGET" "$SOURCE" <<'PY'
import hashlib
from pathlib import Path
import sys
prior, target, source = map(Path, sys.argv[1:])
if any(p.is_symlink() or not p.is_dir() for p in (prior,target,source)):
    raise SystemExit("HOLD_RELEASE_WORKTREE_NOT_REGULAR")
def files(base):
    return {p.relative_to(base/'src').as_posix():p for p in (base/'src').rglob('*') if p.is_file()}
old,new=files(prior),files(target)
expected_added={'app/department/page.tsx'}
changed={'app/page.tsx','lib/search-api.ts'}
if set(new)-set(old)!=expected_added or set(old)-set(new):
    raise SystemExit("HOLD_UNEXPECTED_ROUTE_OR_SOURCE_ADDITION")
actual_changed={k for k in old if old[k].read_bytes()!=new[k].read_bytes()}
if actual_changed!=changed:
    raise SystemExit("HOLD_OTHER_FOUNDER_SOURCE_DRIFT")
if any(p.is_symlink() or p.stat().st_size>700_000 for p in new.values()):
    raise SystemExit("HOLD_SOURCE_SYMLINK_OR_OVERSIZE")
for k in changed | expected_added:
    if new[k].read_bytes()!=(source/'src'/k).read_bytes():
        raise SystemExit("HOLD_CANONICAL_SEO_COMPONENT_DRIFT")
if hashlib.sha256((prior/'src/app/founder/mail/workspace-solar-review.tsx').read_bytes()).hexdigest() != '3fb1ecba105dc5c8a966295d39681d9e45ede4c373edf548f0d3a59c436124fd':
    raise SystemExit("HOLD_PREVIOUS_FOUNDER_MAIL_SOURCE_CHANGED")
print('EXACT_FOUNDER_SOURCE_PARITY_PASS: prior routes unchanged; only seo route and two matching source additions')
PY

[[ -L "$TARGET/node_modules" && "$(readlink "$TARGET/node_modules")" == "$SOURCE/node_modules" ]] || fail DEPENDENCY_LINK_DRIFT
[[ -f "$TARGET/.next/BUILD_ID" && -f "$TARGET/.next/server/app/department/page.js" ]] || fail FROZEN_SEO_PRODUCTION_BUILD_ABSENT
# Pin the exact independently tested frozen Next.js release, preventing a
# rebuild or altered compiled page from being silently promoted.
for entry in \
  'bb6cd1cd72ec969b9415df863c2db1fe971652fee16b266841c47c9f7c3094f7 .next/BUILD_ID' \
  '6c76fc8c0c86985a27ab194ba1676d58da7c74ef48199cb56cbea36fcd8da2c5 .next/server/app/department/page.js' \
  '057a614175a1c7f32a1d271720c2c27f7fff3cab8172deeec2f844a8dca36df9 .next/server/app/founder/mail/page.js' \
  'f3107d8e88cc7fdb14d6ec7b91daafb2a1a77b45e785ed7f64125f53050e231f .next/server/app/page.js' \
  '2a0971697fc9ab22c72aa04d56c3cb1491de750e674cb2e6e660dbbe67019f6b .next/server/app/founder/commercial-pipeline/page.js';do
  digest="${entry%% *}";file="${entry#* }"
  [[ -f "$TARGET/$file" && ! -L "$TARGET/$file" ]] || fail FROZEN_BUILD_COMPONENT_NOT_REGULAR
  found="$(sha256sum "$TARGET/$file")"
  [[ "${found%% *}" == "$digest" ]] || fail FROZEN_BUILD_HASH_CHANGED
done
[[ ! -e "$DROP" && ! -L "$DROP" ]] || fail SEO_DROPIN_EXISTS
[[ "$(systemctl is-active "$UNIT")" == active ]] || fail PREVIOUS_FOUNDER_SERVICE_NOT_ACTIVE
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$PRIOR" ]] || fail ACTIVE_OWNER_RELEASE_CHANGED
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$PRIOR_A $PRIOR_B $PRIOR_C $PRIOR_D" ]] || fail UNEXPECTED_CONSOLE_DROPIN
[[ "$(systemctl show "$UNIT" -p ExecStart --value)" == *"-H 127.0.0.1 -p 3001"* ]] || fail PUBLIC_CONSOLE_BIND_DRIFT
[[ "$(systemctl is-active empire-search-intelligence-api.service)" == active ]] || fail SEARCH_INTELLIGENCE_UNHEALTHY
for p in "${OLD_ROUTES[@]}";do
  code="$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$p")"
  [[ "$code" == 200 ]] || fail PRIOR_FOUNDER_ROUTE_FAILED
done
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/department)" == 404 ]] || fail SEO_ROUTE_ALREADY_LIVE
status="$(curl -sS --max-time 12 -o /dev/null -w '%{http_code}' http://127.0.0.1:8771/v1/search/department/review)"
[[ "$status" == 200 ]] || fail PRIVATE_SEO_API_NOT_READY
curl -fsS --max-time 12 http://127.0.0.1:8771/v1/search/department/review |
  python3 -c 'import sys,json;d=json.load(sys.stdin);assert d["schema_version"]=="empire.search_growth.department_integration.v1";assert d["mode"]=="OBSERVE";assert d["status"]=="DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN";assert d["search_rankings_verified"] is False;assert d["realised_revenue_verified"] is False;assert d["execution_authority"]=="NONE"' || fail SEO_API_TRUTH_DRIFT
for p in /department /v1/search/department/review;do
  [[ "$(curl -sS -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36' --max-time 8 -o /dev/null -w '%{http_code}' "https://empire-ai.co.uk$p")" == 404 ]] || fail PUBLIC_SEO_EXPOSURE
done
echo 'PRIVATE_SEO_FOUNDER_PREFLIGHT_PASS: preserved frozen nine routes, SEO API read-only, public 404, rollback retained'
if [[ "$MODE" == --preflight ]];then
  echo 'PRIVATE_SEO_FOUNDER_STAGED_NOT_DEPLOYED'
  exit 0
fi
[[ "$(id -u)" == 0 ]] || fail ROOT_OPERATOR_REQUIRED

# Founder separately approves this exact private-only switch. Roll back
# only this 95 drop-in on a failed POST-release attestation.
umask 077
tmp=''
activated=0
cleanup(){
 local rc="$?"
 [[ -z "$tmp" ]] || rm -f "$tmp"
 if [[ "$activated" == 1 && "$rc" != 0 ]];then
   echo 'SEO_CONSOLE_RESTORING_PREVIOUS_FROZEN_FOUNDER_BUILD' >&2
   rm -f "$DROP"
   systemctl daemon-reload
   systemctl restart "$UNIT" || true
 fi
}
trap cleanup EXIT
trap 'exit 98' INT TERM
tmp="$(mktemp "$BASE/.96-private-seo-department.XXXXXX")"
printf '[Service]\nWorkingDirectory=%s\nEnvironment=EMPIRE_SEARCH_API_BASE_URL=http://127.0.0.1:8771\n' "$TARGET" > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$DROP"
tmp=''
activated=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for attempt in $(seq 1 30);do
 if [[ "$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:3001/department || true)" == 200 ]];then ready=1;break;fi
 sleep 1
done
[[ "$ready" == 1 ]] || fail PRIVATE_SEO_PAGE_START_FAILED
for p in "${OLD_ROUTES[@]}";do
  [[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$p")" == 200 ]] || fail PRIOR_FOUNDER_ROUTE_REGRESSION
done
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$TARGET" ]] || fail WRONG_WORKTREE
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$PRIOR_A $PRIOR_B $PRIOR_C $PRIOR_D $DROP" ]] || fail OWNER_UNIT_DROPINS_CHANGED
for p in /department /v1/search/department/review;do
  [[ "$(curl -sS -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36' --max-time 8 -o /dev/null -w '%{http_code}' "https://empire-ai.co.uk$p")" == 404 ]] || fail PUBLIC_SEO_RELEASE_EXPOSED
done
activated=0
echo 'PRIVATE_FOUNDER_SEO_DEPARTMENT_RELEASE_VERIFIED'
echo 'routes=10 private_only=yes founder_auth_app_verified=no seo_observe=yes site_published=no'
echo "rollback=rm -f $DROP && systemctl daemon-reload && systemctl restart $UNIT"
