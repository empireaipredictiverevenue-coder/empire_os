#!/usr/bin/env bash
# Original EmpireOS Predictive Cloud V4 Redis 8 *REAL SERVER* acceptance.
# One-shot, isolated, unprivileged, no TCP, no production install/service.
# Downloads official Ubuntu .deb files to /tmp WITHOUT apt install or sudo.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
package_dir="$(mktemp -d /tmp/empire-v4-redis-package.XXXXXX)"
run_dir="$(mktemp -d /tmp/empire-v4-redis-run.XXXXXX)"
cleanup() {
  if [[ -S "$run_dir/redis.sock" && -x "$package_dir/root/usr/bin/redis-cli" ]]; then
    LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu" \
      "$package_dir/root/usr/bin/redis-cli" -s "$run_dir/redis.sock" \
      shutdown nosave >/dev/null 2>&1 || true
  fi
  if [[ -f "$run_dir/redis.pid" ]]; then
    redis_pid="$(cat "$run_dir/redis.pid" 2>/dev/null || true)"
    if [[ "$redis_pid" =~ ^[0-9]+$ ]]; then
      # Kill ONLY the child whose /proc cmdline includes our unique run dir.
      if [[ -r "/proc/$redis_pid/cmdline" ]] && tr '\0' ' ' <"/proc/$redis_pid/cmdline" | grep -Fq "$run_dir"; then
        kill "$redis_pid" 2>/dev/null || true
      fi
    fi
  fi
  rm -rf -- "$package_dir" "$run_dir"
}
trap cleanup EXIT
echo "V4_TEMP_PACKAGE_EXTRACTION_ONLY=yes"
(
  cd "$package_dir"
  timeout 45 apt download redis-server redis-tools liblzf1 >/dev/null
  mkdir root
  for deb in ./*.deb; do dpkg-deb -x "$deb" root; done
)
server="$package_dir/root/usr/bin/redis-server"
cli="$package_dir/root/usr/bin/redis-cli"
test -x "$server"
test -x "$cli"
export LD_LIBRARY_PATH="$package_dir/root/usr/lib/x86_64-linux-gnu"
"$server" --version
"$server" --port 0 --unixsocket "$run_dir/redis.sock" --unixsocketperm 700 \
  --dir "$run_dir" --save "" --appendonly no \
  --maxmemory 32mb --maxmemory-policy noeviction --protected-mode yes \
  --daemonize yes --pidfile "$run_dir/redis.pid" --logfile "$run_dir/redis.log"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  [[ -S "$run_dir/redis.sock" ]] && break
  sleep .1
done
if [[ ! -S "$run_dir/redis.sock" ]]; then
  cat "$run_dir/redis.log" || true
  echo "V4_REAL_REDIS_TEMPORARY_STARTUP_FAILED"
  exit 9
fi
test "$("$cli" -s "$run_dir/redis.sock" ping)" = PONG
test "$("$cli" -s "$run_dir/redis.sock" config get port | tail -1)" = 0
echo "V4_REDIS_LOCAL_UNIX_SOCKET_ONLY=yes"
EMPIRE_V4_REDIS_FIXTURE_SOCKET="$run_dir/redis.sock" \
  PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  scripts/rehearse_predictive_cloud_v4_real_redis_20261024.py
echo "V4_REAL_REDIS_EPHEMERAL_RUN_COMPLETE production_touched=false service_installed=false"
