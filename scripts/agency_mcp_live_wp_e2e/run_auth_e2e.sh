#!/usr/bin/env bash
# Rootless, loopback-only, disposable real WP 6.8 / PHP 8.5 / MariaDB browser and restore acceptance.
set -euo pipefail
umask 077
test "$(id -un)" = ubuntu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
test "$(git -C "$ROOT" branch --show-current)" = "feature/agency-wp-car-yard-private-20261022"
T="$(mktemp -d /tmp/empire_agency_mcp_wordpress_XXXXXXXX)"
DBPID=''
WEBPID=''
cleanup() {
  rc=$?
  trap - EXIT
  if [[ -n "$WEBPID" ]]; then kill "$WEBPID" 2>/dev/null || true; wait "$WEBPID" 2>/dev/null || true; fi
  if [[ -n "$DBPID" ]]; then kill "$DBPID" 2>/dev/null || true; wait "$DBPID" 2>/dev/null || true; fi
  if [[ -d "$T" && "$T" == /tmp/empire_agency_mcp_wordpress_* && "$(stat -c '%a' "$T")" == 700 ]]; then
     rm -rf -- "$T"
  fi
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -m 700 "$T/root"
(
  cd "$T"
  timeout 120s apt download mariadb-server-core mariadb-server mariadb-client-core mariadb-client \
    php8.5-cli php8.5-common php8.5-mysql php8.5-gd php8.5-mbstring \
    php8.5-xml php8.5-curl php8.5-zip libargon2-1 libonig5 libgd3 libzip5 libimagequant0 libxpm4 >/dev/null 2>&1
  for f in ./*.deb; do dpkg-deb -x "$f" root; done
)
LIB="$T/root/usr/lib/x86_64-linux-gnu"
EXT="$T/root/usr/lib/php/20250925"
export LD_LIBRARY_PATH="$LIB"
PHP="$T/root/usr/bin/php8.5"
php_safe() {
 "$PHP" -n -d display_errors=0 -d log_errors=1 -d error_reporting=22527 \
 -d "extension=$EXT/mysqlnd.so" -d "extension=$EXT/mysqli.so" \
 -d "extension=$EXT/mbstring.so" -d "extension=$EXT/dom.so" \
 -d "extension=$EXT/simplexml.so" -d "extension=$EXT/xml.so" \
 -d "extension=$EXT/xmlreader.so" -d "extension=$EXT/xmlwriter.so" \
 -d "extension=$EXT/gd.so" -d "extension=$EXT/curl.so" \
 -d "extension=$EXT/zip.so" "$@"
}
php_safe -v | head -2
for phpfile in "$ROOT"/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/*.php "$ROOT"/scripts/native_wp_v03/*.php; do
  php_safe -l "$phpfile" >/dev/null
done
mkdir -m 700 "$T/data"
export PATH="$T/root/usr/bin:$PATH"
timeout 70s "$T/root/usr/bin/mariadb-install-db" --no-defaults \
 "--basedir=$T/root/usr" "--datadir=$T/data" \
 --auth-root-authentication-method=normal --skip-test-db --user=ubuntu >/dev/null 2>&1
export YARD_MYSQL_SOCKET="$T/mariadb.sock"
"$T/root/usr/sbin/mariadbd" --no-defaults \
 "--basedir=$T/root/usr" "--datadir=$T/data" \
 "--socket=$YARD_MYSQL_SOCKET" "--pid-file=$T/mariadb.pid" \
 "--plugin-dir=$T/root/usr/lib/mysql/plugin" \
 "--character-sets-dir=$T/root/usr/share/mariadb/charsets" \
 "--lc-messages-dir=$T/root/usr/share/mariadb" \
 "--tmpdir=$T" "--log-error=$T/mariadb.log" --skip-networking --skip-log-bin \
 --innodb-buffer-pool-size=64M --max-connections=12 --user=ubuntu &
DBPID=$!
ok=0
for i in $(seq 1 120); do
  if "$T/root/usr/bin/mariadb" --no-defaults -u root "--socket=$YARD_MYSQL_SOCKET" -Nse 'SELECT 1' >/dev/null 2>&1; then ok=1; break; fi
  sleep .1
done
if [[ $ok != 1 ]]; then tail -30 "$T/mariadb.log" || true; exit 2; fi
mariadb_cli() { "$T/root/usr/bin/mariadb" --no-defaults -u root "--socket=$YARD_MYSQL_SOCKET" "$@"; }
export YARD_DATABASE=empire_yard_wp_native
mariadb_cli -e "CREATE DATABASE $YARD_DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mkdir -m 700 "$T/site"
curl -fsSL --max-time 100 "https://wordpress.org/wordpress-6.8.11.tar.gz" -o "$T/wordpress.tar.gz"
tar -xzf "$T/wordpress.tar.gz" -C "$T/site" --strip-components=1 --no-same-owner --no-same-permissions
export YARD_SITE_DIR="$T/site"
mkdir -p "$YARD_SITE_DIR/wp-content/themes/empire-local-services" "$YARD_SITE_DIR/wp-content/plugins/empire-car-yard" "$YARD_SITE_DIR/wp-content/mu-plugins"
cp -a "$ROOT/prototypes/agency_wordpress_service_handoff_20261022/empire-local-services/." "$YARD_SITE_DIR/wp-content/themes/empire-local-services/"
cp -a "$ROOT/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/." "$YARD_SITE_DIR/wp-content/plugins/empire-car-yard/"
mkdir -p "$YARD_SITE_DIR/wp-content/plugins/empire-agency-integration-bridge"
cp -a "$ROOT/prototypes/agency_wordpress_service_handoff_20261022/empire-agency-integration-bridge/." "$YARD_SITE_DIR/wp-content/plugins/empire-agency-integration-bridge/"
port="$(python3 - <<'PY'
import socket
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();print(port)
PY
)"
export YARD_BASE_URL="http://127.0.0.1:$port"
export YARD_ADMIN_PASSWORD="$(python3 -c "import secrets;print(secrets.token_hex(28))")"
export YARD_SCREENSHOT_DIR="$T/screenshots"
mkdir -m 700 "$YARD_SCREENSHOT_DIR"
export YARD_CHROME=/home/ubuntu/.cache/puppeteer/chrome/linux-139.0.7258.66/chrome-linux64/chrome
test -x "$YARD_CHROME"
cat > "$YARD_SITE_DIR/wp-config.php" <<'PHP_CONFIG'
<?php
define('DB_NAME',getenv('YARD_DATABASE'));
define('DB_USER','root');
define('DB_PASSWORD','');
define('DB_HOST','localhost:'.getenv('YARD_MYSQL_SOCKET'));
define('DB_CHARSET','utf8mb4');
define('DB_COLLATE','');
define('WP_HOME',getenv('YARD_BASE_URL'));
define('WP_SITEURL',getenv('YARD_BASE_URL'));
define('WP_ENVIRONMENT_TYPE','local');
define('WP_HTTP_BLOCK_EXTERNAL',true);
define('DISALLOW_FILE_EDIT',true);
define('WP_DEBUG',false);
define('DISABLE_WP_CRON',true);
define('AUTOMATIC_UPDATER_DISABLED',true);
define('EMPIRE_YARD_STAGING_STAFF_UI_ENABLED',true);
define('EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED',true);
define('EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY',true);
define('AUTH_KEY','synthetic_staging_auth_20261022_random_only');
define('SECURE_AUTH_KEY','synthetic_staging_secure_auth_20261022');
define('LOGGED_IN_KEY','synthetic_staging_logged_in_20261022');
define('NONCE_KEY','synthetic_staging_nonce_20261022');
define('AUTH_SALT','synthetic_staging_auth_salt_20261022');
define('SECURE_AUTH_SALT','synthetic_staging_secure_salt_20261022');
define('LOGGED_IN_SALT','synthetic_staging_login_salt_20261022');
define('NONCE_SALT','synthetic_staging_nonce_salt_20261022');
$table_prefix='wp_';
if(!defined('ABSPATH')) define('ABSPATH',__DIR__.'/');
require_once ABSPATH.'wp-settings.php';
PHP_CONFIG
cat > "$YARD_SITE_DIR/wp-content/mu-plugins/yard-stage.php" <<'PHP_HOOKS'
<?php
add_filter('pre_wp_mail',static function(){ return true; });
add_filter('empire_yard_staff_calendar',static function(){
  return ['timezone'=>'Australia/Sydney',
    'hours'=>[1=>['08:00','17:00'],2=>['08:00','17:00'],3=>['08:00','17:00'],4=>['08:00','17:00'],5=>['08:00','17:00']],
    'blackout_dates'=>['2026-12-25']];
});
add_filter('xmlrpc_enabled','__return_false');
PHP_HOOKS
cat > "$YARD_SITE_DIR/router.php" <<'PHP_ROUTER'
<?php
$path=parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH);
if(is_string($path) && is_file(__DIR__.$path)) return false;
require __DIR__.'/index.php';
PHP_ROUTER
export YARD_FAKE_IMAGE="$T/synthetic.png"
python3 - <<'PY'
import os,struct,zlib
w,h=640,360
raw=b''.join(b'\0'+bytes([30,100+(y%70),190,255])*w for y in range(h))
def chunk(t,data):return struct.pack('!I',len(data))+t+data+struct.pack('!I',zlib.crc32(t+data)&0xffffffff)
img=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b'')
open(os.environ['YARD_FAKE_IMAGE'],'wb').write(img)
PY
php_safe "$ROOT/scripts/native_wp_v03/bootstrap.php" > "$T/bootstrap.json"
export YARD_MCP_SECRET_FILE="$T/wp_app_password"
export YARD_MCP_UUID_FILE="$T/wp_app_uuid"
php_safe "$ROOT/scripts/agency_mcp_live_wp_e2e/setup_api.php" > "$T/api_setup.json"
cat "$T/bootstrap.json"
php_safe -S "127.0.0.1:$port" -t "$YARD_SITE_DIR" "$YARD_SITE_DIR/router.php" > "$T/php-server.log" 2>&1 &
WEBPID=$!
ready=0
for i in $(seq 1 100); do
  if curl --noproxy '*' -fsS --max-time 2 "$YARD_BASE_URL/" >/dev/null 2>&1; then ready=1; break; fi
  sleep .1
done
if [[ $ready != 1 ]]; then tail -35 "$T/php-server.log"; exit 3; fi
if ! ss -lnt | grep -q "127.0.0.1:$port "; then echo LOOPBACK_BIND_NOT_VERIFIED; exit 4; fi
echo "NATIVE_WP_MYSQL_LOOPBACK_ONLY_HTTP_READY"
# Credentials are held only in this protected one-shot process environment.
export YARD_MCP_APP_PASSWORD="$(cat "$YARD_MCP_SECRET_FILE")"
node "$ROOT/scripts/agency_mcp_live_wp_e2e/real_wp_mcp.mjs" > "$T/mcp_auth.json"
php_safe "$ROOT/scripts/agency_mcp_live_wp_e2e/revoke_api.php" > "$T/revoke.json"
node "$ROOT/scripts/agency_mcp_live_wp_e2e/verify_revoke.mjs" > "$T/revocation_verified.json"
unset YARD_MCP_APP_PASSWORD
rm -f -- "$YARD_MCP_SECRET_FILE" "$YARD_MCP_UUID_FILE"
python3 - "$T" "$ROOT" <<'PY_REPORT'
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
sandbox,root=map(Path,sys.argv[1:])
api=json.loads((sandbox/'api_setup.json').read_text())
mcp=json.loads((sandbox/'mcp_auth.json').read_text())
revoke=json.loads((sandbox/'revoke.json').read_text())
verified=json.loads((sandbox/'revocation_verified.json').read_text())
bootstrap=json.loads((sandbox/'bootstrap.json').read_text())
assert api['status']=='SYNTHETIC_WORDPRESS_APP_PASSWORD_CREATED'
assert api['integration_enabled'] is True
assert api['plugin_active'] is True
assert mcp['status']=='AUTHENTICATED_MCP_TO_REAL_WORDPRESS_MARIADB_PASS'
assert all(mcp['checks'].values()) and mcp['checks_passed']>=10
assert revoke['status']=='SYNTHETIC_WORDPRESS_APP_PASSWORD_REVOKED'
assert verified['http_status']==401
assert bootstrap['native_wpdb_innodb_ready'] is True
out=root/'docs/commercial/EMPIRE_AGENCY_REAL_WP_MYSQL_MCP_AUTH_E2E_20261022.json'
assert not out.exists() and not out.is_symlink()
paths=[
 'scripts/agency_mcp_live_wp_e2e/setup_api.php',
 'scripts/agency_mcp_live_wp_e2e/revoke_api.php',
 'scripts/agency_mcp_live_wp_e2e/real_wp_mcp.mjs',
 'scripts/agency_mcp_live_wp_e2e/verify_revoke.mjs',
 'scripts/agency_mcp_live_wp_e2e/run_auth_e2e.sh',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/scoped-server.mjs',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/connector-registry.staging.json',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/scoped-policy.test.mjs',
]
result={
 'schema_version':'empire.agency.authenticated_mcp_wp_mysql.v1',
 'status':'REAL_WORDPRESS_MARIADB_SCOPED_MCP_APP_PASSWORD_LIFECYCLE_PASS',
 'observed_utc':datetime.now(timezone.utc).isoformat(),
 'wordpress_version':api['wordpress_version'],
 'php_version':api['php_version'],
 'native_mariadb_database':True,'loopback_http_only':True,
 'native_wordpress_plugin_enabled':True,
 'wordpress_real_application_password_authentication':True,
 'credential_revoked_after_test':True,
 'post_revocation_http_status':verified['http_status'],
 'scope':{'tenant_id':mcp['tenant_id'],'site_id':mcp['site_id'],
          'connector_id':mcp['registry_connector']},
 'mcp_checks':mcp['checks'],'mcp_checks_passed':mcp['checks_passed'],
 'secret_values_in_receipt':False,'test_site_temporary':True,
 'production_changes':False,'crm_payments_outbound_activated':False,
 'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
 'limitations':'Synthetic staging only. No real tenant gateway, production OAuth, vault integration, client API access or production WordPress release.'
}
with out.open('x',encoding='utf8') as f:json.dump(result,f,indent=2,sort_keys=True);f.write(chr(10))
print(json.dumps({'status':result['status'],'checks':result['mcp_checks_passed'],
                  'revoked_http_status':result['post_revocation_http_status'],
                  'production_changes':False},sort_keys=True))
PY_REPORT
echo 'DISPOSABLE_MCP_WORDPRESS_TEST_DONE_CLEANUP_ON_EXIT'
