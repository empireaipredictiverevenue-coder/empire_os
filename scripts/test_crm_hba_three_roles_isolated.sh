#!/usr/bin/env bash
# Prove HBA exact SCRAM policy in disposable PostgreSQL 18, never production.
set -euo pipefail
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
if [[ "${1:-}" != "--isolated-inner" ]]; then
  exec pg_virtualenv -v 18 bash "$0" --isolated-inner
fi
[[ -n "${PGPORT:-}" && "$PGPORT" != 5432 ]] || exit 3
database_dir="$(psql -X -w -q -At -d postgres -c 'SHOW data_directory')"
[[ "$database_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 3
hba="$(psql -X -w -q -At -d postgres -c 'SHOW hba_file')"
[[ "$hba" == /tmp/pg_virtualenv.*/postgresql/18/regress/pg_hba.conf ]] || {
 echo CRM_HBA_FIXTURE=UNEXPECTED_HBA_PATH; exit 3;
}
psql -X -w -q -v ON_ERROR_STOP=1 -d postgres -c 'CREATE DATABASE empiredb'
psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb <<'SQL'
CREATE ROLE empire_crm_auth_login LOGIN NOINHERIT PASSWORD 'fixture-crm-hello-98765!';
CREATE ROLE empire_crm_membership_login LOGIN NOINHERIT PASSWORD 'fixture-crm-hello-98765!';
CREATE ROLE empire_crm_tenant_708efd4b53b2 LOGIN NOINHERIT PASSWORD 'fixture-crm-hello-98765!';
SQL
/srv/empire_os/.venv/bin/python - "$hba" <<'PY'
import sys
from pathlib import Path
from scripts.deploy_crm_hba_three_roles import amended
p=Path(sys.argv[1])
original=p.read_bytes()
p.write_bytes(amended(original))
PY
psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c 'SELECT pg_reload_conf()' | grep -qx t
# The catalog must include three *exact* local rules and no parse error.
effective="$(psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c "
SELECT count(*) FROM pg_catalog.pg_hba_file_rules
WHERE type='local' AND database=ARRAY['empiredb']::text[]
 AND user_name IN (ARRAY['empire_crm_auth_login']::text[],
                   ARRAY['empire_crm_membership_login']::text[],
                   ARRAY['empire_crm_tenant_708efd4b53b2']::text[])
 AND auth_method='scram-sha-256' AND error IS NULL
")"
[[ "$effective" == 3 ]] || { echo CRM_HBA_FIXTURE=ROLE_SPECIFIC_RULES_MISSING; exit 3; }
# Actual three-role SCRAM connections must authenticate; no peer bypass.
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
  actual="$(PGPASSWORD='fixture-crm-hello-98765!' psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$role" -d empiredb -c 'SELECT session_user')"
  [[ "$actual" == "$role" ]] || { echo CRM_HBA_FIXTURE=ROLE_LOGIN_FAILED; exit 3; }
done
# Wrong password must fail on all three identities.
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
  if PGPASSWORD='wrong-fixture-password' psql -X -w -q -At -h "$PGHOST" -p "$PGPORT" -U "$role" -d empiredb -c 'SELECT 1' >/dev/null 2>&1; then
    echo CRM_HBA_FIXTURE=WRONG_PASSWORD_UNSAFE; exit 3
  fi
done
# Baseline superuser socket local access must stay intact.
psql -X -w -q -At -d empiredb -c 'SELECT 1' | grep -qx 1
printf 'CRM_HBA_ISOLATED_PG18=PASS\n'
printf 'CRM_HBA_THREE_PASSWORD_AUTHENTICATIONS=PASS\n'
printf 'CRM_HBA_WRONG_PASSWORD_DENIAL=PASS\n'
printf 'CRM_HBA_EXISTING_LOCAL_AUTH_RETAINED=PASS\n'
printf 'CRM_HBA_PRODUCTION_TOUCH=NO\n'
