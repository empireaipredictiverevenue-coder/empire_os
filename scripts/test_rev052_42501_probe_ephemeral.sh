#!/usr/bin/env bash
# Test held migration ONLY in a new, temporary, UNIX-socket PostgreSQL cluster.
# No production DB, service, role, password, localhost TCP or payment is used.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_BIN=/usr/lib/postgresql/18/bin
scratch="$(mktemp -d /tmp/empire-rev051-fixture-XXXXXXXX)"
chmod 0700 "$scratch"
mkdir -m 0700 "$scratch/socket"
stopped=0
cleanup() {
  if [[ "$stopped" == 1 ]]; then
    "$PG_BIN/pg_ctl" -D "$scratch/db" -m immediate stop >/dev/null 2>&1 || true
  fi
  rm -rf "$scratch"
}
trap cleanup EXIT
"$PG_BIN/initdb" -D "$scratch/db" -A trust -U fixture_admin --no-instructions >"$scratch/initdb.log" 2>&1
# Listen on temp UNIX socket only; no TCP or production PostgreSQL touched.
"$PG_BIN/pg_ctl" -D "$scratch/db" -o "-c listen_addresses='' -k $scratch/socket -p 59631" -w start >"$scratch/pg.log" 2>&1
stopped=1
psql() {
  "$PG_BIN/psql" -X -w -v ON_ERROR_STOP=1 -h "$scratch/socket" -p 59631 "$@"
}
psql -U fixture_admin -d postgres -q <<'SQL'
CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE revenue_alpha LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE revenue_beta LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE DATABASE empiredb OWNER fixture_admin;
SQL
psql -U fixture_admin -d empiredb -q <<'SQL'
GRANT CREATE, USAGE ON SCHEMA public TO empiredb_migrator;
SET ROLE empiredb_migrator;
CREATE TABLE public.empire_tenant_role_bindings (
  role_name name PRIMARY KEY,
  tenant_id uuid NOT NULL,
  active boolean NOT NULL,
  evidence_ref text NOT NULL DEFAULT 'fixture:approved'
);
CREATE TABLE public.empire_crm_tenant_memberships (
  tenant_id uuid NOT NULL,
  subject text NOT NULL,
  role text NOT NULL,
  status text NOT NULL,
  revoked_at timestamptz,
  verified_at timestamptz,
  valid_until timestamptz
);
INSERT INTO public.empire_crm_tenant_memberships VALUES
('708efd4b-53b2-43d7-961d-1cecab67f17a',
 'founder:phil_livesley','owner','active',NULL,now(),NULL);
