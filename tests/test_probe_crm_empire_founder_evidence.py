"""Bounded founder tenant evidence probe tested against disposable PostgreSQL 18.

Operational DB tenant bindings are not proof of a human's identity. Fixture
set-up is deliberately independent of pytest test order and production data.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_crm_membership_authority_ephemeral import membership_pg

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "scripts/probe_crm_empire_founder_evidence.sql"
M042 = ROOT / "migrations/empiredb/042_crm_first_party_login.sql"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"


def _report(raw: str) -> dict:
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1])


@pytest.fixture
def existing_registration(membership_pg):
    run, _, _ = membership_pg
    if run("SELECT to_regclass('public.empire_crm_login_credentials') IS NOT NULL") == "f":
        run(file=M042)
    run("""
      DO $$
      BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles
                       WHERE rolname='empire_intelligence_materializer_login')
        THEN
          CREATE ROLE empire_intelligence_materializer_login LOGIN NOINHERIT;
        END IF;
      END $$;
      CREATE TABLE IF NOT EXISTS public.empire_tenant_role_bindings(
        role_name name PRIMARY KEY, tenant_id uuid NOT NULL,
        active boolean NOT NULL, evidence_ref text,
        created_at timestamptz NOT NULL DEFAULT now());
      CREATE TABLE IF NOT EXISTS public.tenant_business_entity_bindings(
        tenant_id uuid NOT NULL, entity_id uuid NOT NULL,
        binding_kind text NOT NULL, evidence_ref text,
        active boolean NOT NULL, valid_from timestamptz NOT NULL,
        valid_until timestamptz, created_at timestamptz NOT NULL DEFAULT now());
    """)
    # Reset *only disposable fixture* source tables between tests.
    run(f"""
      TRUNCATE public.empire_tenant_role_bindings,
               public.tenant_business_entity_bindings;
      DELETE FROM public.empire_crm_tenant_memberships
      WHERE tenant_id='{TENANT}';
      INSERT INTO public.empire_tenant_role_bindings(role_name,tenant_id,active,evidence_ref)
      VALUES ('empire_intelligence_materializer_login','{TENANT}',true,
              'secret:operator-first-slot');
      INSERT INTO public.tenant_business_entity_bindings
        (tenant_id,entity_id,binding_kind,evidence_ref,active,valid_from)
      VALUES
        ('{TENANT}','00000000-0000-0000-0000-000000000001','observed','private:a',true,now()),
        ('{TENANT}','00000000-0000-0000-0000-000000000002','observed','private:b',true,now()),
        ('{TENANT}','00000000-0000-0000-0000-000000000003','observed','private:c',true,now()),
        ('{TENANT}','00000000-0000-0000-0000-000000000004','observed','private:d',true,now());
    """)
    return run


def test_existing_tenant_role_and_entity_evidence_never_claims_human_ownership(existing_registration):
    run = existing_registration
    raw = run(file=SQL)
    data = _report(raw)
    assert data["schema"] == "empire.crm.founder_existing_tenant_evidence.v1"
    assert data["tenant_id"] == TENANT
    assert data["query_transaction_read_only"] is True
    assert data["role_binding_count"] == 1
    assert data["active_evidenced_role_bindings"] == 1
    assert data["operational_materializer_bindings"] == 1
    assert data["earliest_role_binding_created_at"] is not None
    assert data["entity_binding_count"] == 4
    assert data["active_evidenced_entity_bindings"] == 4
    assert data["active_observed_entity_bindings"] == 4
    assert data["active_owned_entity_bindings"] == 0
    assert data["active_managed_entity_bindings"] == 0
    assert data["crm_memberships"] == 0
    assert data["pending_owner_membership_count"] == 0
    assert data["single_approved_pending_owner_recorded"] is False
    assert data["next_action"] == (
        "REVIEW_INDEPENDENT_FOUNDER_AND_TENANT_EVIDENCE_BEFORE_FIRST_PENDING_MEMBER"
    )
    assert data["crm_credential_records"] == 0
    assert data["human_founder_identity_verified"] is False
    assert data["founder_to_tenant_membership_verified"] is False
    assert data["tenant_key_independently_verified"] is False
    assert data["pilot_activation_authorized"] is False
    assert data["writes_performed"] is False
    for sensitive in ("secret:operator-first-slot", "private:a",
                      "empire_intelligence_materializer_login"):
        assert sensitive not in raw


def test_founder_probe_never_infers_login_from_membership_or_stale_business_evidence(existing_registration):
    run = existing_registration
    run(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (subject,tenant_id,role,status,evidence_ref,verified_at)
      VALUES ('founder:unverified','{TENANT}','owner','active','review-only:subject',now());
      UPDATE public.tenant_business_entity_bindings
      SET active=false WHERE entity_id='00000000-0000-0000-0000-000000000001';
    """)
    raw = run(file=SQL)
    data = _report(raw)
    assert data["crm_memberships"] == 1
    assert data["active_crm_memberships"] == 1
    assert data["pending_owner_membership_count"] == 0
    assert data["single_approved_pending_owner_recorded"] is False
    assert data["next_action"] == (
        "RECONCILE_CRM_MEMBERSHIP_AND_CREDENTIAL_STATE_WITHOUT_ACTIVATION"
    )
    assert data["active_evidenced_entity_bindings"] == 3
    assert data["active_owned_entity_bindings"] == 0
    assert data["human_founder_identity_verified"] is False
    assert data["founder_to_tenant_membership_verified"] is False
    assert "founder:unverified" not in raw
    assert "review-only:subject" not in raw




