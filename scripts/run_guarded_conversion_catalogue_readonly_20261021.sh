#!/usr/bin/env bash
# Dedicated original conversion metadata: existing EmpireDB reader, zero rows/DDL.
# Owner pin, immutable root custody, fail-closed checksum gate.
set -euo pipefail
umask 077
if [[ "$#" -ne 2 ]]; then
  echo 'Usage: run_guarded_conversion_catalogue_readonly --check|--run-read-only FULL_SHA' >&2
  exit 2
fi
ACTION="$1"
COMMIT="$2"
OWNER='/home/ubuntu/empire_agents/predictive_decision_control_20261018'
SHORT="${COMMIT:0:12}"
TARGET="/opt/empire/original_conversion_catalogue_$SHORT"
PY='/srv/empire_os/.venv/bin/python'
PASSFILE='/etc/empire/verified-order-reader/reader.pgpass'
DSN='host=127.0.0.1 port=5432 dbname=empiredb user=empire_verified_order_tenant_login'
FILES=(
  empire_os/__init__.py
  empire_os/predictive_tenant_outcome_reader_preflight.py
  empire_os/predictive_original_conversion_catalogue.py
  scripts/review_original_conversion_catalogue_20261021.py
)
file_sha () {
  git -c safe.directory="$OWNER" -C "$OWNER" show "$COMMIT:$1" |
    sha256sum | cut -d' ' -f1
}
verify_install () {
  [[ -d "$TARGET" && ! -L "$TARGET" ]]
  [[ "$(stat -c '%u' "$TARGET")" == 0 ]]
  [[ -z "$(find "$TARGET" -type l -print -quit)" ]]
  [[ -z "$(find "$TARGET" ! -user root -print -quit)" ]]
  [[ -z "$(find "$TARGET" -perm /022 -print -quit)" ]]
  [[ "$(find "$TARGET" -type f | wc -l)" -eq "${#FILES[@]}" ]]
  for f in "${FILES[@]}"; do
    [[ -f "$TARGET/$f" ]]
    [[ "$(sha256sum "$TARGET/$f" | cut -d' ' -f1)" == "$(file_sha "$f")" ]]
  done
}
preflight () {
  [[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]]
  [[ -x "$PY" ]]
  [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT")" == commit ]]
  for f in "${FILES[@]}"; do
    [[ "$(git -c safe.directory="$OWNER" -C "$OWNER" cat-file -t "$COMMIT:$f")" == blob ]]
  done
  if [[ -e "$TARGET" ]]; then verify_install; fi
}
case "$ACTION" in
  --check)
    preflight
    echo "CONVERSION_CATALOGUE_PINNED_CODE_PREFLIGHT_PASS=$COMMIT"
    echo 'DATABASE_NOT_QUERIED=true'
    exit 0 ;;
  --run-read-only)
    [[ "$(id -u)" == 0 ]] || { echo 'EXISTING_ROOT_CREDENTIAL_OWNER_REQUIRED' >&2; exit 4; } ;;
  *) echo 'CONVERSION_CATALOGUE_UNSUPPORTED_ACTION' >&2; exit 2 ;;
esac
exec 9>/run/lock/empire-original-conversion-catalogue-observe.lock
flock -n 9 || { echo 'CONVERSION_CATALOGUE_CONCURRENT_HOLD' >&2; exit 4; }
preflight
[[ -f "$PASSFILE" && ! -L "$PASSFILE" && -r "$PASSFILE" ]] ||
  { echo 'EXISTING_VERIFIED_READER_CREDENTIAL_UNAVAILABLE' >&2; exit 4; }
if [[ ! -e "$TARGET" ]]; then
  stage="$(mktemp -d /opt/empire/.original-conversion-catalogue.XXXXXXXX)"
  trap 'rm -rf -- "$stage"' EXIT
  git -c safe.directory="$OWNER" -C "$OWNER" archive "$COMMIT" -- "${FILES[@]}" |
    tar -xf - -C "$stage"
  [[ -z "$(find "$stage" -type l -print -quit)" ]] ||
    { echo 'ARCHIVE_SYMLINK_HOLD' >&2; exit 4; }
  for f in "${FILES[@]}"; do
    [[ -f "$stage/$f" && "$(sha256sum "$stage/$f" | cut -d' ' -f1)" == "$(file_sha "$f")" ]]
  done
  chown -R root:root "$stage"
  find "$stage" -type d -exec chmod 0555 {} +
  find "$stage" -type f -exec chmod 0444 {} +
  mv -T -- "$stage" "$TARGET"
  trap - EXIT
fi
verify_install
cd /
env -i PATH=/usr/bin:/bin HOME=/root PGPASSFILE="$PASSFILE" \
    PYTHONPATH="$TARGET" EMPIREDB_TENANT_OUTCOME_READER_DSN="$DSN" \
    "$PY" -P -B -m scripts.review_original_conversion_catalogue_20261021 --read-only
echo 'ORIGINAL_CONVERSION_CATALOGUE_CHECK_NO_ROW_READS_WRITES_OR_GRANTS=true'
