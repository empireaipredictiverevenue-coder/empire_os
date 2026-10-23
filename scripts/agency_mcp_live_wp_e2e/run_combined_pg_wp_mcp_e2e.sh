#!/usr/bin/env bash
# Rootless, loopback-only, disposable real WP 6.8 / PHP 8.5 / MariaDB browser and restore acceptance.
set -euo pipefail
umask 077
test "$(id -un)" = ubuntu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
test "$(git -C "$ROOT" branch --show-current)" = "feature/agency-wp-car-yard-private-20261022"
T="$(mktemp -d /tmp/empire_agency_combined_XXXXXXXX)"
DBPID=''
WEBPID=''
PG_RUNNING=0
cleanup() {
  rc=$?
  trap - EXIT
  if [[ -n "$WEBPID" ]]; then kill "$WEBPID" 2>/dev/null || true; wait "$WEBPID" 2>/dev/null || true; fi
  if [[ -n "$DBPID" ]]; then kill "$DBPID" 2>/dev/null || true; wait "$DBPID" 2>/dev/null || true; fi
  if [[ "$PG_RUNNING" == 1 ]]; then
    /usr/lib/postgresql/18/bin/pg_ctl -D "$T/pgdata" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ -d "$T" && "$T" == /tmp/empire_agency_combined_* && "$(stat -c '%a' "$T")" == 700 ]]; then
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
# Build independent real PostgreSQL 18 instance for the ORIGINAL canonical 041 SQL.
# No TCP listener. The only account records are isolated, fictional fixtures.
test "$YARD_BASE_URL" != ""
/usr/lib/postgresql/18/bin/initdb -D "$T/pgdata" --encoding=UTF8 --locale=C \
 --auth-local=trust --auth-host=reject --no-instructions > "$T/pg-init.log" 2>&1
export PGHOST="$T"
export PGPORT="$(python3 - <<'PY_PGPORT'
import socket
s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()
PY_PGPORT
)"
export PGUSER=ubuntu
/usr/lib/postgresql/18/bin/pg_ctl -D "$T/pgdata" -l "$T/pg.log" \
 -o "-c listen_addresses='' -c unix_socket_directories=$T -c port=$PGPORT -c fsync=off" \
 -w start > "$T/pg-start.log" 2>&1
PG_RUNNING=1
if ss -lnt | grep -q "127.0.0.1:$PGPORT "; then echo PG_TCP_REFUSED; exit 9; fi
psql -X -q -v ON_ERROR_STOP=1 -d postgres <<'PG_ROLES'
CREATE ROLE empiredb_migrator;
GRANT empiredb_migrator TO ubuntu;
CREATE ROLE empiredb_app;
CREATE ROLE empiredb_readonly;
CREATE ROLE empiredb_tenant_reader;
CREATE ROLE empire_revenue_crm_reader;
CREATE ROLE empire_crm_membership_login LOGIN;
PG_ROLES
createdb crm_membership_fixture
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture -c \
 "GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator" >/dev/null
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture \
 -f "$ROOT/migrations/empiredb/041_crm_membership_authority.sql" > "$T/pg-041.log"
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture -c \
 "GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid) TO empire_crm_membership_login" >/dev/null
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture <<'PG_MEMBER'
INSERT INTO public.empire_crm_tenant_memberships
 (tenant_id,subject,role,status,evidence_ref,verified_at,valid_until,revoked_at)
VALUES ('510152ee-21b1-4d88-af83-3937718b4236'::uuid,
        'synthetic:agency-owner','owner','active','synthetic-combined-fixture',
        CURRENT_TIMESTAMP-INTERVAL '1 day',CURRENT_TIMESTAMP+INTERVAL '1 day',NULL);
PG_MEMBER
mkdir -m 700 "$T/connector-secrets"
cp -- "$YARD_MCP_SECRET_FILE" "$T/connector-secrets/agency-wp-test-credential"
chmod 600 "$T/connector-secrets/agency-wp-test-credential"
export PYTHONPATH="$ROOT"
export YARD_COMBINED_ROOT="$T"

