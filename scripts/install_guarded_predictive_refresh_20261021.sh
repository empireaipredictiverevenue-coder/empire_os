#!/usr/bin/env bash
# Founder/production owner explicitly approved guarded OBSERVE refresh only.
# Never executes via unprivileged remote agent; never edits shared source or DB.
set -euo pipefail
umask 077

COMMAND="${1:---check}"
# Production owner supplies the exact reviewed immutable commit, not a mutable
# branch name, symlink, or latest-release pointer.
SOURCE_SHA="${2:-}"
SOURCE_BASE='/home/ubuntu/empire_releases'
SHORT="${SOURCE_SHA:0:12}"
SOURCE="$SOURCE_BASE/predictive_observe_$SHORT"
TARGET="/opt/empire/predictive_guard_$SHORT"
DROPIN_DIR='/etc/systemd/system/empire-predictive-intelligence.service.d'
DROPIN="$DROPIN_DIR/60-predictive-guard.conf"
UNIT='/etc/systemd/system/empire-predictive-intelligence.service'
ORIGINAL='/srv/empire_os/empire_os/predictive_intelligence.py'
MANIFEST="$SOURCE/metadata/critical_source_checksums.sha256"
SCRIPT="$TARGET/scripts/build_predictive_intelligence.py"
EXPECTED_UNIT='c09124b01646fadc539d9209d2148d771ad55613433f0b4ed1dd21ae8fff9719'
EXPECTED_DROPIN='91f80e88e8a71e8759ee693cf5cef5bf9c5c4f47dc201a7f841c8fe0c2c4da2a'
EXPECTED_ORIGINAL='859de1ec3015096c07a4d19e56db9585df7f0c4c0f1234ee6da38e2959b7ada3'

check () {
  [[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]
  [[ -f "$MANIFEST" && -r "$SOURCE/metadata/source.txt" ]]
  grep -qx "SOURCE_COMMIT=$SOURCE_SHA" "$SOURCE/metadata/source.txt"
  (cd "$SOURCE" && sha256sum --status -c "$MANIFEST")
  [[ -f "$SOURCE/empire_os/predictive_intelligence.py" &&
     -f "$SOURCE/scripts/build_predictive_intelligence.py" ]]
  [[ "$(sha256sum "$UNIT" | cut -d' ' -f1)" == "$EXPECTED_UNIT" ]]
  [[ "$(sha256sum "$DROPIN_DIR/20-empiredb.conf" | cut -d' ' -f1)" == "$EXPECTED_DROPIN" ]]
  [[ "$(sha256sum "$ORIGINAL" | cut -d' ' -f1)" == "$EXPECTED_ORIGINAL" ]]
  [[ ! -e "$DROPIN" && ! -L "$DROPIN" ]]
  # Strict expected drop-ins; no second owner or unknown service override.
  [[ "$(find "$DROPIN_DIR" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)" == '20-empiredb.conf' ]]
  [[ ! -L "$SOURCE" ]]
  if find "$SOURCE" -type l -print -quit | grep -q .; then
    printf '%s\n' 'HOLD_SYMLINK_IN_RELEASE' >&2
    return 4
  fi
}

case "$COMMAND" in
  --check)
    check
    printf '%s\n' 'GUARDED_PREDICTIVE_PRODUCTION_RELEASE_PREFLIGHT_PASS'
    printf '%s\n' 'PRODUCTION_UNCHANGED=true'
    exit 0
    ;;
  --apply-owner-approved-observe)
    [[ "$(id -u)" == 0 ]] || { echo 'ROOT_OWNER_EXECUTION_REQUIRED' >&2; exit 4; }
    ;;
  *)
    echo 'Usage: installer --check | --apply-owner-approved-observe' >&2
    exit 2
    ;;
esac

# The root caller already approved this exact feature-only service rollout.
exec 9>/run/lock/empire-predictive-guard-release.lock
flock -n 9 || { echo 'CONCURRENT_GUARD_RELEASE_HELD' >&2; exit 4; }
check
[[ ! -e "$TARGET" && ! -L "$TARGET" ]]
[[ "$(systemctl show empire-predictive-intelligence.service -p ActiveState --value)" != 'active' ]]
[[ "$(systemctl show empire-predictive-intelligence.timer -p ActiveState --value)" == 'active' ]]

