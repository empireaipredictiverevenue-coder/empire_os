#!/usr/bin/env bash
# Empire Predictive Cloud V4.6: ephemeral Redis 8 AOF restart/crash
# + disposable PostgreSQL 18 canonical held receipt reconciliation.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?temporary PostgreSQL host required}" "${PGPORT:?temporary PostgreSQL port required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
package_dir="$(mktemp -d /tmp/empire-v46-redis-package.XXXXXX)"
run_dir="$(mktemp -d /tmp/empire-v4-redis-run.XXXXXX)"
cli="$package_dir/root/usr/bin/redis-cli"
server="$package_dir/root/usr/bin/redis-server"
check_owned_pid(){
 local p="$1"
 [[ "$p" =~ ^[0-9]+$ && -r "/proc/$p/cmdline" ]] \
  && tr '\0' ' ' <"/proc/$p/cmdline" | grep -Fq "$run_dir"
}
stop_owned(){
 if [[ -f "$run_dir/redis.pid" ]]; then
  local p
  p="$(cat "$run_dir/redis.pid" 2>/dev/null || true)"
  if check_owned_pid "$p"; then kill "$p" 2>/dev/null || true; fi
 fi
}
cleanup(){
 if [[ -S "$run_dir/redis.sock" && -x "$cli" ]]; then
  LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu" \
   "$cli" -s "$run_dir/redis.sock" shutdown nosave >/dev/null 2>&1 || true
 fi
 stop_owned
 rm -rf -- "$package_dir" "$run_dir"
}
trap cleanup EXIT
psql -Xq -v ON_ERROR_STOP=1 -d postgres -c \
 'CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS'
createdb empire_v4_outbox_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -c \
 'GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator'
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f \
 migrations/empiredb/064_predictive_v4_projection_outbox_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v4_outbox_fixture -f \
 migrations/empiredb/065_predictive_v4_advisory_replay_receipts_held.sql
(
 cd "$package_dir"
 timeout 45 apt download redis-server redis-tools liblzf1 >/dev/null
 mkdir root
 for deb in ./*.deb; do dpkg-deb -x "$deb" root; done
)
test -x "$server" && test -x "$cli"
export LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu"
"$server" --version | grep -q 'v=8\.'
start_redis(){
 "$server" --port 0 --unixsocket "$run_dir/redis.sock" --unixsocketperm 700 \
 --dir "$run_dir" --save "" --appendonly yes --appendfsync always \
 --maxmemory 32mb --maxmemory-policy noeviction --protected-mode yes \
 --daemonize yes --pidfile "$run_dir/redis.pid" --logfile "$run_dir/redis.log"
 for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if [[ -S "$run_dir/redis.sock" ]] \
   && "$cli" -s "$run_dir/redis.sock" ping 2>/dev/null | grep -qx PONG; then break; fi
  sleep .15
 done
 [[ "$("$cli" -s "$run_dir/redis.sock" ping)" == PONG ]]
 [[ "$("$cli" -s "$run_dir/redis.sock" config get port | tail -1)" == 0 ]]
 [[ "$("$cli" -s "$run_dir/redis.sock" config get appendonly | tail -1)" == yes ]]
 [[ "$("$cli" -s "$run_dir/redis.sock" config get appendfsync | tail -1)" == always ]]
 [[ "$("$cli" -s "$run_dir/redis.sock" config get save | tail -1)" == '' ]]
}
stop_graceful(){
 "$cli" -s "$run_dir/redis.sock" shutdown nosave
 for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  [[ ! -S "$run_dir/redis.sock" ]] && break
  sleep .15
 done
 [[ ! -S "$run_dir/redis.sock" ]]
}
stop_crash(){
 local p
 p="$(cat "$run_dir/redis.pid")"
 check_owned_pid "$p" || { echo V46_REFUSE_KILL_UNOWNED_PROCESS; return 9; }
 kill -KILL "$p"
 for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if ! kill -0 "$p" 2>/dev/null; then break; fi
  sleep .15
 done
 # Redis may leave its Unix socket file after SIGKILL; only this fixture owns it.
 if [[ -S "$run_dir/redis.sock" ]]; then rm -- "$run_dir/redis.sock"; fi
}
phase(){
 EMPIRE_V46_REDIS_FIXTURE_SOCKET="$run_dir/redis.sock" \
 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/rehearse_predictive_cloud_v46_restart_20261024.py "$1"
}
start_redis
phase before_graceful
stop_graceful
echo 'V46_GRACEFUL_SERVER_RESTART_BEGIN'
start_redis
phase after_graceful
stop_crash
echo 'V46_FORCED_SERVER_CRASH_BEGIN'
start_redis
phase after_crash
[[ -d "$run_dir/appendonlydir" ]]
echo 'V46_AOF_RESTART_GAUNTLET_COMPLETE redis_tcp=0 production_empiredb=false real_source_authority=false money_moved=false'