# WordPress and PostgreSQL are now BOTH running inside this single stage.
export YARD_MCP_APP_PASSWORD="$(cat "$YARD_MCP_SECRET_FILE")"
node "$ROOT/scripts/agency_mcp_live_wp_e2e/combined_real_wp_mcp_pg.mjs" > "$T/combined_mcp.json"
php_safe "$ROOT/scripts/agency_mcp_live_wp_e2e/revoke_api.php" > "$T/revoke.json"
node "$ROOT/scripts/agency_mcp_live_wp_e2e/verify_revoke.mjs" > "$T/revocation_verified.json"
unset YARD_MCP_APP_PASSWORD
rm -f -- "$YARD_MCP_SECRET_FILE" "$YARD_MCP_UUID_FILE" \
 "$T/connector-secrets/agency-wp-test-credential"

python3 - "$T" "$ROOT" <<'PY_REPORT'
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
sandbox,root=map(Path,sys.argv[1:])
out=root/'docs/commercial/EMPIRE_AGENCY_COMBINED_PG041_MCP_WORDPRESS_REVOCATION_20261023.json'
if out.exists() or out.is_symlink():
    raise RuntimeError("Refusing overwrite of evidence")
mcp=json.loads((sandbox/'combined_mcp.json').read_text())
setup=json.loads((sandbox/'api_setup.json').read_text())
revocation=json.loads((sandbox/'revocation_verified.json').read_text())
assert mcp['status']=='COMBINED_REAL_PG041_MCP_WP_MARIADB_REVOCATION_PASS'
assert mcp['checks_passed']==len(mcp['checks']) and all(mcp['checks'].values())
assert setup['status']=='SYNTHETIC_WORDPRESS_APP_PASSWORD_CREATED'
assert revocation['status']=='WORDPRESS_EPHEMERAL_CREDENTIAL_REVOCATION_CONFIRMED'
assert revocation['http_status']==401
paths=[
 'scripts/agency_mcp_live_wp_e2e/combined_authority_bridge.py',
 'scripts/agency_mcp_live_wp_e2e/combined_real_wp_mcp_pg.mjs',
 'scripts/agency_mcp_live_wp_e2e/run_combined_pg_wp_mcp_e2e.sh',
 'empire_os/agency_canonical_membership.py',
 'empire_os/agency_connector_authority.py',
 'empire_os/agency_connector_preflight.py',
 'empire_os/agency_connector_credentials.py',
 'migrations/empiredb/041_crm_membership_authority.sql',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/revocation-guard.mjs',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/server.mjs',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-integration-bridge/empire-agency-integration-bridge.php',
]
result={
 'schema_version':'empire.agency.combined_mcp_041_wp_mysql.v1',
 'status':'COMBINED_REAL_POSTGRES_041_MCP_WORDPRESS_MARIADB_REVOCATION_PASS',
 'timestamp_utc':datetime.now(timezone.utc).isoformat(),
 'tests':mcp['checks'],'checks_passed':mcp['checks_passed'],
 'native_postgresql_041':True,'native_wordpress_mariadb':True,
 'same_mcp_session_proved_revocation':True,
 'membership_source':'isolated_real_postgresql_original_041_fixture',
 'wordpress_api_origin':'127.0.0.1_loopback_only',
 'postgresql_transport':'private_unix_socket_no_tcp',
 'mariadb_transport':'private_unix_socket_no_tcp',
 'site_grants':'synthetic_fixture_not_canonical_site_registry',
 'issuer':'ephemeral_test_only_ed25519',
 'secret_storage':'owner_only_temp_file_not_managed_vault',
 'original_wordpress_app_password_revoked':True,
 'revoked_wp_auth_response':401,
 'production_empiredb_accessed':False,'real_user_revoked':False,
 'real_client_or_crm_data_accessed':False,'production_changes':False,
 'public_booking_payments_or_outbound':False,
 'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
}
with out.open('x') as file:
    json.dump(result,file,indent=2,sort_keys=True)
    file.write('\n')
print(json.dumps({'status':result['status'],'checks':result['checks_passed'],
  'revoked_wordpress_http':401,'production_changes':False},sort_keys=True))
PY_REPORT
echo COMBINED_DISPOSABLE_PG_WP_MCP_TEST_CLEANUP_ON_EXIT
