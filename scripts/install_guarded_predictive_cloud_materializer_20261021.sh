#!/usr/bin/env bash
# Root-controlled OBSERVE-only switch for the existing Cloud timer.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: installer --check|--apply-owner-approved-observe EXACT_FULL_COMMIT_SHA' >&2
  exit 2
fi
ACTION="$1"
SHA="$2"
SHORT="$(printf '%s' "$SHA" | cut -c1-12)"
OWNER='/home/ubuntu/empire_agents/predictive_decision_control_20261018'
RELEASE="/home/ubuntu/empire_releases/predictive_observe_$SHORT"
TARGET="/opt/empire/predictive_cloud_guard_$SHORT"
SERVICE='empire-predictive-cloud-materializer.service'
TIMER='empire-predictive-cloud-materializer.timer'
UNIT='/etc/systemd/system/empire-predictive-cloud-materializer.service'
DIR='/etc/systemd/system/empire-predictive-cloud-materializer.service.d'
DROPIN="$DIR/60-verified-source-admission.conf"
MANIFEST="$RELEASE/metadata/critical_source_checksums.sha256"
EXPECTED_UNIT='58a1e516d5c5f46b9638cb16e1e87ea56f7535610b16d1f0cf64691fb74f502f'
EXPECTED_ORIGINAL='e7ecaf095ba4798543c0e7cc1a4c84c41c86ec9b8eb27f6bf7581a8ea4e7c6e8'
EXPECTED_RUNNER='8e165e3e9efe610a73b36b6608d8449f181538a01692f3563f113839a48af4f8'
check () {
  [[ "$SHA" =~ ^[0-9a-f]{40}$ ]]
  [[ -f "$MANIFEST" && ! -L "$RELEASE" ]]
  grep -qx "SOURCE_COMMIT=$SHA" "$RELEASE/metadata/source.txt"
  (cd "$RELEASE" && sha256sum --status -c "$MANIFEST")
  [[ "$(sha256sum "$UNIT" | cut -d' ' -f1)" == "$EXPECTED_UNIT" ]]
  [[ "$(sha256sum /srv/empire_os/empire_os/predictive_cloud_materializer.py | cut -d' ' -f1)" == "$EXPECTED_ORIGINAL" ]]
  [[ "$(sha256sum /srv/empire_os/scripts/run_predictive_cloud_materializer.py | cut -d' ' -f1)" == "$EXPECTED_RUNNER" ]]
  [[ ! -e "$TARGET" && ! -L "$TARGET" && ! -e "$DROPIN" && ! -L "$DROPIN" ]]
  [[ ! -d "$DIR" || -z "$(find "$DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]
  [[ "$(systemctl show "$SERVICE" -p DropInPaths --value)" == '' ]]
  [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$SHA")" == 'commit' ]]
}
case "$ACTION" in
  --check) check; echo 'PREDICTIVE_CLOUD_GUARDED_PREFLIGHT_PASS'; echo 'PRODUCTION_UNCHANGED=true'; exit 0 ;;
  --apply-owner-approved-observe)
    [[ "$(id -u)" == 0 ]] || { echo 'ROOT_OWNER_REQUIRED' >&2; exit 4; } ;;
  *) echo 'Usage: installer --check|--apply-owner-approved-observe EXACT_FULL_COMMIT_SHA' >&2; exit 2 ;;
