#!/usr/bin/env bash
# Exact Founder private-console release from locally built parity candidate.
# This is NOT a public website deploy and it never operates the Gmail/CRM sender.
# Use --preflight before the explicit root-run --apply-approved-private-release.
set -euo pipefail

ROOT=/srv/empire_os
BASE="$ROOT/apps/search-command-centre"
TARGET=/home/ubuntu/empire_worktrees/empire_founder_mail_parity_candidate_20261018
UNIT=empire-founder-console.service
DROP_DIR="/etc/systemd/system/$UNIT.d"
DROP="$DROP_DIR/70-private-solar-review-release.conf"
LOG_NAME=empire-private-solar-review-20261018
MODES=(--preflight --apply-approved-private-release)
ROUTES=(/ /founder /founder/mail /founder/results /founder/solar /founder/youtube /founder/intent-review /revenue)

die() { printf 'HOLD_%s\n' "$1" >&2; exit 4; }
if [[ "${1:-}" != "${MODES[0]}" && "${1:-}" != "${MODES[1]}" || "${2:-}" != "" ]];then
  printf 'Usage: %s --preflight | --apply-approved-private-release\n' "$0" >&2
  exit 2
fi
MODE="$1"

check_hash() {
  local file="$1" expected="$2" actual
  [[ -f "$TARGET/$file" ]] || die MISSING_FROZEN_SOURCE
  actual="$(sha256sum "$TARGET/$file")"
  [[ "${actual%% *}" = "$expected" ]] || die RELEASE_SOURCE_HASH_DRIFT
}
check_hash src/app/founder/mail/page.tsx 3bd87e1c91d32dff74b9447081d27637ae4f1b4eec9f1c0afe6e502c71a3fe2b
check_hash src/app/founder/mail/workspace-solar-review.tsx afbc42e23e2dd01ee941573417c2e751ea44ce0eb8cdba68d9aeb911fef2bc31
check_hash src/app/founder/youtube/page.tsx 8616bd3e92413199d70a95840b272f71391564ae12eeda34b6ed3820aedeb899
check_hash src/app/founder/intent-review/page.tsx 2cf7e8b61a9b5685d4856a826273dc55f4151360f7262354d0cf095b59b5573d

[[ -f "$TARGET/.next/BUILD_ID" && -f "$TARGET/.next/server/app/founder/mail/page.js" ]] || die MISSING_COMPILED_RELEASE
[[ -L "$TARGET/node_modules" ]] || die UNEXPECTED_DEPENDENCY_PATH
[[ "$(readlink "$TARGET/node_modules")" == "$BASE/node_modules" ]] || die UNEXPECTED_DEPENDENCY_PATH
[[ -d "$BASE/src" ]] || die MISSING_CANONICAL_FRONTEND
drift="$(rsync -rcn --itemize-changes --exclude='.next*' "$BASE/src/" "$TARGET/src/")"
[[ -z "$drift" ]] || die UNCOMMITTED_FRONTEND_SOURCE_CHANGED_SINCE_BUILD
[[ ! -e "$DROP" && ! -L "$DROP" ]] || die EXISTING_RELEASE_OVERRIDE
[[ "$(systemctl show "$UNIT" --property=FragmentPath --value)" == "/etc/systemd/system/$UNIT" ]] || die WRONG_SERVICE_UNIT
[[ "$(systemctl show "$UNIT" --property=WorkingDirectory --value)" == "$BASE" ]] || die SERVICE_ALREADY_OVERWRITTEN
[[ -z "$(systemctl show "$UNIT" --property=DropInPaths --value)" ]] || die EXISTING_UNIT_DROPIN
[[ "$(systemctl is-active "$UNIT")" == active ]] || die EXISTING_FOUNDER_CONSOLE_NOT_ACTIVE
[[ "$(systemctl is-active empire-founder-dashboard-api.service)" == active ]] || die FOUNDER_API_NOT_ACTIVE
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || die CRM_PILOT_NOT_ACTIVE
[[ "$(systemctl is-active empire-buyer-acquisition-team.timer)" == active ]] || die EXISTING_GMAIL_MONITOR_NOT_ACTIVE

