#!/usr/bin/env bash
# Original, bounded EmpireDB registry source audit. NO grant, writer or DDL.
# Exact immutable Git commit copied into root-owned /opt code custody.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: registry-readonly --check|--run-read-only FULL_GIT_SHA' >&2
  exit 2
fi
ACTION="$1"
COMMIT="$2"
OWNER='/home/ubuntu/empire_agents/predictive_decision_control_20261018'
SHORT="$(printf '%s' "$COMMIT" | cut -c1-12)"
TARGET="/opt/empire/predictive_registry_readonly_$SHORT"
PY='/srv/empire_os/.venv/bin/python'
PGPASSFILE_PATH='/etc/empire/verified-order-reader/reader.pgpass'
DSN='host=127.0.0.1 port=5432 dbname=empiredb user=empire_verified_order_tenant_login'
FILES=(
  empire_os/__init__.py
  empire_os/predictive_tenant_outcome_reader_preflight.py
  empire_os/predictive_existing_tenant_registry_receipts.py
  scripts/review_predictive_registry_source_admission_20261021.py
)
source_hash () {
  git -c safe.directory="$OWNER" -C "$OWNER" show "$COMMIT:$1" |
    sha256sum | cut -d' ' -f1
}
verify_target () {
  [[ -d "$TARGET" && ! -L "$TARGET" ]]
  [[ "$(stat -c '%u' "$TARGET")" == 0 ]]
  [[ -z "$(find "$TARGET" -type l -print -quit)" ]]
  [[ -z "$(find "$TARGET" ! -user root -print -quit)" ]]
  [[ -z "$(find "$TARGET" -perm /022 -print -quit)" ]]
  for file in "${FILES[@]}"; do
    [[ -f "$TARGET/$file" ]]
    [[ "$(sha256sum "$TARGET/$file" | cut -d' ' -f1)" == "$(source_hash "$file")" ]]
  done
  [[ "$(find "$TARGET" -type f | wc -l)" -eq "${#FILES[@]}" ]]
}
preflight () {
  [[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]
  [[ -x "$PY" ]]
  [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT")" == 'commit' ]]
  for file in "${FILES[@]}"; do
    [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT:$file")" == 'blob' ]]
  done
  if [[ -e "$TARGET" ]]; then verify_target; fi
}
case "$ACTION" in
  --check)
    preflight
    echo "ORIGINAL_REGISTRY_CODE_PREFLIGHT_PASS=$COMMIT"
    echo 'LIVE_DATABASE_NOT_QUERIED=true'
    exit 0 ;;
  --run-read-only)
    [[ "$(id -u)" == 0 ]] || { echo 'ROOT_OWNER_REQUIRED' >&2; exit 4; } ;;
  *)
    echo 'REGISTRY_ACTION_NOT_ALLOWED' >&2
    exit 2 ;;
esac
exec 9>/run/lock/empire-predictive-registry-observe.lock
flock -n 9 || { echo 'REGISTRY_READ_CONCURRENT_HOLD' >&2; exit 4; }
preflight
[[ -f "$PGPASSFILE_PATH" && ! -L "$PGPASSFILE_PATH" && -r "$PGPASSFILE_PATH" ]] ||
  { echo 'EXISTING_ROOT_OWNED_CREDENTIAL_NOT_AVAILABLE' >&2; exit 4; }
if [[ ! -e "$TARGET" ]]; then
  stage="$(mktemp -d /opt/empire/.registry-readonly.XXXXXXXX)"
  trap 'rm -rf -- "$stage"' EXIT
  git -c safe.directory="$OWNER" -C "$OWNER" archive "$COMMIT" -- "${FILES[@]}" |
    tar -xf - -C "$stage"
  [[ -z "$(find "$stage" -type l -print -quit)" ]] ||
    { echo 'REGISTRY_PACKAGE_SYMLINK_HELD' >&2; exit 4; }
  for file in "${FILES[@]}"; do
    [[ -f "$stage/$file" ]]
    [[ "$(sha256sum "$stage/$file" | cut -d' ' -f1)" == "$(source_hash "$file")" ]]
  done
  chown -R root:root "$stage"
  find "$stage" -type d -exec chmod 0555 {} +
  find "$stage" -type f -exec chmod 0444 {} +
  mv -T -- "$stage" "$TARGET"
  trap - EXIT
fi
verify_target
# -P forbids Python from importing untrusted cwd (such as /srv/empire_os).
# Only this exact owner-pinned source and the venv can be imported.
cd /
env -i PATH=/usr/bin:/bin HOME=/root PGPASSFILE="$PGPASSFILE_PATH" \
  PYTHONPATH="$TARGET" EMPIREDB_TENANT_OUTCOME_READER_DSN="$DSN" \
  "$PY" -P -B -m scripts.review_predictive_registry_source_admission_20261021 --read-only
echo 'REGISTRY_READ_FINISHED_NO_PERMISSION_OR_DATA_WRITES=true'
