#!/usr/bin/env bash
# EmpireOS Predictive Cloud V4: real Redis-engine local-only acceptance.
# Never install/start a host service or touch Redis Cloud / production DB.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
binary="${EMPIRE_V4_REDIS_SERVER_BIN:-}"
library="${EMPIRE_V4_REDIS_LIBRARY_DIR:-}"
[[ -n "$binary" && -x "$binary" ]] || {
  echo 'V4_REAL_REDIS_SERVER_BINARY_NOT_PROVIDED'; exit 9;
}
# Redis's packaged redis-server is a multicall symlink. Check its resolved
# executable for provenance but invoke *the symlink* (argv[0]=redis-server),
# otherwise Redis mistakenly enters its RDB checker mode.
resolved="$(realpath "$binary")"
[[ "$binary" == /tmp/empire-v4-redis-package.*/root/usr/bin/redis-server
   && "$resolved" == /tmp/empire-v4-redis-package.*/root/usr/bin/redis-check-rdb ]] || {
  echo 'V4_REFUSED_UNREVIEWED_REDIS_SERVER_BINARY_PATH'; exit 9;
}
[[ -n "$library" && -d "$library" ]] || {
  echo 'V4_REAL_REDIS_LIBRARY_DIRECTORY_NOT_PROVIDED'; exit 9;
}
library="$(realpath "$library")"
[[ "$library" == /tmp/empire-v4-redis-package.*/root/usr/lib/x86_64-linux-gnu ]] || {
  echo 'V4_REFUSED_UNREVIEWED_REDIS_LIBRARY_PATH'; exit 9;
}
[[ -f "$library/liblzf.so.1" ]] || {
  echo 'V4_LIBLZF_DISPOSABLE_RUNTIME_MISSING'; exit 9;
}

runtime="$(mktemp -d /tmp/empire-v4-redis-run.XXXXXX)"
chmod 700 "$runtime"
socket="$runtime/redis.sock"
pid=''
cleanup(){
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
  rm -rf -- "$runtime"
}
trap cleanup EXIT
export LD_LIBRARY_PATH="$library"
"$binary" \
  --port 0 \
  --unixsocket "$socket" \
  --unixsocketperm 700 \
  --bind 127.0.0.1 \
  --protected-mode yes \
  --daemonize no \
  --save "" \
  --appendonly no \
  --maxmemory 32mb \
  --maxmemory-policy noeviction \
  --databases 1 \
  --dir "$runtime" \
  --logfile "$runtime/redis.log" \
  --pidfile "$runtime/redis.pid" >"$runtime/server.stdout" 2>&1 &
pid=$!

for _ in {1..80}; do
  [[ -S "$socket" ]] && break
  kill -0 "$pid" 2>/dev/null || {
    echo 'V4_REAL_REDIS_SERVER_REFUSED_START'
    tail -35 "$runtime/redis.log" 2>/dev/null || true
    exit 7
  }
  sleep 0.05
done
[[ -S "$socket" ]] || { echo 'V4_LOCAL_UNIX_SOCKET_DID_NOT_APPEAR'; exit 7; }
[[ "$(stat -c '%a' "$socket")" == 700 ]] || {
  echo 'V4_UNIX_SOCKET_PERMISSIONS_NOT_PRIVATE'; exit 7;
}
# No persistence, no TCP listener, no system Redis client, no real money.
EMPIRE_V4_REDIS_FIXTURE_SOCKET="$socket" \
  PYTHONPATH=. \
  timeout 22 /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py
echo 'V4_LOCAL_REAL_REDIS_ACCEPTANCE_COMPLETE redis_cloud_connected=false production_touched=false'
