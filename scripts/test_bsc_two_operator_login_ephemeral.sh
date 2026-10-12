#!/usr/bin/env bash
# Disposable PostgreSQL 18 financial LOGIN, SCRAM and SET ROLE proof.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "$#" -eq 0 ]]; then
  exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ "$1" == "--ephemeral-inner" ]] || exit 70
[[ -n "$PGPORT" && "$PGPORT" != "5432" ]] || exit 71
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
hba="$(psql -X -w -At -d postgres -c 'SHOW hba_file')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 72
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || exit 73
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'CREATE DATABASE empiredb'
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'REVOKE ALL PRIVILEGES ON DATABASE empiredb FROM PUBLIC'
PYTHONPATH=. /srv/empire_os/.venv/bin/python - "$hba" <<'PY'
from pathlib import Path
import sys,subprocess
from scripts.prepare_bsc_operator_hba import additive_hba_patch
from scripts.provision_crm_dedicated_logins import scram_verifier
from empire_os.bsc_payment_operator_readiness import EXPECTED
from psycopg import sql
path=Path(sys.argv[1])
original=path.read_bytes()
patched=additive_hba_patch(original)
assert patched.endswith(original)
path.write_bytes(patched)
stmt="BEGIN;"
for group in EXPECTED:
 stmt+=sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;").format(sql.Identifier(group)).as_string(None)
for group,login in EXPECTED.items():
 stmt+=sql.SQL(
   "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {};"
 ).format(sql.Identifier(login),sql.Literal(scram_verifier(
    "ephemeral-only-operator-password-"+login+"-never-production"))).as_string(None)
 stmt+=sql.SQL("GRANT {} TO {} WITH INHERIT FALSE, SET TRUE, ADMIN FALSE;").format(
    sql.Identifier(group),sql.Identifier(login)).as_string(None)
stmt+="COMMIT;"
r=subprocess.run(["psql","-X","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-q"],
                 input=stmt,text=True,capture_output=True,timeout=18)
assert r.returncode==0, "EPHEMERAL_ONLY_LOGIN_DDL_FAILURE"
print("EPHEMERAL_ROLE_AND_MEMBERSHIP_TRANSACTION=COMMITTED_ISOLATED_ONLY")
PY
psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c 'SELECT pg_reload_conf()' | grep -qx t
# Reproduce the actual EmpireDB policy: PUBLIC has no CONNECT.
# A valid role membership and SCRAM login is still not sufficient.
for login in empire_payment_approver_login empire_escrow_verifier_login;do
  password="ephemeral-only-operator-password-$login-never-production"
  if PGPASSWORD="$password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$login" -d empiredb -c 'SELECT 1' >/dev/null 2>&1;then
    echo "EPHEMERAL_UNEXPECTED_CONNECT_BEFORE_DATABASE_GRANT";exit 76
  fi
done
echo "EPHEMERAL_PREGRANT_CONNECT_DENIED_AS_PRODUCTION=YES"
# Exactly two CONNECT grants; neither CREATE nor TEMP, no financial RPC.
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c 'GRANT CONNECT ON DATABASE empiredb TO empire_payment_approver_login, empire_escrow_verifier_login'
echo "EPHEMERAL_TWO_DATABASE_CONNECT_GRANTS_ONLY=APPLIED"
# Verify role privileges are still CONNECT only -- no CREATE or TEMPORARY.
for login in empire_payment_approver_login empire_escrow_verifier_login;do
  acl="$(psql -X -w -At -d postgres -c "SELECT
    has_database_privilege('$login','empiredb','CONNECT')::int::text||'|'||
    has_database_privilege('$login','empiredb','CREATE')::int::text||'|'||
    has_database_privilege('$login','empiredb','TEMP')::int::text")"
  [[ "$acl" == "1|0|0" ]] || { echo "EPHEMERAL_DB_ACL_WIDENED_ABORT";exit 77;}
done
echo "EPHEMERAL_DB_GRANTS_EXACT_CONNECT_ONLY=PASS"
for spec in empire_payment_approver_login:empire_payment_approver empire_escrow_verifier_login:empire_escrow_verifier;do
  login="$(printf '%s' "$spec" | cut -d: -f1)"
  group="$(printf '%s' "$spec" | cut -d: -f2)"
  password="ephemeral-only-operator-password-$login-never-production"
  actual="$(PGPASSWORD="$password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$login" -d empiredb -v ON_ERROR_STOP=1 \
    -c "BEGIN READ ONLY;SELECT session_user||'|'||current_user;SET LOCAL ROLE $group;SELECT session_user||'|'||current_user;ROLLBACK;")"
  echo "$actual" | grep -Fx "$login|$login" >/dev/null
  echo "$actual" | grep -Fx "$login|$group" >/dev/null
  other=empire_payment_approver
  [[ "$group" == empire_payment_approver ]] && other=empire_escrow_verifier
  if PGPASSWORD="$password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$login" -d empiredb -v ON_ERROR_STOP=1 \
    -c "BEGIN READ ONLY; SET LOCAL ROLE $other;ROLLBACK;" >/dev/null 2>&1;then
    echo "EPHEMERAL_CROSS_FINANCIAL_ROLE_ESCALATION_UNSAFE";exit 74
  fi
  if PGPASSWORD="incorrect-ephemeral-password" psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$login" -d empiredb \
    -c "SELECT 1" >/dev/null 2>&1;then
    echo "EPHEMERAL_WRONG_PASSWORD_ACCEPTED_UNSAFE";exit 75
  fi
  echo "EPHEMERAL_AUTH_AND_EXACT_SET_LOCAL_ROLE_PASS=$login"
done
echo "EPHEMERAL_CROSS_ROLE_SET_AND_WRONG_PASSWORD_DENIED=YES"
echo "PRODUCTION_PGPORT_TOUCHED=NO"
echo "FINANCIAL_TRANSACTIONS_SENT=ZERO"