esac
exec 9>/run/lock/empire-predictive-cloud-guard.lock
flock -n 9 || { echo 'CLOUD_GUARD_CONCURRENT_RELEASE_HELD' >&2; exit 4; }
check
[[ "$(systemctl show "$TIMER" -p ActiveState --value)" == 'active' ]]
[[ "$(systemctl show "$SERVICE" -p ActiveState --value)" != 'active' ]]
backup="$(mktemp -d /var/backups/empiredb/.cloud_guard_XXXXXXXX)"
stage="$(mktemp -d /opt/empire/.predictive_cloud_guard_XXXXXXXX)"
timer_stopped=0
rollback_needed=0
revert () {
  result=$?
  trap - EXIT
  if [[ "$rollback_needed" == 1 ]]; then
    rm -f -- "$DROPIN"
    systemctl daemon-reload || true
    for file in future_trend_latest.json formula_latest.json status_latest.json; do
      [[ ! -f "$backup/$file" ]] || cp -p -- "$backup/$file" "/srv/empire_os/runtime/predictive_cloud/$file" || true
    done
    echo 'PREDICTIVE_CLOUD_GUARD_ROLLED_BACK' >&2
  fi
  if [[ "$timer_stopped" == 1 ]]; then systemctl start "$TIMER" || true; fi
  [[ ! -d "$stage" ]] || rm -rf -- "$stage"
  exit "$result"
}
trap revert EXIT
for file in future_trend_latest.json formula_latest.json status_latest.json; do
  [[ ! -f "/srv/empire_os/runtime/predictive_cloud/$file" ]] ||
    cp -p -- "/srv/empire_os/runtime/predictive_cloud/$file" "$backup/$file"
done
systemctl stop "$TIMER"
timer_stopped=1
[[ "$(systemctl show "$SERVICE" -p ActiveState --value)" != 'active' ]]
# Archive the exact reviewed Git object, not mutable /home release code.
git -c safe.directory="$OWNER" -C "$OWNER" archive "$SHA" | tar -xf - -C "$stage"
# The release launcher is a generated audited artifact, not part of Git.
mkdir -p "$stage/bin"
cp -- "$RELEASE/bin/empire-predictive-observe" "$stage/bin/empire-predictive-observe"
cp -- "$MANIFEST" "$stage/.verified-source-checksums.sha256"
(cd "$stage" && sha256sum --status -c .verified-source-checksums.sha256)
if find "$stage" -type l -print -quit | grep -q .; then
  echo 'SOURCE_ARCHIVE_SYMLINK_HOLD' >&2; exit 4
fi
chown -R root:root "$stage"
find "$stage" -type d -exec chmod 0555 {} +
find "$stage" -type f -exec chmod 0444 {} +
mv -T -- "$stage" "$TARGET"
rollback_needed=1
install -d -m 0755 "$DIR"
conf="$(mktemp "$DIR/.60-cloud-guard.XXXXXXXX")"
cat > "$conf" <<EOF
[Service]
Environment=PYTHONPATH=$TARGET
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -B $TARGET/scripts/run_predictive_cloud_materializer.py
EOF
chown root:root "$conf"; chmod 0644 "$conf"
mv -T -- "$conf" "$DROPIN"
systemctl daemon-reload
systemctl start "$SERVICE"
python3 -B - <<'PY'
import json
from pathlib import Path
from datetime import datetime, timezone
root=Path('/srv/empire_os/runtime/predictive_cloud')
for filename in ('future_trend_latest.json','formula_latest.json'):
    result=json.loads((root/filename).read_text())
    dt=datetime.fromisoformat(result['generated_at'])
    assert dt.tzinfo is not None
    assert 0 <= (datetime.now(timezone.utc)-dt).total_seconds() < 120
    assert result['prediction_ready'] is False
    assert result['independent_source_admitted'] is False
    assert result['economic_rows_independently_verified'] is False
    assert result['normalized_economic_candidate_count'] == 0
    assert result['source_admission_state'] == 'UNVERIFIED_LOCAL_SNAPSHOT_ONLY'
    assert result['actual_revenue'] is False
    assert result['execution_authority'] == 'none'
print('PREDICTIVE_CLOUD_LIVE_SOURCE_ADMISSION_HOLD_VERIFIED')
PY
systemctl start "$TIMER"
[[ "$(systemctl show "$TIMER" -p ActiveState --value)" == 'active' ]]
timer_stopped=0
rollback_needed=0
echo "PREDICTIVE_CLOUD_GUARD_DEPLOYED=$SHA"
echo "ROLLBACK_DROPIN=$DROPIN"
echo "PRIOR_RUNTIME_BACKUP=$backup"
echo 'PAYMENTS_OUTBOUND_DATABASE_ROLES_UNCHANGED=true'