for route in "${ROUTES[@]}";do
  [[ "$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die CURRENT_LIVE_ROUTE_NOT_200
done
public_code="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" || die PUBLIC_EXPOSURE_PROBE_UNAVAILABLE
[[ "$public_code" == 404 ]] || die PUBLIC_FOUNDER_ROUTE_NOT_PRIVATE
printf '%s\n' 'PRECHECK_PASS: exact frozen build, no source drift, 8 existing routes, public 404, no competing override'

if [[ "$MODE" == --preflight ]];then
  printf '%s\n' 'PREVIEW_READY_NOT_DEPLOYED'
  exit 0
fi
[[ "$(id -u)" == 0 ]] || die ROOT_OPERATOR_REQUIRED
# All root changes are restricted to a new exact systemd drop-in and this
# one existing, loopback-only Next.js service. Never touch CRM/Gmail units.
umask 077
mkdir -p "$DROP_DIR"
TMP="$(mktemp "$DROP_DIR/.70-private-solar-review.XXXXXX")"
HTML="$(mktemp /tmp/empire-private-solar-review-html.XXXXXX)"
changed=0
rollback() {
  local result="$?"
  rm -f "$TMP" "$HTML"
  if [[ "$changed" == 1 && "$result" -ne 0 ]];then
    printf '%s\n' 'RELEASE_SMOKE_FAILED_ROLLING_BACK_PREVIOUS_FOUNDER_CONSOLE' >&2
    rm -f "$DROP"
    systemctl daemon-reload
    systemctl restart "$UNIT" || true
  fi
}
trap rollback EXIT
printf '[Service]\nWorkingDirectory=%s\n' "$TARGET" > "$TMP"
chmod 0644 "$TMP"
mv "$TMP" "$DROP"
changed=1
systemctl daemon-reload
systemctl restart "$UNIT"
ready=0
for n in $(seq 1 20);do
  if curl -fsS --max-time 5 http://127.0.0.1:3001/founder/mail -o "$HTML" 2>/dev/null;then ready=1;break;fi
  sleep 1
done
[[ "$ready" == 1 ]] || die NEW_FOUNDER_CONSOLE_NOT_READY
for marker in 'Commercial outreach tracking' 'GB NRG' '100% Renewables' 'CRM cases created' 'no auto-send';do
  grep -Fq "$marker" "$HTML" || die NEW_MAIL_PANEL_MISSING
done
for route in "${ROUTES[@]}";do
  [[ "$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "http://127.0.0.1:3001$route")" == 200 ]] || die EXISTING_ROUTE_REGRESSION
done
[[ "$(systemctl show "$UNIT" --property=WorkingDirectory --value)" == "$TARGET" ]] || die UNEXPECTED_RELEASE_DIRECTORY
[[ "$(systemctl is-active "$UNIT")" == active ]] || die FOUNDER_SERVICE_INACTIVE
[[ "$(systemctl is-active empire-revenue-crm-pilot.service)" == active ]] || die CRM_HEALTH_REGRESSION
[[ "$(systemctl is-active empire-buyer-acquisition-team.timer)" == active ]] || die GMAIL_MONITOR_REGRESSION
public_code="$(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' https://empire-ai.co.uk/founder/mail)" || die PUBLIC_ROUTE_VERIFY_UNAVAILABLE
[[ "$public_code" == 404 ]] || die UNEXPECTED_PUBLIC_ACCESS
changed=0
echo "PRIVATE_FOUNDER_MAIL_RELEASE_VERIFIED"
echo "routes=8 founder_mail_panel=visible crm_mutations=none emails_sent=none"
echo "release=$TARGET"
echo "rollback=rm -f $DROP && systemctl daemon-reload && systemctl restart $UNIT"
