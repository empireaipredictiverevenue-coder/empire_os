"""One explicitly approved, PENDING founder CRM member on disposable PG18.

No production access, public API activation, credential provisioning or sends.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_crm_membership_authority_ephemeral import membership_pg

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "scripts/provision_crm_founder_owner_pending.sql"
M042 = ROOT / "migrations/empiredb/042_crm_first_party_login.sql"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"


@pytest.fixture
def pg(membership_pg):
    run, sock, port = membership_pg
    if run("SELECT to_regclass('public.empire_crm_login_credentials') IS NULL") == "t":
        run(file=M042)
    # Disposable only. Real operator is already PostgreSQL superuser.
    run("""
    DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='postgres') THEN
        CREATE ROLE postgres LOGIN SUPERUSER;
      END IF;
      IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_crm_auth_login') THEN
        CREATE ROLE empire_crm_auth_login NOLOGIN NOINHERIT;
      END IF;
    END $$;
    ALTER ROLE empire_crm_membership_login NOLOGIN NOINHERIT;
    CREATE TABLE IF NOT EXISTS public.empire_tenant_role_bindings(
      role_name name PRIMARY KEY,tenant_id uuid NOT NULL,
      active boolean NOT NULL,evidence_ref text);
    CREATE TABLE IF NOT EXISTS public.tenant_business_entity_bindings(
      tenant_id uuid NOT NULL,entity_id uuid NOT NULL,
      binding_kind text NOT NULL,evidence_ref text,
      active boolean NOT NULL,valid_from timestamptz NOT NULL,
      valid_until timestamptz);
    TRUNCATE public.empire_tenant_role_bindings,
             public.tenant_business_entity_bindings,
             public.empire_crm_tenant_memberships,
             public.empire_crm_login_credentials;
    """)
    if run("SELECT count(*) FROM pg_roles WHERE rolname='empire_intelligence_materializer_login'") == "0":
        run("CREATE ROLE empire_intelligence_materializer_login LOGIN NOINHERIT;")
    run(f"""
      INSERT INTO public.empire_tenant_role_bindings
        (role_name,tenant_id,active,evidence_ref)
      VALUES ('empire_intelligence_materializer_login','{TENANT}',
              true,'fixture:operator');
      INSERT INTO public.tenant_business_entity_bindings
        (tenant_id,entity_id,binding_kind,evidence_ref,active,valid_from)
      SELECT '{TENANT}'::uuid,
             ('00000000-0000-0000-0000-'||lpad(x::text,12,'0'))::uuid,
             'observed','fixture:observed',true,now()
      FROM generate_series(1,4) x;
    """)
    return run


def _read(run):
    return run(f"""
      SELECT count(*)::int || '|' ||
             count(*) FILTER (WHERE status='active')::int || '|' ||
             count(*) FILTER (WHERE status='pending' AND role='owner'
                AND tenant_id='{TENANT}' AND subject='founder:phil_livesley')::int
      FROM public.empire_crm_tenant_memberships
    """)


def test_approved_one_pending_owner_only(pg):
    output=pg(file=SQL,user="postgres")
    assert '"member_status": "pending"' in output or '"member_status":"pending"' in output
    assert _read(pg)=="1|0|1"
    assert pg("SELECT count(*) FROM public.empire_crm_login_credentials")=="0"
    assert pg("SELECT rolcanlogin FROM pg_roles WHERE rolname='empire_crm_auth_login'")=="f"
    assert pg("SELECT rolcanlogin FROM pg_roles WHERE rolname='empire_crm_membership_login'")=="f"
    rejected = pg(file=SQL,user="postgres",check=False)
    assert "COMMIT" not in rejected
    assert _read(pg)=="1|0|1"


def test_wrong_session_user_fails_no_row(pg):
    pg(file=SQL,user="ubuntu",check=False)
    assert _read(pg)=="0|0|0"


def test_missing_provenance_fails_no_row(pg):
    pg("DELETE FROM public.empire_tenant_role_bindings")
    pg(file=SQL,user="postgres",check=False)
    assert _read(pg)=="0|0|0"


def test_expired_observed_business_data_does_not_block_pending_identity(pg):
    pg("UPDATE public.tenant_business_entity_bindings SET active=false")
    output=pg(file=SQL,user="postgres")
    assert "pending" in output
    assert _read(pg)=="1|0|1"


def test_no_observed_business_data_does_not_block_pending_identity(pg):
    pg("TRUNCATE public.tenant_business_entity_bindings")
    output=pg(file=SQL,user="postgres")
    assert "pending" in output
    assert _read(pg)=="1|0|1"


def test_ambiguous_tenant_role_bindings_fail_closed(pg):
    pg(f"""
      INSERT INTO public.empire_tenant_role_bindings
       (role_name,tenant_id,active,evidence_ref)
      VALUES ('empiredb_readonly','{TENANT}',true,'fixture:extra-role');
    """)
    rejected=pg(file=SQL,user="postgres",check=False)
    assert "COMMIT" not in rejected
    assert _read(pg)=="0|0|0"


def test_existing_member_prevents_owner_creation(pg):
    pg(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (tenant_id,subject,role,status,evidence_ref,verified_at)
      VALUES ('{TENANT}','another:person','viewer','pending','fixture:first',now());
    """)
    pg(file=SQL,user="postgres",check=False)
    assert _read(pg)=="1|0|0"


def test_sql_is_exact_scope_without_activation():
    sql=SQL.read_text()
    assert sql.count("INSERT INTO public.empire_crm_tenant_memberships")==1
    assert "'owner','pending'" in sql
    assert "session_user <> 'postgres'" in sql
    assert "LOCK TABLE public.empire_crm_tenant_memberships" in sql
    assert "IF EXISTS (SELECT 1 FROM public.empire_crm_tenant_memberships)" in sql
    assert "'human_identity_verified',false" in sql
    for forbidden in ("ALTER ROLE","GRANT ","CREATE ROLE","INSERT INTO public.empire_crm_login_credentials","UPDATE public.empire_crm_tenant_memberships","ON CONFLICT"):
        assert forbidden not in sql
