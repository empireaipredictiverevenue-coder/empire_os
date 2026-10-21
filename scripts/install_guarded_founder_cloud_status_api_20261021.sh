#!/usr/bin/env bash
# Switch ONLY the existing loopback Founder Cloud status API source.
# All other routers and service overlays are preserved.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: installer --check|--apply-owner-approved-observe EXACT_CLOUD_COMMIT_SHA' >&2; exit 2
fi
ACTION="$1"
COMMIT="$2"
EXPECTED_COMMIT='5caaa410676942890caba41924d95338680466f1'
SOURCE='/opt/empire/predictive_cloud_guard_5caaa4106769/empire_os/predictive_cloud_status_api.py'
TARGET='/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018/empire_os/predictive_cloud_status_api.py'
LEGACY_STATUS='/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018/empire_os/predictive_cloud_status.py'
SERVICE_SOURCE='/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018/empire_os/founder_dashboard_service.py'
SERVICE='empire-founder-dashboard-api.service'
UNIT='/etc/systemd/system/empire-founder-dashboard-api.service'
DIR='/etc/systemd/system/empire-founder-dashboard-api.service.d'
EXPECTED_SOURCE_SHA='2759bedb5fc40b3de620d9db112e7b8f58391fa43c979a0b3d80e7272440c106'
EXPECTED_TARGET_SHA='da7cfc60bcbd4bba62802d4ed2384d04b68e13130b97bb897f34621b58e6c175'
EXPECTED_STATUS_SHA='4e4c104be0b71ff6a310354e7c69ba5c72fb1eaec035eebbdfc42de4436bc3c4'
EXPECTED_ROUTER_SHA='8ddf4d47282724726a236e9888964a1e15d38aff58556e0cd5ed51eacedb9fd8'
EXPECTED_UNIT_SHA='79744109c6be86c44e457a4eb77c1089a93a17d3277381ffe55df162e0796877'
sha () { sha256sum "$1" | cut -d' ' -f1; }
preflight () {
  [[ "$COMMIT" == "$EXPECTED_COMMIT" ]]
  [[ -f "$SOURCE" && ! -L "$SOURCE" && -f "$TARGET" && ! -L "$TARGET" ]]
  [[ "$(stat -c '%u' "$SOURCE")" == 0 ]]
  [[ "$(sha "$SOURCE")" == "$EXPECTED_SOURCE_SHA" ]]
  [[ "$(sha "$TARGET")" == "$EXPECTED_TARGET_SHA" ]]
  [[ "$(sha "$LEGACY_STATUS")" == "$EXPECTED_STATUS_SHA" ]]
  [[ "$(sha "$SERVICE_SOURCE")" == "$EXPECTED_ROUTER_SHA" ]]
  [[ "$(sha "$UNIT")" == "$EXPECTED_UNIT_SHA" ]]
  [[ "$(sha "$DIR/20-owned-imap.conf")" == 'a3ae44b4b2f1e1ebd14ab6e46a98af6331e37b84bccffda6b4189ea3cd223f89' ]]
  [[ "$(sha "$DIR/30-canonical-reply-view.conf")" == '4a9915633a4c7ac4282b07d77d10825b81c003fd3303072e9810b02984731ab3' ]]
  [[ "$(sha "$DIR/90-commercial-pipeline-release.conf")" == 'f6ff46a39442a0ab62cb0fdb267d9aad3b6c3f50b42b457dae1f9933b5f8f191' ]]
  [[ "$(sha "$DIR/95-private-historical-evidence-read-api.conf")" == '11903ad1d01e079d32ff38f2f6f6fae496f7130f0133f38cd8ad3dcd7d63b301' ]]
  [[ "$(find "$DIR" -mindepth 1 -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort)" == "$(printf '%s\n' '20-owned-imap.conf' '30-canonical-reply-view.conf' '90-commercial-pipeline-release.conf' '95-private-historical-evidence-read-api.conf')" ]]
  [[ "$(systemctl show "$SERVICE" -p ActiveState --value)" == 'active' ]]
  [[ "$(systemctl show "$SERVICE" -p DropInPaths --value)" == "$DIR/20-owned-imap.conf $DIR/30-canonical-reply-view.conf $DIR/90-commercial-pipeline-release.conf $DIR/95-private-historical-evidence-read-api.conf" ]]
}
case "$ACTION" in
  --check)
    preflight; echo 'FOUNDER_CLOUD_STATUS_SINGLE_MODULE_PREFLIGHT_PASS'; echo 'PRODUCTION_UNCHANGED=true'; exit 0 ;;
  --apply-owner-approved-observe)
    [[ "$(id -u)" -eq 0 ]] || { echo 'ROOT_OWNER_REQUIRED' >&2; exit 4; } ;;
  *) echo 'UNKNOWN_ACTION_HELD' >&2; exit 2 ;;
