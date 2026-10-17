#!/usr/bin/env bash
# Recover the EXISTING founder buyer Gmail readonly token after invalid_grant.
# No new Google project, service, timer, send scope or second mailbox connection.
# IMPORTANT: --apply must be run interactively by the mailbox owner with their
# own browser consent. The old private token is restored on any failed attempt.
set -euo pipefail
umask 077
ROOT=/srv/empire_os
TOKEN="$ROOT/runtime/secrets/buyer-gmail-readonly-token.json"
CLIENT="$ROOT/runtime/secrets/buyer-gmail-readonly-client.json"
BACKUP="$ROOT/runtime/secrets/.buyer-gmail-readonly-token.pre-renew-20261017.json"
AUTHORISER="$ROOT/scripts/authorize_buyer_gmail_readonly.py"
AUTHORISER_SHA=567128721a193d2d6f3e27ea39e2c1d21968360447672b6e4b8a30af9132531a
PY="$ROOT/.venv/bin/python"
CYCLE_LOCK="$ROOT/runtime/buyer_network_intelligence/gmail_cycle.lock"

if [[ "${1:-}" != "--preflight" && "${1:-}" != "--apply" || "$#" -ne 1 ]];then
  echo 'Usage: bash scripts/renew_buyer_gmail_readonly_20261017.sh --preflight | --apply' >&2
  exit 2
fi
[[ ! -L "$TOKEN" && -f "$TOKEN" && ! -L "$CLIENT" && -f "$CLIENT" ]] || { echo 'PRIVATE_OAUTH_FILES_UNAVAILABLE' >&2; exit 3; }
[[ "$(stat -c %a "$TOKEN")" == 600 && "$(stat -c %a "$CLIENT")" == 600 ]] || { echo 'PRIVATE_OAUTH_PERMISSIONS_UNSAFE' >&2; exit 3; }
[[ "$(stat -c %u "$TOKEN")" == "$(id -u)" ]] || { echo 'RUN_AS_ORIGINAL_TOKEN_OWNER' >&2; exit 3; }
[[ ! -e "$BACKUP" && ! -L "$BACKUP" ]] || { echo 'PREVIOUS_RECOVERY_PRESENT_REVIEW_MANUALLY' >&2; exit 3; }
printf '%s  %s\n' "$AUTHORISER_SHA" "$AUTHORISER" | sha256sum -c - >/dev/null || {
  echo 'AUTHORISER_SOURCE_CHANGED_REVIEW_BEFORE_REAUTH' >&2; exit 3;
}
"$PY" - <<'PY'
from pathlib import Path
import json
from google.oauth2.credentials import Credentials
base=Path('/srv/empire_os/runtime/secrets')
token=json.loads((base/'buyer-gmail-readonly-token.json').read_text())
client=json.loads((base/'buyer-gmail-readonly-client.json').read_text())['installed']
readonly=['https://www.googleapis.com/auth/gmail.readonly']
assert token['scopes']==readonly,'UNEXPECTED_OAUTH_SCOPE'
assert token['client_id']==client['client_id'],'OAUTH_CLIENT_ID_MISMATCH'
assert token['client_secret']==client['client_secret'],'OAUTH_CLIENT_SECRET_MISMATCH'
assert token['token_uri']==client['token_uri'],'OAUTH_TOKEN_URI_MISMATCH'
assert isinstance(token.get('account'),(str,type(None))),'INVALID_TOKEN_ACCOUNT_METADATA'
assert token.get('refresh_token'),'NO_REFRESH_TOKEN'
print('EXISTING_READONLY_OAUTH_IDENTITY_AND_SCOPE_VERIFIED')
PY
if [[ "$1" == "--preflight" ]];then
  echo 'READY_REQUIRES_FOUNDERS_GOOGLE_BROWSER_CONSENT; NO_TOKEN_CHANGED; NO_EMAIL_SENT'
  exit 0
fi

# The existing Gmail poller uses this exact lock. A renewal must be isolated
# from the five-thread observation cycle; no SMTP/send permissions are possible.
exec 8>>"$CYCLE_LOCK"
flock -n 8 || { echo 'GMAIL_CYCLE_BUSY_WAIT_AND_RETRY' >&2; exit 4; }
RENEWED=0
restore_on_exit() {
  local result=$?
  trap - EXIT
  if [[ "$RENEWED" != 1 ]];then
    if [[ -f "$BACKUP" ]];then
      if [[ -f "$TOKEN" && ! -L "$TOKEN" ]];then rm -- "$TOKEN"; fi
      mv -- "$BACKUP" "$TOKEN"
      echo 'AUTHORIZATION_INCOMPLETE_OLD_TOKEN_RESTORED; NO_EMAIL_SENT' >&2
    fi
  else
    rm -- "$BACKUP"
  fi
  exit "$result"
}
trap restore_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mv -- "$TOKEN" "$BACKUP"
echo 'GOOGLE_BROWSER_CONSENT_REQUIRED; READONLY_SCOPE_ONLY; PORT_38765'
"$PY" "$AUTHORISER"
# Verify ownership of the newly authorised Gmail account rather than silently
# binding the CRM to a different Google account selected in the browser.
"$PY" - <<'PY'
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
path=Path('/srv/empire_os/runtime/secrets/buyer-gmail-readonly-token.json')
scope='https://www.googleapis.com/auth/gmail.readonly'
creds=Credentials.from_authorized_user_file(str(path),[scope])
if not creds.valid or set(creds.scopes or [])!={scope}:
    raise SystemExit('NEW_READONLY_OAUTH_CREDENTIALS_NOT_VERIFIED')
profile=build('gmail','v1',credentials=creds,cache_discovery=False).users().getProfile(userId='me').execute()
if str(profile.get('emailAddress') or '').strip().lower()!='flavag83@gmail.com':
    raise SystemExit('GOOGLE_ACCOUNT_MISMATCH_OLD_TOKEN_RESTORED')
if path.stat().st_mode & 0o077:
    raise SystemExit('NEW_TOKEN_NOT_PRIVATE')
print('EXACT_FOUNDER_BUYER_GMAIL_READONLY_ACCOUNT_VERIFIED')
PY
RENEWED=1
echo 'BUYER_GMAIL_READONLY_REAUTHORIZED; NO_SEND_SCOPE; NO_EMAIL_SENT'
