#!/usr/bin/env bash
set -euo pipefail

# EmpireDB pgBackRest backup/restore proof.
# Root-run only. Uses an encrypted LOCAL repository for mechanical restore proof.
# It deliberately does NOT enable archive_mode or change the canonical backend.
# Off-node durability remains a separate cutover gate.

STANZA="empiredb"
PG_CLUSTER="18 main"
PGDATA="/var/lib/postgresql/18/main"
CONFIG="/etc/pgbackrest/empiredb.conf"
REPO="/var/backups/empiredb/pgbackrest"
RESTORE="/var/lib/postgresql/18/empiredb-restore-proof"
RESTORE_PORT="55432"
PG_CTL="/usr/lib/postgresql/18/bin/pg_ctl"
TEMP_LOG="/tmp/empiredb-restore-proof.log"

[[ "$(id -u)" -eq 0 ]] || { echo "run as root"; exit 1; }

for cmd in pgbackrest pg_ctlcluster psql openssl runuser; do
  command -v "$cmd" >/dev/null || { echo "missing command: $cmd"; exit 1; }
done
[[ -x "$PG_CTL" ]] || { echo "missing $PG_CTL"; exit 1; }

install -d -m 0750 -o postgres -g postgres "$REPO"
install -d -m 0750 -o postgres -g postgres /etc/pgbackrest

if [[ ! -f "$CONFIG" ]]; then
  CIPHER_PASS="$(openssl rand -base64 48)"
  umask 077
  cat >"$CONFIG" <<EOF
[$STANZA]
pg1-path=$PGDATA

[global]
repo1-type=posix
repo1-path=$REPO
repo1-cipher-type=aes-256-cbc
repo1-cipher-pass=$CIPHER_PASS
repo1-retention-full=2
process-max=4
log-level-console=info
log-level-file=info
EOF
  chown postgres:postgres "$CONFIG"
  chmod 0600 "$CONFIG"
fi

# Ensure the dedicated config stays private and does not drift to another path.
[[ "$(stat -c '%U:%G:%a' "$CONFIG")" == "postgres:postgres:600" ]] || {
  echo "unsafe pgBackRest config permissions"; exit 1;
}
grep -Fxq "pg1-path=$PGDATA" "$CONFIG"
grep -Fxq "repo1-path=$REPO" "$CONFIG"
grep -Fxq "repo1-cipher-type=aes-256-cbc" "$CONFIG"

runuser -u postgres -- pgbackrest   --config="$CONFIG" --stanza="$STANZA" stanza-create

MAIN_WAS_ACTIVE=0
POOL_WAS_ACTIVE=0
systemctl is-active --quiet postgresql@18-main && MAIN_WAS_ACTIVE=1 || true
systemctl is-active --quiet pgbouncer && POOL_WAS_ACTIVE=1 || true

restore_started=0
cleanup() {
  set +e
  if [[ "$restore_started" -eq 1 ]]; then
    runuser -u postgres -- "$PG_CTL" -D "$RESTORE" -m fast stop >/dev/null 2>&1
  fi
  rm -rf --one-file-system "$RESTORE"
  if [[ "$MAIN_WAS_ACTIVE" -eq 1 ]]; then
    pg_ctlcluster 18 main start >/dev/null 2>&1 || true
  fi
  if [[ "$POOL_WAS_ACTIVE" -eq 1 ]]; then
    systemctl start pgbouncer >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# EmpireDB is still non-canonical, so an offline backup avoids enabling WAL
# archiving before the required off-node repository exists.
systemctl stop pgbouncer || true
pg_ctlcluster 18 main stop

runuser -u postgres -- pgbackrest   --config="$CONFIG" --stanza="$STANZA"   --type=full --no-online backup

pg_ctlcluster 18 main start
systemctl start pgbouncer

runuser -u postgres -- pgbackrest   --config="$CONFIG" --stanza="$STANZA"   --output=text --verbose verify

rm -rf --one-file-system "$RESTORE"
install -d -m 0700 -o postgres -g postgres "$RESTORE"

runuser -u postgres -- pgbackrest   --config="$CONFIG" --stanza="$STANZA"   --pg1-path="$RESTORE" --archive-mode=off restore

# Boot the restored copy on an isolated port/socket. Command-line settings have
# higher precedence than Debian's live config, especially data_directory.
runuser -u postgres -- "$PG_CTL"   -D "$RESTORE"   -l "$TEMP_LOG"   -o "-c config_file=/etc/postgresql/18/main/postgresql.conf -c data_directory=$RESTORE -c port=$RESTORE_PORT -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp -c archive_mode=off"   start
restore_started=1

for _ in $(seq 1 30); do
  if runuser -u postgres -- psql       -h /tmp -p "$RESTORE_PORT" -d empiredb -Atqc "SELECT 1"       >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

PROSPECTS="$(runuser -u postgres -- psql   -h /tmp -p "$RESTORE_PORT" -d empiredb -Atqc   "SELECT count(*) FROM public.prospects")"
SCHEMA_TABLES="$(runuser -u postgres -- psql   -h /tmp -p "$RESTORE_PORT" -d empiredb -Atqc   "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")"

[[ "$PROSPECTS" == "32899" ]] || {
  echo "restore prospect count mismatch: $PROSPECTS"; exit 1;
}
[[ "$SCHEMA_TABLES" -ge 40 ]] || {
  echo "restore public table count too low: $SCHEMA_TABLES"; exit 1;
}

runuser -u postgres -- "$PG_CTL" -D "$RESTORE" -m fast stop
restore_started=0
rm -rf --one-file-system "$RESTORE"

systemctl is-active --quiet postgresql@18-main
systemctl is-active --quiet pgbouncer

INFO_JSON="$(runuser -u postgres -- pgbackrest   --config="$CONFIG" --stanza="$STANZA" --output=json info)"

python3 - <<PY
import json
info = json.loads('''$INFO_JSON''')
assert info and info[0]["status"]["code"] == 0, info
print(json.dumps({
    "schema_version": "empire.pgbackrest-restore-proof.v1",
    "stanza": "$STANZA",
    "repository": "encrypted_local_posix",
    "repository_cipher": "aes-256-cbc",
    "archive_mode_changed": False,
    "off_node_repository_verified": False,
    "restored_database": "empiredb",
    "restored_prospects": int("$PROSPECTS"),
    "restored_public_tables": int("$SCHEMA_TABLES"),
    "live_postgres_active": True,
    "pgbouncer_active": True,
    "verified": True,
}, sort_keys=True))
PY
