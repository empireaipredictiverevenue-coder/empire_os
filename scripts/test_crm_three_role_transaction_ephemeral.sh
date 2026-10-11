#!/usr/bin/env bash
# Executes actual CRM three-role operator transaction in disposable PG18 only.
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
psql -X -w -q -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE empiredb TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'"
psql -X -w -q -v ON_ERROR_STOP=1 -d empiredb <<'SQL'
CREATE ROLE postgres LOGIN SUPERUSER;
CREATE ROLE empire_revenue_crm_reader NOLOGIN NOINHERIT;
CREATE ROLE empire_crm_auth_login NOLOGIN NOINHERIT PASSWORD NULL;
CREATE ROLE empire_crm_membership_login NOLOGIN NOINHERIT PASSWORD NULL;
CREATE TABLE public.empire_tenant_role_bindings(role_name name PRIMARY KEY,
 tenant_id uuid NOT NULL,active boolean NOT NULL,evidence_ref text);
CREATE TABLE public.empire_crm_tenant_memberships(
 tenant_id uuid, subject text,role text,status text,verified_at timestamptz,
 revoked_at timestamptz,valid_until timestamptz,evidence_ref text);
CREATE TABLE public.empire_crm_login_credentials(subject text, invitation_tenant_id uuid);
CREATE VIEW public.revenue_crm_prospects AS SELECT NULL::uuid AS tenant_id;
CREATE VIEW public.revenue_crm_buyers AS SELECT NULL::uuid AS tenant_id;
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $fn$ SELECT tenant_id FROM public.empire_tenant_role_bindings
 WHERE role_name=session_user AND active LIMIT 1 $fn$;
INSERT INTO public.empire_crm_tenant_memberships VALUES(
 '708efd4b-53b2-43d7-961d-1cecab67f17a',
 'founder:phil_livesley','owner','active',now(),NULL,NULL,'fixture:one-owner');
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_revenue_crm_reader;
SQL
PYTHONPATH=. /srv/empire_os/.venv/bin/python - "$hba" <<'PY'
import sys
from pathlib import Path
from scripts.provision_crm_dedicated_logins import ROLES
p=Path(sys.argv[1])
p.write_bytes(("local empiredb postgres trust\n"+"".join(f"local empiredb {role} scram-sha-256\n" for role in ROLES)).encode()+p.read_bytes())
PY
psql -X -w -q -At -v ON_ERROR_STOP=1 -d empiredb -c 'SELECT pg_reload_conf()' | grep -qx t
PYTHONPATH=. /srv/empire_os/.venv/bin/python - <<'PY'
import os
from pathlib import Path
import psycopg
from scripts import provision_crm_dedicated_logins as m
m._conn=lambda:psycopg.connect(f"host=/tmp port={os.environ['PGPORT']} dbname=empiredb user=postgres connect_timeout=5")
m.VAULT_DIR=Path(os.environ["PGHOST"])/"nonexistent-crm-vault"
assert m._conn().execute('SELECT pg_encoding_to_char(encoding) FROM pg_database WHERE datname=current_database()').fetchone()==('UTF8',)
assert m.catalog()["status"]=="READY_TO_PROVISION",m.catalog()
passwords={name:f"ephemeral_{name}_strong_36_character_random_fixtures" for name in m.ROLES}
m.operator_apply({"verifiers":{r:m.scram_verifier(passwords[r]) for r in m.ROLES}})
report=m.postcommit_catalog()
assert report["status"]=="CATALOG_VERIFIED",report
assert m.catalog()["status"]=="BLOCKED_NO_CHANGES"
PY
# Validate libpq's *file-based* secret flow as well as the SCRAM verifier.
passfile="$(dirname "$hba")/fixture-role-passfile"
umask 077
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
 password="ephemeral_${role}_strong_36_character_random_fixtures"
 printf '/tmp:%s:empiredb:%s:%s\n' "$PGPORT" "$role" "$password" >> "$passfile"
done
chmod 600 "$passfile"
for role in empire_crm_auth_login empire_crm_membership_login empire_crm_tenant_708efd4b53b2; do
 actual="$(env -u PGPASSWORD PGPASSFILE="$passfile" psql -X -w -q -At -h /tmp -p "$PGPORT" -U "$role" -d empiredb -c 'SELECT session_user')"
 [[ "$actual" == "$role" ]] || exit 3
done
session_proof="$(env -u PGPASSWORD PGPASSFILE="$passfile" psql -X -w -q -At -h /tmp -p "$PGPORT" -U empire_crm_tenant_708efd4b53b2 -d empiredb -c "BEGIN READ ONLY; SET LOCAL ROLE empire_revenue_crm_reader; SELECT public.empire_current_tenant_id(); ROLLBACK;")"
[[ "$session_proof" == '708efd4b-53b2-43d7-961d-1cecab67f17a' ]] || {
 echo CRM_THREE_ROLES_ISOLATED_TENANT_SCOPE_FAILED; exit 3;
}
echo CRM_THREE_ROLES_ISOLATED_PGPASSFILE_PROOF_PASS
echo CRM_THREE_ROLES_ISOLATED_TENANT_SESSION_BINDING_PASS
echo CRM_THREE_ROLES_ISOLATED_ATOMIC_TRANSACTION_PASS
echo CRM_THREE_ROLES_ISOLATED_SAFE_CATALOG_READBACK_PASS
echo CRM_THREE_ROLES_ISOLATED_ACTUAL_LOGIN_PASS
echo CRM_THREE_ROLES_PRODUCTION_TOUCHED_NO