esac
exec 9>/run/lock/empire-founder-cloud-status-api-20261021.lock
flock -n 9 || { echo 'FOUNDER_CLOUD_STATUS_CONCURRENT_CHANGE_HELD' >&2; exit 4; }
preflight
backup="$(mktemp -d /var/backups/empiredb/.founder_cloud_api_XXXXXXXX)"
cp -p -- "$TARGET" "$backup/previous_status_api.py"
changed=0
restore () {
  code=$?
  trap - EXIT
  if [[ "$changed" == 1 ]]; then
    install -o ubuntu -g ubuntu -m 0644 "$backup/previous_status_api.py" "$TARGET" || true
    systemctl restart "$SERVICE" || true
    echo 'FOUNDER_CLOUD_STATUS_SINGLE_MODULE_ROLLED_BACK' >&2
  fi
  exit "$code"
}
trap restore EXIT
# Only the Cloud status module is replaced. Preserve the exact original
# Founder app source and all other owner routers.
tmp="$(mktemp "$(dirname "$TARGET")/.predictive-cloud-status.XXXXXXXX")"
cp -- "$SOURCE" "$tmp"
chown ubuntu:ubuntu "$tmp"
chmod 0644 "$tmp"
[[ "$(sha "$tmp")" == "$EXPECTED_SOURCE_SHA" ]]
mv -T -- "$tmp" "$TARGET"
changed=1
systemctl restart "$SERVICE"
# Loopback-only non-mutating probes after restart; refuse stale/forged status.
for attempt in 1 2 3 4 5; do
  if curl -fsS --max-time 3 http://127.0.0.1:8766/health > "$backup/health.json" &&
     curl -fsS --max-time 4 http://127.0.0.1:8766/v1/predictive-cloud/status > "$backup/cloud_status.json"; then
    break
  fi
  sleep 1
done
python3 -B - "$backup/health.json" "$backup/cloud_status.json" <<'PY'
import json,sys
health=json.load(open(sys.argv[1]))
cloud=json.load(open(sys.argv[2]))
assert health['ok'] is True and health['read_only'] is True
assert cloud['available'] is True
assert cloud['schema_version']=='empire.predictive_cloud.status.v2'
assert cloud['component_count']==28
assert len(cloud['components'])==28
assert cloud['execution_authority']=='none'
assert cloud['customer_forecast_verified'] is False
assert cloud['commercial_prediction_authorized'] is False
assert cloud['framework_operational'] is False
assert cloud['outreach_sent_by_status'] is False
assert cloud['payment_action_by_status'] is False
print('FOUNDER_CLOUD_STATUS_LIVE_API_VALIDATION_PASS')
PY
[[ "$(sha "$TARGET")" == "$EXPECTED_SOURCE_SHA" ]]
[[ "$(sha "$SERVICE_SOURCE")" == "$EXPECTED_ROUTER_SHA" ]]
[[ "$(sha "$UNIT")" == "$EXPECTED_UNIT_SHA" ]]
[[ "$(systemctl show "$SERVICE" -p ActiveState --value)" == 'active' ]]
changed=0
echo "FOUNDER_CLOUD_STATUS_API_PROMOTED=$COMMIT"
echo "ROLLBACK_FILE=$backup/previous_status_api.py"
echo 'OTHER_ROUTERS_CLOUD_TIMER_DB_OUTBOUND_PAYMENTS_UNCHANGED=true'
