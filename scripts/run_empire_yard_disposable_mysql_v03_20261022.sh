#!/usr/bin/env bash
# One-shot, user-scoped, network-disabled MariaDB concurrency test.
set -euo pipefail
umask 077
test "$(whoami)" = ubuntu
T="$(mktemp -d /tmp/empire_yard_mysql_v03_XXXXXXXX)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
test "$(stat -c %a "$T")" = 700
SOCK="$T/sock"
PIDFILE="$T/mysql.pid"
LOGFILE="$T/mysql.log"
PHP="$T/root/usr/bin/php8.5"
EXT="$T/root/usr/lib/php/20250925"
export LD_LIBRARY_PATH="$T/root/usr/lib/x86_64-linux-gnu"
php_safe() {
 "$PHP" -n -d "extension=$EXT/mysqlnd.so" -d "extension=$EXT/mysqli.so" "$@"
}
TEST="$ROOT/tests/verify_empire_car_yard_real_mariadb_20261022.php"
dbpid=''
cleanup() {
  code=$?
  trap - EXIT
  if [[ -n "$dbpid" ]]; then
    kill "$dbpid" 2>/dev/null || true
    wait "$dbpid" 2>/dev/null || true
  fi
  if [[ "$T" == /tmp/empire_yard_mysql_v03_* && -d "$T" && "$(stat -c %a "$T")" == 700 ]]; then
    rm -rf -- "$T"
  fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -m 700 "$T/root"
(
  cd "$T"
  timeout 90s apt download mariadb-server-core mariadb-server mariadb-client-core php8.5-cli php8.5-mysql php8.5-common libargon2-1 >/dev/null 2>&1
  for f in ./*.deb; do dpkg-deb -x "$f" root; done
)
mkdir -m 700 "$T/data"
export PATH="$T/root/usr/bin:$PATH"
timeout 60s "$T/root/usr/bin/mariadb-install-db" --no-defaults   "--basedir=$T/root/usr" "--datadir=$T/data"   --auth-root-authentication-method=normal --skip-test-db --user=ubuntu >/dev/null 2>&1
echo "DISPOSABLE_USER_SCOPED_PHP_MARIADB_INITIALIZED"
for src in "$TEST" "$ROOT"/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/*.php "$ROOT"/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/*.php; do
  php_safe -l "$src" >/dev/null
done
echo "NATIVE_PHP_LINT_PASS"
"$T/root/usr/sbin/mariadbd" --no-defaults \
  "--basedir=$T/root/usr" "--datadir=$T/data" \
  "--socket=$SOCK" "--pid-file=$PIDFILE" \
  "--plugin-dir=$T/root/usr/lib/mysql/plugin" \
  "--character-sets-dir=$T/root/usr/share/mariadb/charsets" \
  "--lc-messages-dir=$T/root/usr/share/mariadb" \
  "--tmpdir=$T" "--log-error=$LOGFILE" \
  --skip-networking --skip-log-bin \
  --innodb-buffer-pool-size=32M --max-connections=8 \
  --table-open-cache=128 --user=ubuntu &
dbpid=$!
ready=0
for i in $(seq 1 100); do
  if "$T/root/usr/bin/mariadb" --no-defaults --socket="$SOCK" -u root -Nse "SELECT 1" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep .1
done
if [[ $ready != 1 ]]; then
  echo "DISPOSABLE_MYSQL_START_FAILURE"
  tail -25 "$LOGFILE" || true
  exit 2
fi
echo "MARIADB_STARTED_SOCKET_ONLY"
"$T/root/usr/bin/mariadb" --no-defaults --socket="$SOCK" -u root \
 -e "CREATE DATABASE empire_yard_synthetic CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
mkdir -m 700 "$T/barrier"
php_safe "$TEST" schema "$SOCK" "$T/barrier/schema"
php_safe "$TEST" hold "$SOCK" "$T/barrier/a" > "$T/a.json" 2>"$T/a.err" &
a=$!
php_safe "$TEST" hold "$SOCK" "$T/barrier/b" > "$T/b.json" 2>"$T/b.err" &
b=$!
bars=0
for i in $(seq 1 90); do
  if [[ -f "$T/barrier/a.ready" && -f "$T/barrier/b.ready" ]]; then
    bars=1; break
  fi
  sleep .05
done
if [[ $bars != 1 ]]; then
  echo "CONCURRENCY_BARRIER_FAILED"
  cat "$T/a.err" "$T/b.err" || true
  exit 3
fi
touch "$T/barrier/go"
wait "$a"; wait "$b"
echo "CONCURRENT_ATTEMPT_A=$(cat "$T/a.json")"
echo "CONCURRENT_ATTEMPT_B=$(cat "$T/b.json")"
php_safe "$TEST" verify "$SOCK" "$T/barrier/check"
php_safe "$TEST" cancel_rebook "$SOCK" "$T/barrier/check"
python3 - "$T/a.json" "$T/b.json" <<'PY'
import json,sys
a,b=[json.load(open(p)) for p in sys.argv[1:]]
assert sorted([a['result'],b['result']])==['ACCEPTED','DENIED'],(a,b)
print('REAL_MARIADB_TWO_PROCESS_CONCURRENCY_PASS')
PY
REPORT="$ROOT/docs/commercial/EMPIRE_CAR_YARD_V03_MARIADB_CONCURRENCY_20261022.json"
test ! -e "$REPORT"
db_version="$("$T/root/usr/bin/mariadb" --no-defaults --socket="$SOCK" -u root -Nse 'SELECT VERSION()')"
php_version="$(php_safe -r 'echo PHP_VERSION;')"
python3 - "$T/a.json" "$T/b.json" "$REPORT" "$db_version" "$php_version" "$ROOT" <<'PY'
import sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
a,b=[json.loads(Path(v).read_text()) for v in sys.argv[1:3]]
assert sorted([a['result'],b['result']]) == ['ACCEPTED','DENIED']
target=Path(sys.argv[3])
root=Path(sys.argv[6])
files=[
 'tests/verify_empire_car_yard_real_mariadb_20261022.php',
 'scripts/run_empire_yard_disposable_mysql_v03_20261022.sh',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/class-empire-yard-booking-store.php',
 'prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/class-empire-yard-booking-rules.php'
]
receipt={
 'schema_version':'empire.agency.car_yard_v03_real_mariadb_concurrency.v1',
 'status':'REAL_MARIADB_TWO_PROCESS_INNODB_CONCURRENCY_PASS',
 'observed_utc':datetime.now(timezone.utc).isoformat(),
 'platform':'ISOLATED_USER_SCOPED_MARIADB_UNIX_SOCKET_NO_TCP',
 'mariadb_version':sys.argv[4],'php_version':sys.argv[5],
 'independent_simultaneous_php_processes':2,
 'accepted_attempts':1,'denied_conflicting_attempts':1,
 'bookings_after_concurrency':1,'occupied_quarter_hour_slots':4,
 'audit_events_after_concurrency':1,
 'cancel_rebook_passed':True,'audits_after_cancel_rebook':3,
 'source_sha256':{k:hashlib.sha256((root/k).read_bytes()).hexdigest() for k in files},
 'synthetic_only':True,'production_changes':False,'mysql_tcp_enabled':False,
 'wordpress_with_mysql_tested':False,'browser_tested':False,
 'temporary_database_teardown_registered':True
}
with target.open('x') as f: json.dump(receipt,f,sort_keys=True,indent=2); f.write(chr(10))
print('MYSQL_RECEIPT_RECORDED',str(target))
PY
echo "MYSQL_SOCKET_NETWORKING_DISABLED_AND_TEARDOWN_ON_EXIT"
