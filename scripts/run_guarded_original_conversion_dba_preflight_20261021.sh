#!/usr/bin/env bash
# Read-only, SHA-pinned, root-owned pgBackRest + EmpireDB catalogue check.
# No DDL, no migration, no credentials, no private records are exposed.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: run_guarded_original_conversion_dba_preflight --check|--run-read-only FULL_SHA' >&2
  exit 2
fi
ACTION="$1"
COMMIT="$2"
OWNER='/home/ubuntu/empire_agents/predictive_decision_control_20261018'
SHORT="${COMMIT:0:12}"
TARGET="/opt/empire/original_conversion_dba_preflight_$SHORT"
PY='/srv/empire_os/.venv/bin/python'
FILES=(
  empire_os/__init__.py
  empire_os/rev051_pgbackrest_readiness.py
  scripts/review_original_conversion_dba_prerequisites_20261021.py
)
source_hash() {
  git -c safe.directory="$OWNER" -C "$OWNER" show "$COMMIT:$1" |
    sha256sum | cut -d' ' -f1
}
verify_install() {
  [[ -d "$TARGET" && ! -L "$TARGET" ]]
  [[ "$(stat -c '%u' "$TARGET")" == 0 ]]
  [[ -z "$(find "$TARGET" -type l -print -quit)" ]]
  [[ -z "$(find "$TARGET" ! -user root -print -quit)" ]]
  [[ -z "$(find "$TARGET" -perm /022 -print -quit)" ]]
  [[ "$(find "$TARGET" -type f | wc -l)" -eq "${#FILES[@]}" ]]
  for source in "${FILES[@]}"; do
    [[ -f "$TARGET/$source" ]]
    [[ "$(sha256sum "$TARGET/$source" | cut -d' ' -f1)" == "$(source_hash "$source")" ]]
  done
}
preflight() {
  [[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]
  [[ -x "$PY" ]]
  [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT")" == commit ]]
  for source in "${FILES[@]}"; do
    [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT:$source")" == blob ]]
  done
  if [[ -e "$TARGET" ]]; then verify_install; fi
}
case "$ACTION" in
  --check)
    preflight
    echo "ORIGINAL_CONVERSION_DBA_PREFLIGHT_PINNED_CODE_PASS=$COMMIT"
    echo 'DATABASE_AND_BACKUP_NOT_QUERIED=true'
    exit 0 ;;
  --run-read-only)
    [[ "$(id -u)" == 0 ]] ||
      { echo 'EXISTING_ROOT_OBSERVER_REQUIRED' >&2; exit 4; } ;;
  *)
    echo 'UNSUPPORTED_DBA_PREFLIGHT_ACTION' >&2
    exit 2 ;;
esac
exec 9>/run/lock/empire-original-conversion-dba-preflight.lock
flock -n 9 || { echo 'CONCURRENT_DBA_READ_HOLD' >&2; exit 4; }
preflight
if [[ ! -e "$TARGET" ]]; then
  stage="$(mktemp -d /opt/empire/.original-conversion-dba-preflight.XXXXXXXX)"
  trap 'rm -rf -- "$stage"' EXIT
  git -c safe.directory="$OWNER" -C "$OWNER" archive "$COMMIT" -- "${FILES[@]}" |
    tar -xf - -C "$stage"
  [[ -z "$(find "$stage" -type l -print -quit)" ]] ||
    { echo 'ARCHIVE_SYMLINK_HOLD' >&2; exit 4; }
  for source in "${FILES[@]}"; do
    [[ -f "$stage/$source" &&
       "$(sha256sum "$stage/$source" | cut -d' ' -f1)" == "$(source_hash "$source")" ]]
  done
  chown -R root:root "$stage"
  find "$stage" -type d -exec chmod 0555 {} +
  find "$stage" -type f -exec chmod 0444 {} +
  mv -T -- "$stage" "$TARGET"
  trap - EXIT
fi
verify_install
cd /
env -i PATH=/usr/bin:/bin HOME=/root PYTHONPATH="$TARGET" \
  "$PY" -P -B -m scripts.review_original_conversion_dba_prerequisites_20261021 \
  --read-only
echo 'ORIGINAL_CONVERSION_DBA_PREFLIGHT_NO_DATABASE_MUTATION=true'
