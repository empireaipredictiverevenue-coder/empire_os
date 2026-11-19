#!/usr/bin/env bash
# No-root, no-install, no-DB, no-container Mautic 7 upstream Client contract.
# Reproducible on EmpireOS Ubuntu 26.04 using signed apt archives.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
SYSTEM_PYTHON=/srv/empire_os/.venv/bin/python
UPSTREAM_SOURCE_URL="https://raw.githubusercontent.com/mautic/mautic/e323d688a2cbc37f4ebcc9bd7d2f2042833bde24/app/bundles/WebhookBundle/Http/Client.php"
UPSTREAM_SHA256="d33316dcb61c6350856316941ca39f9369d3d7783c0141fd667f63b7fe75813c"

test "$(id -u)" -ne 0 || { echo "REFUSE_ROOT_CONTRACT_RUN"; exit 3; }
test -x "$SYSTEM_PYTHON" || { echo "MISSING_EXISTING_TEST_PYTHON"; exit 3; }
test -f "$ROOT/tests/mautic_sandbox/verify_upstream_client.php"
test -f "$ROOT/tests/test_mautic_upstream_php_contract.py"
grep -q 'VERSION_ID="26.04"' /etc/os-release || {
  echo "UNSUPPORTED_TEST_RUNTIME_DISTRIBUTION"; exit 3;
}

TMP="$(mktemp -d /tmp/empire_mautic_upstream_php_test.XXXXXXXX)"
chmod 700 "$TMP"
cleanup() {
  status=$?
  trap - EXIT HUP INT TERM
  case "$TMP" in
    /tmp/empire_mautic_upstream_php_test.*) rm -rf -- "$TMP" ;;
    *) echo "UNSAFE_TEMP_PATH_REFUSED";;
  esac
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

cd "$TMP"
# Download official Ubuntu binary packages as user. No apt install, sudo,
# changes to system PHP, APT sources, running daemons or configuration.
apt download php8.5-cli libargon2-1 > "$TMP/apt-download.log" 2>&1
for package in php8.5-cli_*.deb libargon2-1_*.deb; do
  test -f "$package" || { echo "SIGNED_PACKAGE_DOWNLOAD_MISSING"; exit 4; }
  dpkg-deb -x "$package" "$TMP/root"
done

curl -fLsS --connect-timeout 8 --max-time 25 \
  "$UPSTREAM_SOURCE_URL" -o "$TMP/Client.php"
printf '%s  %s\n' "$UPSTREAM_SHA256" "$TMP/Client.php" | sha256sum --check --status || {
  echo "UPSTREAM_MAUTIC_7_CLIENT_DIGEST_MISMATCH"; exit 4;
}

export LD_LIBRARY_PATH="$TMP/root/usr/lib/x86_64-linux-gnu"
export EMPIRE_MAUTIC_TEST_PHP_BIN="$TMP/root/usr/bin/php8.5"
export EMPIRE_MAUTIC_TEST_UPSTREAM_CLIENT="$TMP/Client.php"
"$EMPIRE_MAUTIC_TEST_PHP_BIN" -n -l \
  "$ROOT/tests/mautic_sandbox/verify_upstream_client.php" >/dev/null

cd "$ROOT"
PYTHONDONTWRITEBYTECODE=1 "$SYSTEM_PYTHON" -B -m pytest \
  -q -p no:cacheprovider tests/test_mautic_upstream_php_contract.py
echo "UNMODIFIED_MAUTIC_7_PHP_SENDER_TO_CRM_TEST_PASSED_TEMP_CLEANUP"
