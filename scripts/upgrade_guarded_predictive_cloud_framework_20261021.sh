#!/usr/bin/env bash
# Controlled successor to existing root-owned Cloud guard f4fe409c56fa.
# Only the two-minute OBSERVE materializer is switched. Private Founder API
# service, payments, tenants, original checkout and other agents are untouched.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: upgrade --check|--apply-owner-approved-observe EXACT_FULL_COMMIT_SHA' >&2
  exit 2
fi
MODE="$1"
SHA="$2"
SHORT="$(printf '%s' "$SHA" | cut -c1-12)"
SOURCE="/home/ubuntu/empire_releases/predictive_observe_$SHORT"
OWNER='/home/ubuntu/empire_agents/predictive_decision_control_20261018'
TARGET="/opt/empire/predictive_cloud_guard_$SHORT"
OLD='/opt/empire/predictive_cloud_guard_f4fe409c56fa'
UNIT='/etc/systemd/system/empire-predictive-cloud-materializer.service'
DROPIN='/etc/systemd/system/empire-predictive-cloud-materializer.service.d/60-verified-source-admission.conf'
SERVICE='empire-predictive-cloud-materializer.service'
TIMER='empire-predictive-cloud-materializer.timer'
MANIFEST="$SOURCE/metadata/critical_source_checksums.sha256"
BEFORE_UNIT_SHA='58a1e516d5c5f46b9638cb16e1e87ea56f7535610b16d1f0cf64691fb74f502f'
BEFORE_DROPIN_SHA='47634d5c8141bbc393d08d025d1332e3f9d04f084155723d02030505d8c5ab78'
BEFORE_OLD_WRITER_SHA='ff4cb8613957e6e8f98a1012b51f6f7e37d88acfb2ed4df5a0e322c9327eeee2'
BEFORE_OLD_RUNNER_SHA='8e165e3e9efe610a73b36b6608d8449f181538a01692f3563f113839a48af4f8'
sha () { sha256sum "$1" | cut -d' ' -f1; }
preflight () {
  [[ "$SHA" =~ ^[0-9a-f]{40}$ ]]
  [[ -f "$MANIFEST" && ! -L "$SOURCE" && ! -e "$TARGET" && ! -L "$TARGET" ]]
  grep -qx "SOURCE_COMMIT=$SHA" "$SOURCE/metadata/source.txt"
  (cd "$SOURCE" && sha256sum --status -c "$MANIFEST")
  [[ "$(sha "$UNIT")" == "$BEFORE_UNIT_SHA" ]]
  [[ "$(sha "$DROPIN")" == "$BEFORE_DROPIN_SHA" ]]
  [[ "$(sha "$OLD/empire_os/predictive_cloud_materializer.py")" == "$BEFORE_OLD_WRITER_SHA" ]]
  [[ "$(sha "$OLD/scripts/run_predictive_cloud_materializer.py")" == "$BEFORE_OLD_RUNNER_SHA" ]]
  [[ "$(systemctl show "$SERVICE" -p DropInPaths --value)" == "$DROPIN" ]]
  [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$SHA")" == 'commit' ]]
  [[ "$(find "$(dirname "$DROPIN")" -maxdepth 1 -mindepth 1 -printf '%f\n')" == "$(basename "$DROPIN")" ]]
}
case "$MODE" in
  --check)
    preflight
    echo 'PREDICTIVE_CLOUD_FRAMEWORK_UPGRADE_PREFLIGHT_PASS'
    echo 'PRODUCTION_UNCHANGED=true'
    exit 0 ;;
  --apply-owner-approved-observe)
    [[ "$(id -u)" -eq 0 ]] || { echo 'ROOT_OWNER_REQUIRED' >&2; exit 4; } ;;
  *) echo 'REFUSE_UNKNOWN_CLOUD_UPGRADE_ACTION' >&2; exit 2 ;;