def test_exact_approved_pending_owner_readback_never_claims_authentication(existing_registration):
    run = existing_registration
    # Use the exact evidence from the previously approved single-row release.
    # This is an EPHEMERAL fixture insert, never a production write.
    run(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (subject,tenant_id,role,status,evidence_ref,verified_at)
      VALUES (
        'founder:phil_livesley','{TENANT}','owner','pending',
        'founder:chat-approved-single-owner-20261010'
        ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
        ||'|tenant:operator-evidence-only-not-legal-proof',
        now()
      );
    """)
    report = _report(run(file=SQL))
    assert report["crm_memberships"] == 1
    assert report["active_crm_memberships"] == 0
    assert report["crm_credential_records"] == 0
    assert report["pending_owner_membership_count"] == 1
    assert report["single_approved_pending_owner_recorded"] is True
    assert report["next_action"] == (
        "VERIFY_HUMAN_AND_TENANT_CONTROL_BEFORE_SEPARATE_ACTIVE_MEMBERSHIP_APPROVAL"
    )
    assert report["human_founder_identity_verified"] is False
    assert report["founder_to_tenant_membership_verified"] is False
    assert report["pilot_activation_authorized"] is False
    assert report["logins_enabled_by_this_probe"] is False
    assert report["writes_performed"] is False


def test_pending_owner_must_match_original_evidence_and_exact_identity(existing_registration):
    run = existing_registration
    for subject, evidence in (
        ("founder:other_person",
         "founder:chat-approved-single-owner-20261010"
         "|identity:connected-gmail-profile-reviewed-ownership-pending"
         "|tenant:operator-evidence-only-not-legal-proof"),
        ("founder:phil_livesley", "fixture:unreviewed-pending-owner"),
    ):
        run(f"""
          INSERT INTO public.empire_crm_tenant_memberships
            (subject,tenant_id,role,status,evidence_ref,verified_at)
          VALUES ('{subject}','{TENANT}','owner','pending',
                  '{evidence}',now());
        """)
        report = _report(run(file=SQL))
        assert report["pending_owner_membership_count"] == 0
        assert report["single_approved_pending_owner_recorded"] is False
        assert report["next_action"] == (
            "RECONCILE_CRM_MEMBERSHIP_AND_CREDENTIAL_STATE_WITHOUT_ACTIVATION"
        )
        run(f"""
          DELETE FROM public.empire_crm_tenant_memberships
          WHERE tenant_id='{TENANT}';
        """)


def test_extra_member_prevents_single_founder_pending_claim(existing_registration):
    run = existing_registration
    run(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (subject,tenant_id,role,status,evidence_ref,verified_at)
      VALUES
        ('founder:phil_livesley','{TENANT}','owner','pending',
         'founder:chat-approved-single-owner-20261010'
         ||'|identity:connected-gmail-profile-reviewed-ownership-pending'
         ||'|tenant:operator-evidence-only-not-legal-proof',now()),
        ('other:person','{TENANT}','viewer','pending','fixture:other',now());
    """)
    report = _report(run(file=SQL))
    assert report["pending_owner_membership_count"] == 1
    assert report["crm_memberships"] == 2
    assert report["single_approved_pending_owner_recorded"] is False
    assert report["next_action"] == (
        "RECONCILE_CRM_MEMBERSHIP_AND_CREDENTIAL_STATE_WITHOUT_ACTIVATION"
    )
    assert report["human_founder_identity_verified"] is False


def test_founder_evidence_probe_has_no_database_mutation_or_sensitive_output():
    sql = SQL.read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in sql
    assert "ROLLBACK;" in sql
    assert "SET LOCAL statement_timeout = '5000ms'" in sql
    assert TENANT in sql
    assert "'tenant_key_independently_verified',false" in sql
    assert "'human_founder_identity_verified',false" in sql
    assert "'pilot_activation_authorized',false" in sql
    assert "'human_founder_identity_verified',false" in sql
    assert "'single_approved_pending_owner_recorded'" in sql
    assert "'pending_owner_membership_count'" in sql
    assert "WHERE subject='founder:phil_livesley'" in sql
    for forbidden in (
        "INSERT INTO", "DELETE FROM", "UPDATE public.", "CREATE ROLE",
        "CREATE TABLE", "ALTER ROLE", "GRANT ", "password_salt",
        "password_digest", "login_email", "SELECT *", "session_user =",
    ):
        assert forbidden not in sql
