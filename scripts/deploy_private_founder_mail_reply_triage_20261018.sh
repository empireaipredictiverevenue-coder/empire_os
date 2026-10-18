#!/usr/bin/env bash
# One-time Founder Mail reply-triage release. Uses PREVIOUS live private
# console as automatic rollback; no public, DB, Gmail or CRM mutations.
set -euo pipefail

LIVE_PREVIOUS=/home/ubuntu/empire_worktrees/empire_founder_mail_parity_candidate_20261018
NEW_RELEASE=/home/ubuntu/empire_worktrees/empire_founder_mail_reply_triage_candidate_20261018
UNIT=empire-founder-console.service
BASE=/etc/systemd/system/empire-founder-console.service.d
PREVIOUS_DROP="$BASE/70-private-solar-review-release.conf"
DROP="$BASE/80-private-reply-triage-release.conf"
CANONICAL=/srv/empire_os/apps/search-command-centre
ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /revenue)

die() { printf 'HOLD_%s\n' "$1" >&2; exit 4; }
[[ "${1:-}" == --preflight || "${1:-}" == --apply-approved-private-release ]] ||
  { echo 'Usage: deploy_private_founder_mail_reply_triage_20261018.sh --preflight | --apply-approved-private-release' >&2;exit 2; }
[[ "${2:-}" == "" ]] || { echo 'Usage: exactly one mode argument required' >&2;exit 2; }
MODE="$1"

hash_equals() {
  local path="$1" value="$2" actual
  [[ -f "$path" && ! -L "$path" ]] || die MISSING_SOURCE_OR_UNEXPECTED_SYMLINK
  actual="$(sha256sum "$path")"
  [[ "${actual%% *}" == "$value" ]] || die EXACT_SOURCE_DRIFT
}
hash_equals "$NEW_RELEASE/src/app/founder/mail/workspace-solar-review.tsx" bd55dc9feb32872ce2f30be51991ce376cbdc76f93da28f3074b2cde624855c4
hash_equals "$CANONICAL/src/app/founder/mail/workspace-solar-review.tsx" bd55dc9feb32872ce2f30be51991ce376cbdc76f93da28f3074b2cde624855c4
hash_equals "$NEW_RELEASE/src/app/founder/mail/page.tsx" 3bd87e1c91d32dff74b9447081d27637ae4f1b4eec9f1c0afe6e502c71a3fe2b
hash_equals "$NEW_RELEASE/src/app/founder/youtube/page.tsx" 8616bd3e92413199d70a95840b272f71391564ae12eeda34b6ed3820aedeb899
hash_equals "$NEW_RELEASE/src/app/founder/intent-review/page.tsx" 2cf7e8b61a9b5685d4856a826273dc55f4151360f7262354d0cf095b59b5573d
[[ -f "$NEW_RELEASE/.next/BUILD_ID" && -f "$NEW_RELEASE/.next/server/app/founder/mail/page.js" ]] || die BUILD_NOT_FROZEN
[[ -L "$NEW_RELEASE/node_modules" &&
  "$(readlink "$NEW_RELEASE/node_modules")" == "$CANONICAL/node_modules" ]] || die UNEXPECTED_BUILD_DEPENDENCIES
other_changes="$(rsync -rcn --itemize-changes --exclude='workspace-solar-review.tsx' "$LIVE_PREVIOUS/src/" "$NEW_RELEASE/src/")"
[[ -z "$other_changes" ]] || die OTHER_AGENTS_SOURCE_DIFFERS
[[ ! -e "$DROP" && ! -L "$DROP" ]] || die ALREADY_RELEASED_OR_CONFLICTING_OVERRIDE
# Private drop-in directory is root-readable only; check the active
# drop-in through systemd instead of testing the file as unprivileged user.
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$LIVE_PREVIOUS" ]] || die WRONG_LIVE_RELEASE
[[ "$(systemctl show "$UNIT" -p DropInPaths --value)" == "$PREVIOUS_DROP" ]] || die UNEXPECTED_COMPETING_OVERRIDES
[[ "$(systemctl is-active "$UNIT")" == active ]] || die LIVE_CONSOLE_DOWN
for check in empire-founder-dashboard-api.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer; do
  [[ "$(systemctl is-active "$check")" == active ]] || die RELATED_SERVICE_UNHEALTHY
done
for route in "${ROUTES[@]}";do
  [[ "$(curl -sS --max-time 9 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die PREVIOUS_ROUTE_UNAVAILABLE
done
[[ "$(curl -sS --max-time 9 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die PUBLIC_EXPOSURE_CONFLICT
echo 'PRECHECK_PASS: exact incremental source, 8 current routes, unchanged CRM/Gmail, public 404, rollback intact'

if [[ "$MODE" == --preflight ]];then echo 'TRIAGE_RELEASE_PREPARED_NOT_LIVE';exit 0;fi
[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED

tmp=''
html=''
changed=0
cleanup() {
  local rc="$?"
  [[ -z "$tmp" ]] || rm -f "$tmp"
  [[ -z "$html" ]] || rm -f "$html"
  if [[ "$changed" == 1 && "$rc" != 0 ]]; then
    echo 'TRIAGE_RELEASE_FAILED_REVERTING_TO_VERIFIED_PRIOR_CONSOLE' >&2
    rm -f "$DROP"
    systemctl daemon-reload
    systemctl restart "$UNIT" || true
  fi
}
trap cleanup EXIT
trap 'exit 98' TERM INT

umask 077
tmp="$(mktemp "$BASE/.80-private-reply-triage.XXXXXX")"
html="$(mktemp /tmp/empire-founder-mail-triage-smoke.XXXXXX)"
printf '[Service]\nWorkingDirectory=%s\n' "$NEW_RELEASE" > "$tmp"
chmod 0644 "$tmp"
mv "$tmp" "$DROP"
tmp=''
changed=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for n in $(seq 1 20);do
  if curl -fsS --max-time 5 http://127.0.0.1:3001/founder/mail -o "$html" 2>/dev/null;then ready=1;break;fi
  sleep 1
done
[[ "$ready" == 1 ]] || die NEW_CONSOLE_STARTUP_FAILED
for marker in 'Commercial outreach tracking' 'GB NRG' '100% Renewables' 'CRM cases created' 'no auto-send'; do
  grep -Fq "$marker" "$html" || die TRIAGE_MAIL_PANEL_MISSING
done
for route in "${ROUTES[@]}";do
  [[ "$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die NEW_CONSOLE_ROUTE_REGRESSION
done
[[ "$(systemctl show "$UNIT" -p WorkingDirectory --value)" == "$NEW_RELEASE" ]] || die WRONG_DEPLOYED_RELEASE
[[ "$(systemctl is-active "$UNIT")" == active ]] || die FOUNDER_CONSOLE_NOT_ACTIVE
for check in empire-founder-dashboard-api.service empire-revenue-crm-pilot.service empire-buyer-acquisition-team.timer; do
  [[ "$(systemctl is-active "$check")" == active ]] || die OTHER_SERVICE_REGRESSION
done
[[ "$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" == 404 ]] || die UNEXPECTED_PUBLIC_EXPOSURE
changed=0
echo 'FOUNDER_REPLY_TRIAGE_RELEASE_VERIFIED'
echo 'routes=8 panel=live crm_writes=no email_sent=no new_scheduled_services=no'
echo "rollback=rm -f $DROP && systemctl daemon-reload && systemctl restart $UNIT"
