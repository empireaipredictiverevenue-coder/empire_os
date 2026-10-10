"""Founder CRM pilot: tenant *candidates*, never authenticated ownership.

Uses disposable PostgreSQL 18 and exact read-only production probe SQL.
No live database connections, new authority, credential output or sends.
"""
from __future__ import annotations

import json
from pathlib import Path

from test_crm_membership_authority_ephemeral import A, B, membership_pg

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "scripts/probe_crm_founder_tenant_candidates.sql"
M042 = ROOT / "migrations/empiredb/042_crm_first_party_login.sql"


def test_founder_tenant_probe_never_infers_identity_from_candidate(membership_pg):
    run, _, _ = membership_pg
    run(file=M042)
    # Fixture-only, minimal source tables: no change to live schema.
    run("""
        CREATE TABLE public.empire_tenant_role_bindings(
          role_name name PRIMARY KEY,
          tenant_id uuid NOT NULL,
          active boolean NOT NULL DEFAULT true,
          evidence_ref text);
        CREATE TABLE public.tenant_business_entity_bindings(
          tenant_id uuid NOT NULL,
          entity_id uuid NOT NULL,
          binding_kind text NOT NULL,
          evidence_ref text NOT NULL,
          active boolean NOT NULL,
          valid_from timestamptz NOT NULL,
          valid_until timestamptz);
        INSERT INTO public.empire_tenant_role_bindings
          (role_name,tenant_id,active,evidence_ref)
        VALUES ('tenant-A', '00000000-0000-0000-0000-000000000101',
                true, 'fixture:tenant-service-binding');
        INSERT INTO public.tenant_business_entity_bindings
          (tenant_id,entity_id,binding_kind,evidence_ref,active,valid_from)
        VALUES ('00000000-0000-0000-0000-000000000101',
                '11111111-1111-1111-1111-111111111111',
                'owned','fixture:business-scope-not-human',true,now()),
               ('00000000-0000-0000-0000-000000000102',
                '22222222-2222-2222-2222-222222222222',
                'observed','fixture:not-owned',true,now());
    """)
    raw = run(file=SQL)
    report = json.loads(raw[raw.index("{"):raw.rindex("}")+1])
    assert report["schema"] == "empire.crm.founder_candidate_inventory.v1"
    assert report["query_transaction_read_only"] is True
    assert report["mode"] == "OBSERVE"
    assert report["writes_performed"] is False
    assert report["logins_enabled"] is False
    assert report["credential_record_count"] == 0
    assert report["crm_membership_total"] == 0
    assert report["tenant_candidates_total"] == 2
    assert [x["tenant_id"] for x in report["candidate_tenants"]] == [A,B]
    assert report["candidate_tenants"][0]["owned_entity_evidence_count"] == 1
    assert report["candidate_tenants"][1]["owned_entity_evidence_count"] == 0
    assert report["human_founder_identity_verified"] is False
    assert report["founder_to_tenant_membership_verified"] is False
    assert report["pilot_activation_authorized"] is False
    assert "fixture:business-scope-not-human" not in raw
    assert "tenant-A" not in raw
    # Even real-looking membership evidence must not silently prove who
    # controls a person: live authentication is an independent missing check.
    run(f"""
      INSERT INTO public.empire_crm_tenant_memberships
       (subject,tenant_id,role,status,evidence_ref,verified_at)
      VALUES ('founder:candidate','{A}','owner','active',
       'fixture:membership-is-not-human-auth',now());
    """)
    second = run(file=SQL)
    report2 = json.loads(second[second.index("{"):second.rindex("}")+1])
    assert report2["crm_membership_total"] == 1
    assert report2["candidate_tenants"][0]["active_crm_memberships"] == 1
    assert report2["human_founder_identity_verified"] is False
    assert report2["founder_to_tenant_membership_verified"] is False
    assert "founder:candidate" not in second


def test_founder_probe_readonly_limits_and_no_sensitive_output():
    sql = SQL.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in sql
    assert "ROLLBACK;" in sql
    assert "SET LOCAL statement_timeout='5000ms'" in sql
    assert "LIMIT 20" in sql
    assert "'tenant_candidates_truncated'" in sql
    assert "'human_founder_identity_verified',false" in sql
    assert "'pilot_activation_authorized',false" in sql
    assert "'private_email_read',false" in sql
    for forbidden in (
        "INSERT INTO", "UPDATE public.", "ALTER ROLE", "GRANT ",
        "DELETE FROM", "CREATE ROLE", "CREATE TABLE",
        "password_salt", "password_digest",
    ):
        assert forbidden not in sql