CREATE TABLE public.buyers (
  id uuid PRIMARY KEY,
  org_id uuid
);
CREATE TABLE public.fulfilment_orders (
  id uuid PRIMARY KEY,
  buyer_id uuid,
  product_id uuid,
  state text NOT NULL,
  settled_at timestamptz,
  price_cents bigint NOT NULL,
  commercial_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE public.commercial_events (
  id uuid PRIMARY KEY,
  event_type text NOT NULL,
  fulfilment_order_id uuid,
  buyer_id uuid,
  product_id uuid,
  amount_cents bigint,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('revenue_alpha','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true),
 ('revenue_beta','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true),
 ('empire_intelligence_materializer_login','708efd4b-53b2-43d7-961d-1cecab67f17a',true);
INSERT INTO public.buyers VALUES
 ('11111111-1111-4111-8111-111111111111',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('22222222-2222-4222-8222-222222222222',
  'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'),
 ('33333333-aaaa-4aaa-8aaa-333333333333',
  '708efd4b-53b2-43d7-961d-1cecab67f17a');
INSERT INTO public.fulfilment_orders VALUES
 ('33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',
  'settled',now(),12345,
  '{"causal_lineage":{"example":"alpha"}}'::jsonb),
 ('55555555-5555-4555-8555-555555555555',
  '22222222-2222-4222-8222-222222222222',
  '66666666-6666-4666-8666-666666666666',
  'settled',now(),77889,
  '{"causal_lineage":{"example":"beta"}}'::jsonb),
 ('88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',
  'settled',now(),9000,
  '{"causal_lineage":{"example":"mismatch"}}'::jsonb),
 ('12341234-1234-4234-8234-123412341234',
  '33333333-aaaa-4aaa-8aaa-333333333333',
  '44444444-4444-4444-8444-444444444444',
  'settled',now(),56789,
  '{"causal_lineage":{"example":"founder-tenant"}}'::jsonb);
INSERT INTO public.commercial_events VALUES
 ('77777777-7777-4777-8777-777777777777',
  'revenue_recognized',
  '33333333-3333-4333-8333-333333333333',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',12345,
  '{"actual_revenue":true,"causal_lineage":{"example":"alpha"}}'::jsonb,now()),
 ('99999999-9999-4999-8999-999999999999',
  'revenue_recognized',
  '55555555-5555-4555-8555-555555555555',
  '22222222-2222-4222-8222-222222222222',
  '66666666-6666-4666-8666-666666666666',77889,
  '{"actual_revenue":true,"causal_lineage":{"example":"beta"}}'::jsonb,now()),
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaac',
  'revenue_recognized',
  '88888888-8888-4888-8888-888888888888',
  '11111111-1111-4111-8111-111111111111',
  '44444444-4444-4444-8444-444444444444',9001,
  '{"actual_revenue":true,"causal_lineage":{"example":"mismatch"}}'::jsonb,now()),
 ('abc12345-1234-4234-8234-123412341234',
  'revenue_recognized',
  '12341234-1234-4234-8234-123412341234',
  '33333333-aaaa-4aaa-8aaa-333333333333',
  '44444444-4444-4444-8444-444444444444',56789,
  '{"actual_revenue":true,"causal_lineage":{"example":"founder-tenant"}}'::jsonb,now());
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
  SELECT tenant_id FROM public.empire_tenant_role_bindings
   WHERE role_name=session_user AND active IS TRUE LIMIT 1
$$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
RESET ROLE;
SQL
psql -U fixture_admin -d empiredb -q -f "$repo/migrations/empiredb/051_predictive_revenue_event_reader_held.sql" >"$scratch/migration.log"
# The held migration intentionally lacks a dedicated login grant: catalog
# preflight MUST remain HOLD even though the role/function are now present.
psql -U fixture_admin -d empiredb -Atq \
  -f "$repo/scripts/probe_predictive_revenue_event_reader_catalog_readonly.sql" \
  > "$scratch/before_grant.json"
python3 - "$scratch/before_grant.json" <<'PYREAD'
import json,sys
x=json.load(open(sys.argv[1]))
assert x["status"]=="HOLD_EVENT_READER_CATALOG_NOT_PROVEN",x
assert x["function_exists"] is True and x["capability_exists"] is True
assert x["dedicated_login_member_exists"] is False
PYREAD

# Execute the exact generated production read-only preflight SQL against
# the isolated fixture. Only its data_directory and HBA location should
# differ from real EmpireDB. This catches SQL catalogue incompatibility.
PYTHONPATH="$repo" /srv/empire_os/.venv/bin/python - <<'PYSQL' > "$scratch/rev052-preflight.sql"
from scripts.provision_revenue_event_evidence_login_20261018 import readiness_sql
print(readiness_sql())
PYSQL
psql -U fixture_admin -d empiredb -Atq -f "$scratch/rev052-preflight.sql" \
  > "$scratch/rev052-preflight.json"
python3 - "$scratch/rev052-preflight.json" <<'PYVERIFY'
import json,sys
with open(sys.argv[1]) as handle:
    data=json.load(handle)
excepted={'hba_file_matches','data_directory_matches'}
assert all(v is True for k,v in data.items() if k not in excepted),data
assert all(data.get(k) is False for k in excepted),data
print('REV052_ISOLATED_READONLY_SQL_CATALOG_PREFLIGHT=PASS')
PYVERIFY
# The fixture uses its *own* pg_hba.conf and temporary Unix socket. The
# real EmpireDB HBA, credentials, tenant member records remain untouched.
PYTHONPATH="$repo" /srv/empire_os/.venv/bin/python - "$scratch/db/pg_hba.conf" <<'PYHBA'
from pathlib import Path
import sys
from scripts.provision_revenue_event_evidence_login_20261018 import PREFIX
p=Path(sys.argv[1])
p.write_bytes(PREFIX.encode("ascii")+p.read_bytes())
PYHBA
"$PG_BIN/pg_ctl" -D "$scratch/db" reload >/dev/null
# Reuse the exact provision transaction builder but generate only fake fixture
# secrets, not the production operator's private 0600 credentials.
PYTHONPATH="$repo" /srv/empire_os/.venv/bin/python - <<'PYDDL' | psql -U fixture_admin -d empiredb -q
from scripts.provision_revenue_event_evidence_login_20261018 import (
    provision_sql, scram_verifier,
)
fixture_only_password="isolated-test-credential-not-a-real-secret-12345"
print(provision_sql(scram_verifier(fixture_only_password)))
PYDDL

export PGPASSWORD="isolated-test-credential-not-a-real-secret-12345"
login="empire_predictive_revenue_evidence_login"
observed="$(psql -U "$login" -d empiredb -Atq <<'SQL'
BEGIN READ ONLY;
SELECT session_user,
       pg_catalog.has_table_privilege(session_user,'public.commercial_events','SELECT'),
       pg_catalog.has_table_privilege(session_user,'public.fulfilment_orders','SELECT');
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*)::text||':'||coalesce(max(amount_cents),0)::text
  FROM public.read_predictive_revenue_event_v1(
   'abc12345-1234-4234-8234-123412341234',
   '708efd4b-53b2-43d7-961d-1cecab67f17a');
SELECT count(*)::text
  FROM public.read_predictive_revenue_event_v1(
   '77777777-7777-4777-8777-777777777777',
   'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
ROLLBACK;
SQL
)"
expected="$(printf '%s\n' "$login|f|f"  '1:56789' '0')"
if [[ "$observed" != "$expected" ]]; then
  echo 'REV052_EPHEMERAL_TENANT_AND_EVENT_BOUNDARIES_FAIL' >&2
  exit 10
fi
binding="$(psql -U fixture_admin -d empiredb -Atq -c "SELECT count(*) FROM public.empire_tenant_role_bindings WHERE role_name='$login' AND tenant_id='708efd4b-53b2-43d7-961d-1cecab67f17a' AND active")"
test "$binding" = 1
# The exact HBA first-match rule enforces SCRAM rather than the fixture
# cluster's deliberately permissive base auth.
if PGPASSWORD='wrong-fixture-password' psql -U "$login" -d empiredb     -Atq -c "SELECT session_user" >"$scratch/deny.log" 2>&1; then
  echo 'REV052_EPHEMERAL_BAD_PASSWORD_WAS_ACCEPTED' >&2
  exit 11
fi
# Even the restricted capability cannot access the underlying ledger.
if psql -U "$login" -d empiredb -Atq >"$scratch/acl.log" 2>&1 <<'SQL'
BEGIN READ ONLY;
SET LOCAL ROLE empire_predictive_revenue_evidence_reader;
SELECT count(*) FROM public.commercial_events;
ROLLBACK;
SQL
then
  echo 'REV052_EPHEMERAL_LEDGER_TABLE_READ_WAS_ACCEPTED' >&2
  exit 12
fi
# Exercise exact psycopg protocol used by the production verifier, not only
# libpq psql. The test connector targets this isolated Unix socket ONLY.
PYTHONPATH="$repo" /srv/empire_os/.venv/bin/python - "$scratch/socket" <<'PYAUDIT'
import psycopg,sys
from scripts.review_rev052_committed_login_readonly_20261018 import bounded_auth_probe
fixture_password="isolated-test-credential-not-a-real-secret-12345"
def connect_fixture(**kwargs):
    kwargs["host"]=sys.argv[1]
    kwargs["port"]=59631
    return psycopg.connect(**kwargs)
with connect_fixture(dbname="empiredb",user="empire_predictive_revenue_evidence_login",password=fixture_password,connect_timeout=5) as dbg:
    with dbg.cursor() as c:
        sample=c.execute("SELECT session_user::text,current_user::text,pg_catalog.has_table_privilege(session_user,'public.commercial_events','SELECT')").fetchone()
        print("FIXTURE_IDENTITY_SHAPE",repr(sample),[type(v).__name__ for v in sample],flush=True)
result=bounded_auth_probe(fixture_password,connector=connect_fixture)
assert result["failure_stage"]=="NONE",result
assert result["auth_connection_verified"] is True
assert result["session_login_identity_verified"] is True
assert result["capability_set_role_verified"] is True
assert result["capability_function_execute_verified"] is True
assert result["sentinel_zero_result_verified"] is True
assert result["real_event_selected"] is False
print("REV052_ISOLATED_PSYCOPG_AUTH_FUNCTION_PROOF=PASS")
# Exercise the original already-deployed REV052 verifier as well: monkeypatch
# ONLY this temporary Python process to point at the disposable test socket.
from scripts.provision_revenue_event_evidence_login_20261018 import live_login_proof
original_connect=psycopg.connect
def original_verifier_fixture(**kwargs):
    kwargs["host"]=sys.argv[1]
    kwargs["port"]=59631
    return original_connect(**kwargs)
psycopg.connect=original_verifier_fixture
try:
    assert live_login_proof(fixture_password) is True
finally:
    psycopg.connect=original_connect
print("REV052_ISOLATED_ORIGINAL_LOGIN_PROOF=PASS")
PYAUDIT
# Synthetic ACL-hardening to reproduce a private public namespace while
# retaining EXECUTE/USAGE on the restricted NOLOGIN capability.
psql -U fixture_admin -d empiredb -q -c 'REVOKE USAGE ON SCHEMA public FROM PUBLIC'
PYTHONPATH="$repo" /srv/empire_os/.venv/bin/python - "$scratch/socket" <<'PY42501'
import json,sys,psycopg
from scripts.diagnose_rev052_login_privilege_readonly_20261018 import _session
original=psycopg.connect
def isolated_connect(**kw):
    kw.update(host=sys.argv[1],port=59631)
    return original(**kw)
r=_session("isolated-test-credential-not-a-real-secret-12345",connector=isolated_connect)
print('REV052_PRIVATE_SCHEMA_PROBE',json.dumps(r,sort_keys=True))
assert r['authenticated'] is True
assert r['session_readonly'] is True
assert r['metadata']['identity']['status']=='PASS'
assert r['role_set'] is True
assert r['restricted_function_executable'] is True
assert r['stage']=='DONE'
# Even with no PUBLIC schema USAGE, both the original function verifier
# and the founder's existing root-only reconciliation MUST succeed.
from scripts.provision_revenue_event_evidence_login_20261018 import live_login_proof
original_connect=psycopg.connect
def production_login_fixture(**kw):
    kw.update(host=sys.argv[1],port=59631)
    return original_connect(**kw)
psycopg.connect=production_login_fixture
try:
    assert live_login_proof("isolated-test-credential-not-a-real-secret-12345") is True
finally:
    psycopg.connect=original_connect
from scripts.review_rev052_committed_login_readonly_20261018 import review,CATALOG_SQL
import subprocess

def fixture_admin(sql):
    cmd=["/usr/lib/postgresql/18/bin/psql","-X","-q","-A","-t",
         "-v","ON_ERROR_STOP=1","-h",sys.argv[1],"-p","59631",
         "-U","fixture_admin","-d","empiredb"]
    done=subprocess.run(cmd,input=sql,text=True,capture_output=True,check=True)
    return done.stdout.strip()
report=review(
    admin_query=fixture_admin,
    password_reader=lambda:"isolated-test-credential-not-a-real-secret-12345",
    connector=isolated_connect,
)
assert report['status']=='REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED',report
assert all(report['catalog_checks'].values())
assert report['auth_checks']['login_has_no_direct_source_table_select'] is True
assert report['direct_source_table_acl_proof']=='ADMIN_READ_ONLY_CATALOG'
print('REV052_PRIVATE_SCHEMA_ADMIN_ACL_PLUS_LOGIN_PROOF=PASS')
PY42501
unset PGPASSWORD
echo 'REV052_ISOLATED_POSTGRES_PASS dedicated_scram=YES wrong_password=DENIED founder_tenant=BOUND own_event=1 cross_tenant=0 ledger_select=DENIED production=UNTOUCHED'
