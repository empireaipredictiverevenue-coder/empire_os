#!/usr/bin/env bash
# Exact three-role SCRAM verifier/password proof, disposable PG18 ONLY.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "${1:-}" != "--ephemeral-inner" ]]; then
 exec pg_virtualenv -v 18 bash "$0" --ephemeral-inner
fi
[[ -n "${PGPORT:-}" && "${PGPORT}" != "5432" ]] || exit 3
data_dir="$(psql -X -w -At -d postgres -c 'SHOW data_directory')"
hba="$(psql -X -w -At -d postgres -c 'SHOW hba_file')"
[[ "$data_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 3
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || exit 3
psql -X -w -v ON_ERROR_STOP=1 -d postgres -q -c "CREATE DATABASE empiredb"
PYTHONPATH=. /srv/empire_os/.venv/bin/python - "$hba" <<'PY'
import sys, pathlib, subprocess
from scripts.provision_crm_dedicated_logins import scram_verifier, ROLES
from psycopg import sql
p=pathlib.Path(sys.argv[1])
original=p.read_bytes()
rules="".join(f"local empiredb {role} scram-sha-256\n" for role in ROLES)
p.write_bytes(rules.encode()+original)
con=subprocess.run(["psql","-X","-w","-v","ON_ERROR_STOP=1","-d","empiredb","-q"],
    input="BEGIN;"+ "".join(
    sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {};").format(
        sql.Identifier(role),sql.Literal(scram_verifier(
            "ephemeral-only-43-character-fixture-password-xyz")))
       .as_string(None) for role in ROLES)+"COMMIT;",
    text=True,capture_output=True)
assert con.returncode == 0, "ephemeral PostgreSQL rejected SCRAM verifier"
PY
psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c 'SELECT pg_reload_conf()' | grep -qx t
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
 actual="$(PGPASSWORD='ephemeral-only-43-character-fixture-password-xyz' psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$role" -d empiredb -c 'SELECT session_user')"
 [[ "$actual" == "$role" ]] || exit 3
 if PGPASSWORD='wrong-ephemeral-only' psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$role" -d empiredb -c 'SELECT 1' >/dev/null 2>&1; then
  echo CRM_LOGIN_EPHEMERAL_WRONG_PASSWORD_UNSAFE; exit 3
 fi
done
echo CRM_LOGIN_EPHEMERAL_SCRAM_VERIFIERS_PASS
echo CRM_LOGIN_EPHEMERAL_THREE_PASSWORD_CONNECTIONS_PASS
echo CRM_LOGIN_EPHEMERAL_PRODUCTION_TOUCHED_NO
