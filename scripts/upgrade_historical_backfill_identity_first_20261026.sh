#!/usr/bin/env bash
# One scoped owner-authorised upgrade of the EXISTING EmpireOS qualification service.
# Adds five identity-linked, previously unscored prospects per 15-minute cycle
# alongside the existing ten chronological prospects. No new unit, DB or sender.
set -euo pipefail
ROOT=/srv/empire_os
SERVICE=empire-qualification.service
OLD=/etc/systemd/system/empire-qualification.service.d/35-empire-qualification-historical-backfill.conf
NEW=/etc/systemd/system/empire-qualification.service.d/36-empire-qualification-historical-identity-first.conf
SOURCE=$ROOT/deploy/systemd/36-empire-qualification-historical-identity-first.conf
GENERAL=$ROOT/runtime/qualification/historical_backfill_cursor.json
LINKED=$ROOT/runtime/qualification/historical_identity_linked_cursor.json

if [[ "$EUID" -ne 0 ]]; then
  echo "HOLD: authorised root systemd operator required" >&2
  exit 3
fi
cd "$ROOT"
printf '%s\n' \
  'd8733b1fe053ccea73bb838f413bce23737831dc646c49b34d5122bb01061be7  empire_os/qualification_data_repository.py' \
  '8f748989d5c1f88ac1dbcc345e471f1ec3398d3e83bf18e2da6089bc6acdaf54  empire_os/qualification_worker_v2.py' \
  '66fe3652fd3810c5b5e9873edecf57796f57b7711cdefbb914545d5b7c119e57  scripts/run_qualification_cycle.py' \
  '5613a073d97bfa06befcf75e56880c7892192f2990b4b50fa6b119825bd6fc8b  deploy/systemd/36-empire-qualification-historical-identity-first.conf' |
  sha256sum --check --status || {
    echo "HOLD: staged code differs from verified version" >&2
    exit 4
  }
if [[ ! -f "$OLD" ]] || ! grep -q -- '--historical-backfill-limit 10 ' "$OLD"; then
  echo "HOLD: previous ten-prospect pilot is not installed as expected" >&2
  exit 5
fi
if systemctl is-active --quiet "$SERVICE"; then
  echo "HOLD: qualification owner service is running" >&2
  exit 6
fi
cursor() {
  "$ROOT/.venv/bin/python" -B -c '
import sys
from pathlib import Path
sys.path.insert(0, "/srv/empire_os")
from empire_os.qualification_historical_backfill_cursor import load_cursor
print(load_cursor(Path(sys.argv[1])))
' "$1"
}
BEFORE_GENERAL="$(cursor "$GENERAL")"
BEFORE_LINKED="$(cursor "$LINKED")"
created=0
if [[ -e "$NEW" ]]; then
  cmp -s "$SOURCE" "$NEW" || {
    echo "HOLD: existing priority override differs" >&2
    exit 7
  }
else
  install -m 0644 "$SOURCE" "$NEW"
  created=1
fi
rollback() {
  if [[ "$created" -eq 1 ]] && [[ -f "$NEW" ]]; then
    rm -f "$NEW"
    systemctl daemon-reload
    echo "Rolled back priority override to original 10-item sweep" >&2
  fi
}
trap 'status=$?; if [[ "$status" -ne 0 ]]; then rollback; fi' EXIT
systemctl daemon-reload
if ! systemctl start "$SERVICE"; then
  echo "HOLD: controlled combined batch failed to start" >&2
  exit 8
fi
AFTER_GENERAL="$(cursor "$GENERAL")"
AFTER_LINKED="$(cursor "$LINKED")"
if [[ ! "$AFTER_GENERAL" =~ ^[0-9]+$ ]] || [[ ! "$AFTER_LINKED" =~ ^[0-9]+$ ]] ||
   [[ "$AFTER_GENERAL" -le "$BEFORE_GENERAL" ]] ||
   [[ "$AFTER_LINKED" -le "$BEFORE_LINKED" ]]; then
  echo "HOLD: cursors did not both advance" >&2
  exit 9
fi
echo "TAM_BACKFILL_IDENTITY_PRIORITISATION_ACTIVE"
echo "CHRONOLOGICAL_CURSOR=$AFTER_GENERAL"
echo "IDENTITY_LINKED_CURSOR=$AFTER_LINKED"
echo "PER_CYCLE_CAP=10_chronological_plus_5_already_identity_linked"
echo "SERVICE=existing_empire_qualification TIMER=existing_15_minute"
echo "BUYER_ACTIVATION=false OUTBOUND=false PAYMENT=false"
