#!/usr/bin/env bash
# Rootless, loopback-only, disposable real WP 6.8 / PHP 8.5 / MariaDB browser and restore acceptance.
set -euo pipefail
umask 077
test "$(id -un)" = ubuntu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
test "$(git -C "$ROOT" branch --show-current)" = "feature/agency-wp-car-yard-private-20261022"
T="$(mktemp -d /tmp/empire_yard_react_v3_wp_XXXXXXXX)"
DBPID=''
WEBPID=''
cleanup() {
  rc=$?
  trap - EXIT
  if [[ -n "$WEBPID" ]]; then kill "$WEBPID" 2>/dev/null || true; wait "$WEBPID" 2>/dev/null || true; fi
  if [[ -n "$DBPID" ]]; then kill "$DBPID" 2>/dev/null || true; wait "$DBPID" 2>/dev/null || true; fi
  if [[ -d "$T" && "$T" == /tmp/empire_yard_react_v3_wp_* && "$(stat -c '%a' "$T")" == 700 ]]; then
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
mkdir -p "$YARD_SITE_DIR/wp-content/themes/empire-yard-atelier"
tar -C "$ROOT/prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier" --exclude=node_modules --exclude=.git -cf - . | tar -C "$YARD_SITE_DIR/wp-content/themes/empire-yard-atelier" -xf -
cp -a "$ROOT/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/." "$YARD_SITE_DIR/wp-content/plugins/empire-car-yard/"
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
php_safe "$ROOT/scripts/premium_wp_v1/bootstrap.php" > "$T/bootstrap.json"
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
node "$ROOT/scripts/premium_wp_v1/browser_acceptance_v3.cjs" > "$T/browser.json"
python3 - "$T/browser.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]));assert r['status']=='WORDPRESS_REACT_3D_BROWSER_ACCEPTANCE_PASS'
assert all(r['checks'].values())
print('WORDPRESS_BROWSER_ASSERTIONS_PASS',r['number_of_checks'])
PY
DB_SQL="$T/backup.sql"
"$T/root/usr/bin/mariadb-dump" --no-defaults -u root "--socket=$YARD_MYSQL_SOCKET" \
  --single-transaction --skip-lock-tables --default-character-set=utf8mb4 \
  "$YARD_DATABASE" > "$DB_SQL"
test -s "$DB_SQL"
tar -czf "$T/site-files.tar.gz" -C "$YARD_SITE_DIR" .
test -s "$T/site-files.tar.gz"
mkdir -m 700 "$T/restored"
tar -xzf "$T/site-files.tar.gz" -C "$T/restored"
export YARD_DATABASE=empire_yard_wp_restored
mariadb_cli -e "CREATE DATABASE $YARD_DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mariadb_cli "$YARD_DATABASE" < "$DB_SQL"
export YARD_RESTORED_SITE_DIR="$T/restored"
php_safe "$ROOT/scripts/premium_wp_v1/restore_verify.php" > "$T/restore.json"
python3 - "$T" "$ROOT" <<'PY'
import json,sys,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
tmp,root=map(Path,sys.argv[1:])
bootstrap=json.loads((tmp/'bootstrap.json').read_text())
browser=json.loads((tmp/'browser.json').read_text())
restore=json.loads((tmp/'restore.json').read_text())
assert bootstrap['status']=='NATIVE_WP_MYSQL_STAGE_BOOTSTRAP_PASS'
assert bootstrap['native_wpdb_innodb_ready'] is True
assert browser['status']=='WORDPRESS_REACT_3D_BROWSER_ACCEPTANCE_PASS'
assert all(browser['checks'].values())
assert restore['status']=='NATIVE_WP_MYSQL_RESTORE_PASS'
assert restore['booking_rows']==1 and restore['booking_audit_events']==3
snap_dst=root/'docs/commercial/car_yard_react_browser_evidence_v3'
snap_dst.mkdir(parents=True,exist_ok=True)
for name,meta in browser['screenshots'].items():
   src=tmp/'screenshots'/name
   assert hashlib.sha256(src.read_bytes()).hexdigest()==meta['sha256']
   dest=snap_dst/name
   if dest.exists(): raise RuntimeError('Refusing screenshot overwrite')
   shutil.copyfile(src,dest)
receipt=root/'docs/commercial/EMPIRE_CAR_YARD_REACT_MOTION_V3_BROWSER_ACCEPTANCE_20261023.json'
if receipt.exists(): raise RuntimeError('Refusing receipt overwrite')
manifest={}
for rel in ['scripts/premium_wp_v1/bootstrap.php','scripts/premium_wp_v1/browser_acceptance_v3.cjs','scripts/premium_wp_v1/restore_verify.php','scripts/premium_wp_v1/run_react_wordpress_design_v2.sh',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/main.jsx',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/ShowroomScene.jsx',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/src/inventory-enhance.js',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/dist/yard.js',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/dist/yard.css',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/vite.config.mjs',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/package-lock.json',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-yard-atelier/functions.php']:
  manifest[rel]=hashlib.sha256((root/rel).read_bytes()).hexdigest()
payload={
 'status':'WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS',
 'observed_utc':datetime.now(timezone.utc).isoformat(),
 'wordPress_mysql_same_runtime':True,
 'loopback_only_http':True,
 'mariadb_unix_socket_only':True,
 'wordpress_version':bootstrap['wordpress'],
 'php_version':bootstrap['php'],
 'browser_version':browser['browser'],
 'bootstrap':bootstrap,
 'browser_checks':browser['checks'],
 'browser_check_count':browser['number_of_checks'],
 'responsive':{'desktop':browser['wide'],'mobile':browser['narrow']},
 'screenshots':browser['screenshots'],
 'backup_sql_sha256':hashlib.sha256((tmp/'backup.sql').read_bytes()).hexdigest(),
 'backup_site_tar_sha256':hashlib.sha256((tmp/'site-files.tar.gz').read_bytes()).hexdigest(),
 'restore_verified':restore,
 'source_manifest_sha256':manifest,
 'external_requests_blocked':browser['external_requests_blocked'],
 'production_changes':False,'synthetic_data_only':True,
 'customer_bookings_enabled':False,'outbound_or_payments_enabled':False
}
with receipt.open('x') as f:json.dump(payload,f,indent=2,sort_keys=True);f.write('\n')
print('WORDPRESS_REACT_THREE_NATIVE_MYSQL_BROWSER_RESTORE_PASS',browser['number_of_checks'],'browser checks',restore['booking_audit_events'],'audit events')
PY
echo "DISPOSABLE_NATIVE_STAGING_COMPLETED_AND_TEARDOWN_ON_EXIT"
