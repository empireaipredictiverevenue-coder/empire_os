#!/usr/bin/env bash
# Independent, ephemeral PostgreSQL 18 test for EXACT ONE direct BSC verifier.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then
  exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ "$1" == "--ephemeral-inner" && -n "${PGPORT:-}" && "$PGPORT" != "5432" ]] || exit 72
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
hba="$(psql -X -w -At -d postgres -c 'SHOW hba_file')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 73
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || exit 74

psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'CREATE DATABASE empiredb'
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'REVOKE ALL PRIVILEGES ON DATABASE empiredb FROM PUBLIC'
PYTHONPATH=. ./.venv/bin/python - "$hba" <<'PY'
from pathlib import Path
import sys, subprocess
from psycopg import sql
from scripts.activate_direct_bsc_verifier_identity import additive_hba, LOGIN, GROUP
from scripts.provision_crm_dedicated_logins import scram_verifier
p=Path(sys.argv[1])
before=p.read_bytes()
after=additive_hba(before)
assert after.endswith(before)
p.write_bytes(after)
password="only-ephemeral-direct-verifier-test-password-no-real-secrets"
statement="BEGIN;"
for group in (GROUP,"empire_payment_approver","empire_escrow_verifier"):
 statement+=sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT;").format(sql.Identifier(group)).as_string(None)
statement+=sql.SQL(
 "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {};"
).format(sql.Identifier(LOGIN),sql.Literal(scram_verifier(password))).as_string(None)
statement+=sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;").format(
 sql.Identifier(GROUP),sql.Identifier(LOGIN)).as_string(None)
statement+="COMMIT;"
r=subprocess.run(["psql","-X","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-q"],
 input=statement,text=True,capture_output=True,timeout=15)
assert r.returncode==0, "isolated role transaction failed"
print("EPHEMERAL_DIRECT_ROLE_CREATION=PASS")
PY
psql -X -w -At -d empiredb -c 'SELECT pg_reload_conf()' | grep -qx t

password="only-ephemeral-direct-verifier-test-password-no-real-secrets"
if PGPASSWORD="$password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U empire_bsc_verifier_login -d empiredb -c 'SELECT 1' >/dev/null 2>&1;then
  echo "BLOCKED_UNEXPECTED_PREGRANT_CONNECT";exit 77
fi
echo "EPHEMERAL_PREGRANT_CONNECT_DENIED=PASS"
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'GRANT CONNECT ON DATABASE empiredb TO empire_bsc_verifier_login'
acl="$(psql -X -w -At -d postgres -c "SELECT
has_database_privilege('empire_bsc_verifier_login','empiredb','CONNECT')::int::text||'|'||
has_database_privilege('empire_bsc_verifier_login','empiredb','CREATE')::int::text||'|'||
has_database_privilege('empire_bsc_verifier_login','empiredb','TEMP')::int::text")"
[[ "$acl" == "1|0|0" ]] || { echo "BLOCKED_DATABASE_ACL_DRIFT";exit 78; }

identity="$(PGPASSWORD="$password" psql -X -w -q -At -F '|' -h "$PGHOST" -p "$PGPORT" -U empire_bsc_verifier_login -d empiredb -v ON_ERROR_STOP=1 -c 'BEGIN READ ONLY; SELECT session_user,current_user; SET LOCAL ROLE empire_bsc_verifier;SELECT session_user,current_user; ROLLBACK;')"
echo "$identity" | grep -Fx 'empire_bsc_verifier_login|empire_bsc_verifier_login' >/dev/null
echo "$identity" | grep -Fx 'empire_bsc_verifier_login|empire_bsc_verifier' >/dev/null

for denied in empire_payment_approver empire_escrow_verifier; do
  if PGPASSWORD="$password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U empire_bsc_verifier_login -d empiredb -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY; SET LOCAL ROLE $denied; ROLLBACK;" >/dev/null 2>&1;then
    echo "BLOCKED_CROSS_ROLE_ESCALATION";exit 79
  fi
done
if PGPASSWORD="wrong-ephemeral-only" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U empire_bsc_verifier_login -d empiredb -c 'SELECT 1' >/dev/null 2>&1;then
  echo "BLOCKED_WRONG_PASSWORD_ACCEPTED";exit 80
fi
echo "EPHEMERAL_DIRECT_VERIFIER_AUTH_AND_ISOLATION=PASS"
echo "PRODUCTION_PORT_5432_TOUCHED=NO"
echo "FINANCIAL_ACTIONS_SENT=ZERO"