stage="$(mktemp -d /opt/empire/.predictive_guard_XXXXXXXX)"
backup_dir="$(mktemp -d /var/backups/empiredb/.predictive_guard_XXXXXXXX)"
rollback_needed=0
timer_stopped=0
revert () {
  rc=$?
  trap - EXIT
  if [[ "$rollback_needed" == 1 ]]; then
    rm -f -- "$DROPIN"
    systemctl daemon-reload || true
    # Only restore the old snapshot when no other service/agent changed it.
    if [[ -f "$backup_dir/latest.json" ]]; then
      cp -f -- "$backup_dir/latest.json" /srv/empire_os/runtime/predictive_intelligence/latest.json || true
    fi
    echo 'GUARDED_REFRESH_SERVICE_ROLLED_BACK_TO_ORIGINAL' >&2
  fi
  if [[ "$timer_stopped" == 1 ]]; then
    systemctl start empire-predictive-intelligence.timer || true
  fi
  [[ ! -e "$stage" ]] || rm -rf -- "$stage"
  exit "$rc"
}
trap revert EXIT
install -d -m 0700 "$backup_dir"
if [[ -f /srv/empire_os/runtime/predictive_intelligence/latest.json ]]; then
  cp -p -- /srv/empire_os/runtime/predictive_intelligence/latest.json "$backup_dir/latest.json"
fi

systemctl stop empire-predictive-intelligence.timer
timer_stopped=1
[[ "$(systemctl show empire-predictive-intelligence.service -p ActiveState --value)" != 'active' ]] || {
  echo 'PRODUCTION_REFRESH_ALREADY_RUNNING_HOLD' >&2; exit 4;
}
cp -a -- "$SOURCE/." "$stage/"
chown -R root:root "$stage"
find "$stage" -type d -exec chmod 0555 {} +
find "$stage" -type f -exec chmod 0444 {} +
(cd "$stage" && sha256sum --status -c metadata/critical_source_checksums.sha256)
mv -T -- "$stage" "$TARGET"
rollback_needed=1
tmp_conf="$(mktemp "$DROPIN_DIR/.60-predictive-guard.XXXXXXXX")"
cat > "$tmp_conf" <<EOF
[Service]
Environment=PYTHONPATH=$TARGET
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -B $SCRIPT --repo-root /srv/empire_os
EOF
chmod 0644 "$tmp_conf"
chown root:root "$tmp_conf"
mv -T -- "$tmp_conf" "$DROPIN"
systemctl daemon-reload
systemctl start empire-predictive-intelligence.service

# Source must explicitly quarantine unscoped legacy RPC, even when it is zero.
python3 -B - <<'PY'
import json
from pathlib import Path
path=Path('/srv/empire_os/runtime/predictive_intelligence/latest.json')
data=json.loads(path.read_text())
assert data["source_scope_admission_status"] in (
 "GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED",
 "GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED"
)
assert data.get("original_tenant_source_authenticated") is False
assert data.get("original_outcome_issuer_authenticated") is False
assert data.get("original_forecast_registered_before_outcome") is False
assert data.get("tenant_id") is None
assert data.get("product_estimates") == {}
assert data.get("source_outcome_count") == 0
assert data.get("probability_ready_product_count") == 0
assert data.get("execution_authority") == "none"
print("GUARDED_PREDICTIVE_REFRESH_SOURCE_ADMISSION_VERIFIED")
PY
systemctl start empire-predictive-intelligence.timer
timer_stopped=0
# Complete only when the original recurring refresh timer is active again.
[[ "$(systemctl show empire-predictive-intelligence.timer -p ActiveState --value)" == 'active' ]]
rollback_needed=0
echo "PINNED_GUARDED_REFRESH_DEPLOYED=$SOURCE_SHA"
echo "ROLLBACK_SERVICE_DROPIN=$DROPIN"
echo "BEFORE_DEPLOY_RUNTIME_BACKUP=$backup_dir/latest.json"
echo 'OUTBOUND_PAYMENT_DB_AUTH_CHANGES=false'