esac
exec 9>/run/lock/empire-predictive-cloud-guard.lock
flock -n 9 || { echo 'ANOTHER_CLOUD_RELEASE_ACTIVE' >&2; exit 4; }
preflight
[[ "$(systemctl show "$TIMER" -p ActiveState --value)" == 'active' ]]
[[ "$(systemctl show "$SERVICE" -p ActiveState --value)" != 'active' ]]
backup="$(mktemp -d /var/backups/empiredb/.cloud_framework_upgrade_XXXXXXXX)"
stage="$(mktemp -d /opt/empire/.cloud_framework_upgrade_XXXXXXXX)"
timer_stopped=0
rollback_needed=0
cleanup () {
  code=$?
  trap - EXIT
  if [[ "$rollback_needed" == 1 ]]; then
    cp -p -- "$backup/previous_dropin.conf" "$DROPIN" || true
    systemctl daemon-reload || true
    for filename in future_trend_latest.json formula_latest.json optimization_fabric_latest.json status_latest.json; do
      if [[ -f "$backup/$filename" ]]; then
        cp -p -- "$backup/$filename" "/srv/empire_os/runtime/predictive_cloud/$filename" || true
      fi
    done
    echo 'PREDICTIVE_CLOUD_FRAMEWORK_RESTORED_PREVIOUS_GUARD' >&2
  fi
  if [[ "$timer_stopped" == 1 ]]; then systemctl start "$TIMER" || true; fi
  [[ ! -d "$stage" ]] || rm -rf -- "$stage"
  exit "$code"
}
trap cleanup EXIT
cp -p -- "$DROPIN" "$backup/previous_dropin.conf"
for filename in future_trend_latest.json formula_latest.json optimization_fabric_latest.json status_latest.json; do
  [[ ! -f "/srv/empire_os/runtime/predictive_cloud/$filename" ]] ||
    cp -p -- "/srv/empire_os/runtime/predictive_cloud/$filename" "$backup/$filename"
done
systemctl stop "$TIMER"
timer_stopped=1
[[ "$(systemctl show "$SERVICE" -p ActiveState --value)" != 'active' ]]
git -c safe.directory="$OWNER" -C "$OWNER" archive "$SHA" | tar -xf - -C "$stage"
mkdir -p "$stage/bin"
cp -- "$SOURCE/bin/empire-predictive-observe" "$stage/bin/empire-predictive-observe"
cp -- "$MANIFEST" "$stage/.verified-source-checksums.sha256"
(cd "$stage" && sha256sum --status -c .verified-source-checksums.sha256)
if find "$stage" -type l -print -quit | grep -q .; then
  echo 'SYMLINKED_SOURCE_HELD' >&2; exit 4
fi
chown -R root:root "$stage"
find "$stage" -type d -exec chmod 0555 {} +
find "$stage" -type f -exec chmod 0444 {} +
mv -T -- "$stage" "$TARGET"
rollback_needed=1
tmp="$(mktemp "$(dirname "$DROPIN")/.60-cloud-framework.XXXXXXXX")"
cat > "$tmp" <<EOF
[Service]
Environment=PYTHONPATH=$TARGET
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -B $TARGET/scripts/run_predictive_cloud_materializer.py
EOF
chown root:root "$tmp"; chmod 0644 "$tmp"
mv -T -- "$tmp" "$DROPIN"
systemctl daemon-reload
systemctl start "$SERVICE"
env PYTHONPATH="$TARGET" /srv/empire_os/.venv/bin/python -B - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
from empire_os.predictive_cloud_status_api import read_predictive_cloud_status
root=Path("/srv/empire_os/runtime/predictive_cloud")
now=datetime.now(timezone.utc)
for filename in ("future_trend_latest.json","formula_latest.json"):
    item=json.loads((root/filename).read_text())
    observed=datetime.fromisoformat(item["generated_at"])
    assert observed.tzinfo is not None
    assert 0 <= (now-observed).total_seconds() < 120
    assert item["prediction_ready"] is False
    assert item["independent_source_admitted"] is False
    assert item["execution_authority"] == "none"
optimization=json.loads((root/"optimization_fabric_latest.json").read_text())
assert optimization["schema_version"] == "empire.optimization.status.v2"
assert optimization["external_qpu_called"] is False
assert optimization["third_party_services"]["execution_allowed"] is False
assert optimization["automatic_production_routing"] is False
status=read_predictive_cloud_status(root/"status_latest.json", now=now)
assert status["available"] is True
assert status["components"]["optimization_fabric"]["freshness"] == "fresh"
assert status["customer_forecast_verified"] is False
assert status["commercial_prediction_authorized"] is False
assert status["framework_operational"] is False
assert status["execution_authority"] == "none"
print("CLOUD_FRAMEWORK_STATUS_AND_OPTIMIZATION_REFRESH_VERIFIED")
PY
systemctl start "$TIMER"
[[ "$(systemctl show "$TIMER" -p ActiveState --value)" == 'active' ]]
timer_stopped=0
rollback_needed=0
echo "CLOUD_FRAMEWORK_UPGRADE_DEPLOYED=$SHA"
echo "ROLLBACK_DROPIN=$DROPIN"
echo "BACKUP=$backup"
echo 'DB_PAYMENTS_OUTBOUND_UNCHANGED=true'
