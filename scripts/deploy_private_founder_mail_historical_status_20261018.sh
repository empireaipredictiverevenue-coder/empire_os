#!/usr/bin/env bash
# One-time private Founder Mail evidence-status UI release. No DB DDL or
# Gmail/CRM/payment modifications. Retain prior 70+80 release for rollback.
set -euo pipefail
UNIT=empire-founder-console.service
BASE=/etc/systemd/system/$UNIT.d
PRIOR=/home/ubuntu/empire_worktrees/empire_founder_mail_reply_triage_candidate_20261018
TARGET=/home/ubuntu/empire_worktrees/empire_founder_mail_historical_evidence_candidate_20261018
CANONICAL=/srv/empire_os/apps/search-command-centre
PRIOR_A="$BASE/70-private-solar-review-release.conf"
PRIOR_B="$BASE/80-private-reply-triage-release.conf"
DROP="$BASE/90-private-historical-evidence-release.conf"
ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /revenue)

die(){ printf 'HOLD_%s\n' "$1" >&2;exit 4; }
[[ "${1:-}" == --preflight || "${1:-}" == --apply-approved-private-release ]] ||
  { echo 'Usage: --preflight | --apply-approved-private-release' >&2;exit 2; }
[[ "${2:-}" == "" ]] || { echo 'Usage: exactly one argument' >&2;exit 2; }
MODE="$1"

require_sha(){
  local path="$1" digest="$2" found
  [[ -f "$path" && ! -L "$path" ]] || die RELEASE_COMPONENT_UNEXPECTED
  found="$(sha256sum "$path")"
  [[ "${found%% *}" == "$digest" ]] || die RELEASE_HASH_CHANGED
}
require_sha "$CANONICAL/src/app/founder/mail/workspace-solar-review.tsx" 3fb1ecba105dc5c8a966295d39681d9e45ede4c373edf548f0d3a59c436124fd
require_sha "$TARGET/src/app/founder/mail/workspace-solar-review.tsx" 3fb1ecba105dc5c8a966295d39681d9e45ede4c373edf548f0d3a59c436124fd
require_sha "$PRIOR/src/app/founder/mail/workspace-solar-review.tsx" bd55dc9feb32872ce2f30be51991ce376cbdc76f93da28f3074b2cde624855c4
[[ -f "$TARGET/.next/BUILD_ID" && -f "$TARGET/.next/server/app/founder/mail/page.js" ]] || die RELEASE_BUILD_NOT_PRESENT
[[ -L "$TARGET/node_modules" && "$(readlink "$TARGET/node_modules")" == "$CANONICAL/node_modules" ]] || die RELEASE_DEPENDENCY_DRIFT
unchanged="$(rsync -rcn --itemize-changes --exclude='workspace-solar-review.tsx' "$PRIOR/src/" "$TARGET/src/")"
[[ -z "$unchanged" ]] || die OTHER_FOUNDER_FEATURE_DRIFT
[[ ! -e "$DROP" && ! -L "$DROP" ]] || die RELEASE_ALREADY_EXISTS
[[ "$(systemctl show "$UNIT" -p ActiveState --value)" == active ]] || die PRIOR_CONSOLE_NOT_ACTIVE
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$PRIOR" ]] || die UNEXPECTED_ACTIVE_CONSOLE
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$PRIOR_A $PRIOR_B" ]] || die UNEXPECTED_SYSTEMD_OVERRIDES
for unit in empire-founder-dashboard-api.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer;do
  [[ "$(systemctl is-active "$unit")" == active ]] || die EXISTING_SERVICE_NOT_HEALTHY
done
for route in "${ROUTES[@]}";do
  [[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die EXISTING_ROUTE_UNAVAILABLE
done
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:8766/v1/founder-mailbox/workspace-solar-historical-evidence-status)" == 200 ]] || die PRIVATE_EVIDENCE_SOURCE_UNAVAILABLE
[[ "$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PUBLIC_ROUTE_EXPOSURE
echo 'PRECHECK_PASS: frozen Founder build, all 8 routes, private evidence API, public 404, previous rollback intact'
if [[ "$MODE" == --preflight ]];then echo 'PRIVATE_EVIDENCE_UI_STAGED_NOT_DEPLOYED';exit 0;fi
[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED

tmp=''
html=''
activated=0
cleanup(){
 local rc="$?"
 [[ -z "$tmp" ]] || rm -f "$tmp"
 [[ -z "$html" ]] || rm -f "$html"
 if [[ "$activated" == 1 && "$rc" != 0 ]];then
   echo 'HISTORICAL_EVIDENCE_UI_ROLLBACK_TO_PRIOR_CONSOLE' >&2
   rm -f "$DROP"
   systemctl daemon-reload
   systemctl restart "$UNIT" || true
 fi
}
trap cleanup EXIT
trap 'exit 98' INT TERM
umask 077
tmp="$(mktemp "$BASE/.90-private-historical-evidence.XXXXXX")"
html="$(mktemp /tmp/empire-foundermail-historical-status.XXXXXX)"
printf '[Service]\nWorkingDirectory=%s\n' "$TARGET" > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$DROP"
tmp=''
activated=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for attempt in $(seq 1 20);do
 if curl -fsS --max-time 5 http://127.0.0.1:3001/founder/mail -o "$html" 2>/dev/null;then ready=1;break;fi
 sleep 1
done
[[ "$ready" == 1 ]] || die NEW_CONSOLE_HEALTH_FAILED
python3 - "$html" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import sys
class P(HTMLParser):
 def __init__(self):super().__init__();self.values=[]
 def handle_data(self,t):self.values.append(t)
p=P();p.feed(Path(sys.argv[1]).read_text())
rendered=' '.join(' '.join(p.values).split()).lower()
for marker in (
 'Commercial outreach tracking','Original Gmail sends',
 '6 original sends preserved','historical receipts verified in EmpireDB',
 'GB NRG','100% Renewables','CRM cases created'
):
 if marker.lower() not in rendered:
  raise SystemExit('HOLD_HISTORICAL_UI_EXPECTED_MARKER_MISSING')
PY
for route in "${ROUTES[@]}";do
 [[ "$(curl -sS --max-time 9 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die ROUTE_REGRESSION
done
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$TARGET" ]] || die WRONG_RELEASE_DIRECTORY
for unit in empire-founder-dashboard-api.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer;do
 [[ "$(systemctl is-active "$unit")" == active ]] || die SUPPORTING_SERVICE_REGRESSION
done
[[ "$(curl -sS --max-time 9 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PUBLIC_FOUNDER_ROUTE_EXPOSED
activated=0
echo 'FOUNDER_HISTORICAL_EVIDENCE_UI_RELEASE_VERIFIED'
echo 'routes=8 historical_evidence=read_only crm_writes=no email_sent=no'
echo "rollback=rm -f $DROP && systemctl daemon-reload && systemctl restart $UNIT"
