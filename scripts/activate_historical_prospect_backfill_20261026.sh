#!/usr/bin/env bash
# Controlled existing-service activation of the 2026-10-26 33K v2 prospect backfill.
# Requires explicit root invocation by the authorised EmpireOS operator.
# Does not introduce a second unit, touch payment/outbound or alter DB thresholds.
set -euo pipefail

ROOT=/srv/empire_os
DROPIN_DIR=/etc/systemd/system/empire-qualification.service.d
DROPIN="$DROPIN_DIR/35-empire-qualification-historical-backfill.conf"
SOURCE="$ROOT/deploy/systemd/35-empire-qualification-historical-backfill.conf"
CURSOR="$ROOT/runtime/qualification/historical_backfill_cursor.json"

if [[ "$EUID" -ne 0 ]]; then
  echo "Requires owner-authorised root systemd execution" >&2
  exit 3
fi
cd "$ROOT"

# Refuse to install if the reviewed live implementation or drop-in has drifted.
printf '%s\n' \
  '7b7f1e9fbdd6e6075b853bcfd72a8034ac087baf65cec1ac32abae4f3b4b83fb  empire_os/qualification_data_repository.py' \
  '2e17b8ede27e60c39367f2b9cc5374450eae17794b3de233d33abcea92799c77  empire_os/qualification_worker_v2.py' \
  '2e0d251329ada9c4d04d032a885ceca9b53c37b02b9f806067cfdcf2f7243da0  empire_os/qualification_historical_backfill_cursor.py' \
  'cb1cb0fe40c45ca34e414336b59b2743af0bc9cbc76d7558a39bc9933e6a70c1  scripts/run_qualification_cycle.py' \
  '2336e48e37a915c513bd03d5b7d663781386b9299b5db40d4c9a675781432717  deploy/systemd/35-empire-qualification-historical-backfill.conf' |
  sha256sum --check --status || {
    echo "HOLD: reviewed qualification source changed since preflight" >&2
    exit 4
  }

if systemctl is-active --quiet empire-qualification.service; then
  echo "HOLD: existing qualification cycle is already running" >&2
  exit 5
fi

read_progress() {
  "$ROOT/.venv/bin/python" -B -c '
import sys
sys.path.insert(0, "/srv/empire_os")
from empire_os.qualification_historical_backfill_cursor import load_cursor
print(load_cursor())
'
}
BEFORE_OFFSET="$(read_progress)"
installed_now=0
if [[ -e "$DROPIN" ]]; then
  cmp -s "$SOURCE" "$DROPIN" || {
    echo "HOLD: an existing historical backfill override differs" >&2
    exit 6
  }
else
  install -d -m 0755 "$DROPIN_DIR"
  install -m 0644 "$SOURCE" "$DROPIN"
  installed_now=1
fi

rollback_if_unverified() {
  if [[ "$installed_now" -eq 1 ]] && [[ -f "$DROPIN" ]]; then
    rm -f "$DROPIN"
    systemctl daemon-reload
    echo "Restored original qualification ExecStart after incomplete pilot" >&2
  fi
}
trap 'code=$?; if [[ "$code" -ne 0 ]]; then rollback_if_unverified; fi' EXIT

systemctl daemon-reload
if ! systemctl start empire-qualification.service; then
  echo "HOLD: first bounded backfill service failed" >&2
  exit 7
fi

if [[ ! -f "$CURSOR" ]]; then
  echo "HOLD: service completed but backfill cursor did not appear" >&2
  exit 8
fi

NEXT_OFFSET="$(read_progress)"
if [[ ! "$NEXT_OFFSET" =~ ^[0-9]+$ ]] || [[ "$NEXT_OFFSET" -le "$BEFORE_OFFSET" ]]; then
  echo "HOLD: no positive backfill cursor progress attested" >&2
  exit 9
fi

echo "BACKFILL_FIRST_CYCLE_SUCCESS"
echo "NEXT_OLDEST_FIRST_OFFSET=$NEXT_OFFSET"
echo "BATCH_CAP=10"
echo "SCHEDULE=EXISTING_QUALIFICATION_TIMER"
echo "BUYER_ACTIVATION=false OUTBOUND=false PAYMENT=false"
