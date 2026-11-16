#!/usr/bin/env bash
# Offline exact libpq SCRAM verification for original REV052 explicit password.
# An intact selector plus missing password replicates founder's NO PASSWORD.
# No live passwords, roles, data, network listener, service or backups.
set -euo pipefail
export PATH=/usr/lib/postgresql/18/bin:/usr/bin:/bin
test "$(id -u)" != 0 || { echo REFUSE_ROOT_DISPOSABLE_CLUSTER; exit 2; }
tmp="$(mktemp -d /tmp/empire-rev052-scram-XXXXXXX)"
trap 'pg_ctl -D "$tmp/db" -m immediate stop >/dev/null 2>&1 || :; rm -rf "$tmp"' EXIT
initdb -D "$tmp/db" -U ubuntu -A trust -E UTF8 --no-sync >/dev/null
mkdir -m 700 "$tmp/sock"
pg_ctl -D "$tmp/db" -l "$tmp/log" \
 -o "-c listen_addresses= -c unix_socket_directories=$tmp/sock -c port=55492" start >/dev/null
PGHOST="$tmp/sock" PGPORT=55492 psql -X -qAt -v ON_ERROR_STOP=1 \
 -d postgres -c "CREATE ROLE synthetic_rev052_evidence_login LOGIN PASSWORD 'only-for-disposable-regression';"
PGHOST="$tmp/sock" PGPORT=55492 createdb empiredb
printf '%s\n' "local empiredb synthetic_rev052_evidence_login scram-sha-256" \
 | cat - "$tmp/db/pg_hba.conf" > "$tmp/hba"
cp "$tmp/hba" "$tmp/db/pg_hba.conf"
chmod 600 "$tmp/db/pg_hba.conf"
pg_ctl -D "$tmp/db" reload >/dev/null
# Matches ALL FOUR selectors yet contains no supplied password.
printf '%s\n' "$tmp/sock:55492:empiredb:synthetic_rev052_evidence_login:" \
 > "$tmp/incomplete.pgpass"
chmod 600 "$tmp/incomplete.pgpass"
PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B - "$tmp" <<'PY'
from pathlib import Path
import sys
import psycopg
from psycopg.conninfo import make_conninfo
from scripts.activate_predictive_native_reader_existing_login_20261116 import (
    _safe_error_category,
)
path=Path(sys.argv[1])
conn=dict(host=str(path/"sock"),port=55492,dbname="empiredb",
          user="synthetic_rev052_evidence_login",connect_timeout=5)
dsn_bad=make_conninfo(**conn,passfile=str(path/"incomplete.pgpass"))
try:
    with psycopg.connect(dsn_bad) as unused:
        raise AssertionError("NO PASSWORD SHOULD HAVE FAILED")
except psycopg.OperationalError as exc:
    assert _safe_error_category(exc)=="PGPASS_NO_MATCHING_PASSWORD",repr(
        _safe_error_category(exc))
print("MATCHING_PGPASS_FIELDS_BUT_NO_PASSWORD_REPRODUCED=PASS")
# Existing REV053 passes the original password directly to SCRAM.
dsn_good=make_conninfo(**conn,password="only-for-disposable-regression")
with psycopg.connect(dsn_good) as db:
    with db.cursor() as cur:
        cur.execute("SET TRANSACTION READ ONLY")
        cur.execute("SELECT current_database(),session_user,"
                    "current_setting('transaction_read_only')")
        assert cur.fetchone()==(
            "empiredb","synthetic_rev052_evidence_login","on")
print("EXPLICIT_REV052_PASSWORD_AUTHENTICATED_SCRAM_READONLY=PASS")
PY
