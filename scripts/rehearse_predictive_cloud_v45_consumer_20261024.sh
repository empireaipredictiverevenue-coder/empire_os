#!/usr/bin/env bash
# V4.5 real Redis consumer recovery + real ephemeral PG transaction proof.
# No production connection, no installed service, no TCP Redis, no live traffic.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?disposable PostgreSQL required}" "${PGPORT:?disposable PostgreSQL port required}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] && (( PGPORT >= 5433 )) || exit 9
pgdir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pgdir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
package_dir="$(mktemp -d /tmp/empire-v45-redis-package.XXXXXX)"
run_dir="$(mktemp -d /tmp/empire-v4-redis-run.XXXXXX)"
cleanup() {
 if [[ -S "$run_dir/redis.sock" && -x "$package_dir/root/usr/bin/redis-cli" ]]; then
  LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu" \
   "$package_dir/root/usr/bin/redis-cli" -s "$run_dir/redis.sock" shutdown nosave >/dev/null 2>&1 || true
 fi
 if [[ -f "$run_dir/redis.pid" ]]; then
  pid="$(cat "$run_dir/redis.pid" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r "/proc/$pid/cmdline" ]] \
    && tr '\0' ' ' <"/proc/$pid/cmdline" | grep -Fq "$run_dir"; then
    kill "$pid" 2>/dev/null || true
  fi
 fi
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
server="$package_dir/root/usr/bin/redis-server"
cli="$package_dir/root/usr/bin/redis-cli"
test -x "$server" && test -x "$cli"
export LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu"
"$server" --port 0 --unixsocket "$run_dir/redis.sock" --unixsocketperm 700 \
 --dir "$run_dir" --save "" --appendonly no --maxmemory 32mb \
 --maxmemory-policy noeviction --protected-mode yes \
 --daemonize yes --pidfile "$run_dir/redis.pid" --logfile "$run_dir/redis.log"
for i in 1 2 3 4 5 6 7 8 9 10; do
 [[ -S "$run_dir/redis.sock" ]] && break
 sleep .1
done
[[ -S "$run_dir/redis.sock" ]]
[[ "$("$cli" -s "$run_dir/redis.sock" ping)" == PONG ]]
[[ "$("$cli" -s "$run_dir/redis.sock" config get port | tail -1)" == 0 ]]
[[ "$("$cli" -s "$run_dir/redis.sock" config get appendonly | tail -1)" == no ]]
EMPIRE_V45_REDIS_FIXTURE_SOCKET="$run_dir/redis.sock" \
 PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 scripts/rehearse_predictive_cloud_v45_consumer_20261024.py
echo 'V45_EPHEMERAL_CONSUMER_GAUNTLET_COMPLETE redis_tcp=0 production_empiredb=false systemd_installed=false'
