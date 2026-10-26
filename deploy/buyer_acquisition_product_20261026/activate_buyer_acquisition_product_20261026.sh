#!/usr/bin/env bash
set -euo pipefail
LIVE=/home/ubuntu/empire_releases/property_birmingham_private_stage_20261022_v3/web
STAGED=/home/ubuntu/empire_worktrees/buyer_acquisition_product_20261026/web
SERVICE=empire-founder-console.service
BACKUP=$LIVE/.next_before_buyer_acquisition_product_20261026
SRCBACKUP=/home/ubuntu/empire_worktrees/buyer_acquisition_product_20261026/pre_release_source_backup
OLD_BUILD=0t60DLLfLyK-nB-8qymek
NEW_BUILD=neAbmPtarqZQ6Cd-Mk4ov
OLD_PAGE_SHA=1a6f6f518a59e36fb6d9e7f6c66535c5d9e07fc4b2c65b0e3fabfab1ef029a2c
REL=src/app/founder/commercial-pipeline
if [[ "${EUID}" -ne 0 ]]; then echo "HOLD: root owner required" >&2; exit 3; fi
if [[ -L "$LIVE" || -L "$STAGED" || -L "$LIVE/.next" || -L "$STAGED/.next" ]]; then echo "HOLD: unexpected release symlink" >&2; exit 4; fi
if [[ -e "$BACKUP" || -e "$SRCBACKUP" ]]; then echo "HOLD: backup destination already exists" >&2; exit 5; fi
if [[ "$(cat "$LIVE/.next/BUILD_ID")" != "$OLD_BUILD" || "$(cat "$STAGED/.next/BUILD_ID")" != "$NEW_BUILD" ]]; then
  echo "HOLD: protected original/staged build changed" >&2; exit 6
fi
if [[ "$(sha256sum "$LIVE/$REL/page.tsx" | cut -d' ' -f1)" != "$OLD_PAGE_SHA" ]]; then
  echo "HOLD: commercial page owner changed original" >&2; exit 7
fi
if ! cmp -s "$LIVE/src/app/department/evidence/page.tsx" "$STAGED/src/app/department/evidence/page.tsx"; then
  echo "HOLD: protected SEO owner source differs" >&2; exit 8
fi
# Abort on any other source modification. This update owns exactly these three paths.
diffs="$(diff -qr "$LIVE/src" "$STAGED/src" || true)"
expected_a="Only in $STAGED/$REL: buyer-acquisition-team-panel.tsx"
expected_b="Only in $STAGED/$REL: buyer-acquisition-team-table.tsx"
expected_c="Files $LIVE/$REL/page.tsx and $STAGED/$REL/page.tsx differ"
while IFS= read -r line; do
  [[ -z "$line" || "$line" == "$expected_a" || "$line" == "$expected_b" || "$line" == "$expected_c" ]] || {
    echo "HOLD: unrelated frontend source changed: $line" >&2; exit 9;
  }
done <<< "$diffs"
if ! systemctl is-active --quiet "$SERVICE"; then echo "HOLD: original console not active" >&2; exit 10; fi
if ! grep -q 'BuyerAcquisitionTeamPanel' "$STAGED/$REL/page.tsx"; then echo "HOLD: staged route not integrated" >&2; exit 11; fi
mkdir "$SRCBACKUP"
cp -p "$LIVE/$REL/page.tsx" "$SRCBACKUP/page.tsx"
changed=false
rollback() {
  if [[ "$changed" == true ]]; then
    echo "ACTIVATION_HELD_RESTORING_ORIGINAL_FOUNDER_CONSOLE" >&2
    systemctl stop "$SERVICE" || true
    if [[ -e "$LIVE/.next" ]]; then mv "$LIVE/.next" "$STAGED/.next_failed_activation"; fi
    if [[ -d "$BACKUP" ]]; then mv "$BACKUP" "$LIVE/.next"; fi
    cp -p "$SRCBACKUP/page.tsx" "$LIVE/$REL/page.tsx"
    rm -f "$LIVE/$REL/buyer-acquisition-team-panel.tsx" "$LIVE/$REL/buyer-acquisition-team-table.tsx"
    systemctl start "$SERVICE" || true
  fi
}
trap rollback EXIT
systemctl stop "$SERVICE"
changed=true
mv "$LIVE/.next" "$BACKUP"
mv "$STAGED/.next" "$LIVE/.next"
install -o ubuntu -g ubuntu -m 0644 "$STAGED/$REL/page.tsx" "$LIVE/$REL/page.tsx"
install -o ubuntu -g ubuntu -m 0644 "$STAGED/$REL/buyer-acquisition-team-panel.tsx" "$LIVE/$REL/buyer-acquisition-team-panel.tsx"
install -o ubuntu -g ubuntu -m 0644 "$STAGED/$REL/buyer-acquisition-team-table.tsx" "$LIVE/$REL/buyer-acquisition-team-table.tsx"
systemctl start "$SERVICE"
ok=false
for count in $(seq 1 16); do
  if curl -fsS --max-time 6 http://127.0.0.1:3001/founder/commercial-pipeline > /tmp/empire_buyer_product_activation.html; then
    ok=true; break
  fi
  sleep 1
done
if [[ "$ok" != true ]]; then echo "HOLD: founder commercial route unavailable" >&2; exit 12; fi
/usr/bin/python3 - <<'PY'
from pathlib import Path
import urllib.request
html=Path('/tmp/empire_buyer_product_activation.html').read_text()
for term in ('Buyer intelligence workbench','Search buyer companies',
             'Filter companies by industry','polyares.com','Commercial operations',
             'No outbound authority'):
    assert term in html, 'missing buyer product acceptance marker'
for path,expected in (('/founder', 'Empire Founder Console'),
                      ('/department/evidence','Indexed versions')):
    with urllib.request.urlopen('http://127.0.0.1:3001'+path,timeout=8) as res:
        assert res.status==200
        assert expected in res.read().decode('utf-8')
print('BUYER_TEAM_PRODUCT_ACCEPTED_ON_ORIGINAL_FOUNDER_CONSOLE')
print('FOUNDER_AND_SEO_ROUTES_PRESERVED')
PY
if [[ "$(cat "$LIVE/.next/BUILD_ID")" != "$NEW_BUILD" ]]; then
  echo "HOLD: staged build not active" >&2; exit 13
fi
changed=false
trap - EXIT
echo "FOUNDER_BUYER_ACQUISITION_PRODUCT_LIVE_VERIFIED"
echo "ROLLBACK_BACKUP=$BACKUP"
echo "NO_API_OR_DB_OR_OUTBOUND_CHANGE"
