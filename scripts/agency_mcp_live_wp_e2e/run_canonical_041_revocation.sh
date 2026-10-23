#!/usr/bin/env bash
# Isolated PostgreSQL 18 fixture for the EXISTING canonical EmpireDB 041 function.
# NEVER connect to or modify production EmpireDB. No TCP listener, no sudo.
set -euo pipefail
umask 077
test "$(id -un)" = ubuntu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
test "$(git -C "$ROOT" branch --show-current)" = "feature/agency-wp-car-yard-private-20261022"
T="$(mktemp -d /tmp/empire_agency_041_sql_XXXXXXXX)"
PGCTL=/usr/lib/postgresql/18/bin/pg_ctl
INITDB=/usr/lib/postgresql/18/bin/initdb
POSTGRES=/usr/lib/postgresql/18/bin/postgres
RUNNING=0
cleanup() {
  status=$?
  trap - EXIT
  if [[ "$RUNNING" == 1 ]]; then
    "$PGCTL" -D "$T/data" -m immediate stop >/dev/null 2>&1 || true
  fi
  if [[ "$T" == /tmp/empire_agency_041_sql_* && -d "$T" && "$(stat -c '%a' "$T")" == 700 ]]; then
    rm -rf -- "$T"
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$INITDB" -D "$T/data" --encoding=UTF8 --locale=C --auth-local=trust --auth-host=reject --no-instructions >"$T/init.log" 2>&1
export PGHOST="$T"
export PGPORT="$(python3 - <<'PY_PORT'
import socket
sock=socket.socket()
sock.bind(('127.0.0.1',0))
port=sock.getsockname()[1]
sock.close()
print(port)
PY_PORT
)"
export PGUSER=ubuntu
"$PGCTL" -D "$T/data" -l "$T/postgres.log" \
    -o "-c listen_addresses='' -c unix_socket_directories=$T -c port=$PGPORT -c fsync=off" \
    -w start > "$T/start.log" 2>&1
RUNNING=1
test ! -z "$PGPORT"
if ss -lnt | grep -q "127.0.0.1:$PGPORT"; then
    echo "REFUSING_TCP_POSTGRES_FIXTURE"; exit 2
fi
psql -X -q -v ON_ERROR_STOP=1 -d postgres <<'SQL_ROLES'
CREATE ROLE empiredb_migrator;
GRANT empiredb_migrator TO ubuntu;
CREATE ROLE empiredb_app;
CREATE ROLE empiredb_readonly;
CREATE ROLE empiredb_tenant_reader;
CREATE ROLE empire_revenue_crm_reader;
CREATE ROLE empire_crm_membership_login LOGIN;
SQL_ROLES
createdb crm_membership_fixture
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture -c "GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator" >/dev/null
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture \
  -f "$ROOT/migrations/empiredb/041_crm_membership_authority.sql" > "$T/041.log"
psql -X -q -v ON_ERROR_STOP=1 -d crm_membership_fixture -c \
 "GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid) TO empire_crm_membership_login" >/dev/null

PYTHONPATH="$ROOT" /srv/empire_os/.venv/bin/python -B "$ROOT/scripts/agency_mcp_live_wp_e2e/real_canonical_041_revocation.py" \
  > "$T/observations.json"
python3 - "$T/observations.json" "$ROOT" <<'PY_RECEIPT'
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
observations=Path(sys.argv[1])
root=Path(sys.argv[2])
data=json.loads(observations.read_text())
assert data['status']=='REAL_POSTGRES_CANONICAL_041_MEMBERSHIP_REVOCATION_FIXTURE_PASS'
assert data['checks_passed']==len(data['checks'])
assert all(data['checks'].values())
out=root/'docs/commercial/EMPIRE_AGENCY_CANONICAL_041_POSTGRES_REVOCATION_FIXTURE_20261023.json'
if out.exists():
    raise RuntimeError('Refusing to overwrite immutable test evidence')
paths=[
  'empire_os/agency_canonical_membership.py',
  'empire_os/agency_connector_authority.py',
  'empire_os/agency_connector_preflight.py',
  'scripts/agency_mcp_live_wp_e2e/real_canonical_041_revocation.py',
  'scripts/agency_mcp_live_wp_e2e/run_canonical_041_revocation.sh',
  'migrations/empiredb/041_crm_membership_authority.sql',
]
data['source_sha256']={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in paths}
data['observed_utc']=datetime.now(timezone.utc).isoformat()
with out.open('x') as f:
    json.dump(data,f,sort_keys=True,indent=2)
    f.write('\n')
print('ISOLATED_CANONICAL_041_SQL_REVOCATION_PASS',data['checks_passed'])
PY_RECEIPT
echo "EPHEMERAL_PG_FIXTURE_TEARDOWN_ON_EXIT"
