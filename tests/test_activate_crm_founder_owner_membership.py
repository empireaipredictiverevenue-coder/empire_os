"""Founder-approved existing 041 membership-only activation on disposable PG18.

No production DBA privileges, live EmpireDB writes, HTTP activation or mail.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from test_crm_membership_authority_ephemeral import membership_pg
from test_provision_crm_founder_owner_pending import pg

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "scripts/provision_crm_founder_owner_pending.sql"
ACTIVATE = ROOT / "scripts/activate_crm_founder_owner_membership.sql"
TENANT = "708efd4b-53b2-43d7-961d-1cecab67f17a"
SUBJECT = "founder:phil_livesley"


def _state(run) -> str:
    return run(f"""
      SELECT
        (SELECT count(*) FROM public.empire_crm_tenant_memberships)::text
        ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
          WHERE tenant_id='{TENANT}' AND subject='{SUBJECT}'
             AND role='owner' AND status='pending')
        ||'|'||(SELECT count(*) FROM public.empire_crm_tenant_memberships
          WHERE tenant_id='{TENANT}' AND subject='{SUBJECT}'
             AND role='owner' AND status='active')
        ||'|'||(SELECT count(*) FROM public.empire_crm_login_credentials)
    """)


def _prepare(run):
    run(file=PENDING, user="postgres")
    assert _state(run) == "1|1|0|0"


def test_one_authorised_status_transition_only(pg):
    _prepare(pg)
    first_evidence = pg(f"""
      SELECT evidence_ref FROM public.empire_crm_tenant_memberships
       WHERE tenant_id='{TENANT}' AND subject='{SUBJECT}'
    """)
    receipt=pg(file=ACTIVATE, user="postgres")
    assert '"membership_status": "active"' in receipt or '"membership_status":"active"' in receipt
    assert _state(pg) == "1|0|1|0"
    final_evidence = pg(f"""
      SELECT evidence_ref FROM public.empire_crm_tenant_memberships
       WHERE tenant_id='{TENANT}' AND subject='{SUBJECT}'
    """)
    assert final_evidence.startswith(first_evidence + "|")
    assert "chat-approved-pending-to-active-20261010" in final_evidence
    assert "two-authoritative-nameservers-confirmed-20261010" in final_evidence
    assert pg("SELECT rolcanlogin FROM pg_roles WHERE rolname='empire_crm_auth_login'") == "f"
    assert pg("SELECT rolcanlogin FROM pg_roles WHERE rolname='empire_crm_membership_login'") == "f"
    assert pg("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'empire_crm_tenant_%' AND rolcanlogin") == "0"
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "1|0|1|0"


def test_unprivileged_session_cannot_activate(pg):
    _prepare(pg)
    assert "COMMIT" not in pg(file=ACTIVATE, user="ubuntu", check=False)
    assert _state(pg) == "1|1|0|0"


def test_absent_pending_record_cannot_activate(pg):
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "0|0|0|0"


def test_modified_identity_or_evidence_cannot_activate(pg):
    _prepare(pg)
    pg(f"""
      UPDATE public.empire_crm_tenant_memberships
         SET evidence_ref='test:tampers-original'
       WHERE tenant_id='{TENANT}' AND subject='{SUBJECT}'
    """)
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "1|1|0|0"


def test_second_membership_aborts_exact_activation(pg):
    _prepare(pg)
    pg(f"""
      INSERT INTO public.empire_crm_tenant_memberships
        (tenant_id,subject,role,status,evidence_ref,verified_at)
      VALUES ('{TENANT}','other:person','viewer','pending','fixture:other',now())
    """)
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "2|1|0|0"


def test_credential_preexisting_blocks_activation(pg):
    _prepare(pg)
    pg(f"""
      INSERT INTO public.empire_crm_login_credentials
      (subject,login_email,password_salt,password_digest,status,evidence_ref,
       verified_at,invitation_tenant_id,invitation_token_hash,
       invitation_expires_at)
      VALUES
      ('other:person','other@example.org',
       decode(repeat('ab',32),'hex'),decode(repeat('cd',64),'hex'),
       'pending','fixture:existing',now(),'{TENANT}',
       decode(repeat('ef',32),'hex'),now()+interval '1 hour');
    """)
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "1|1|0|1"


def test_materializer_tenant_authority_removed_blocks(pg):
    _prepare(pg)
    pg("DELETE FROM public.empire_tenant_role_bindings")
    assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
    assert _state(pg) == "1|1|0|0"


def test_disabled_crm_identity_roles_guarded(pg):
    _prepare(pg)
    try:
        pg("ALTER ROLE empire_crm_auth_login LOGIN")
        assert "COMMIT" not in pg(file=ACTIVATE, user="postgres", check=False)
        assert _state(pg) == "1|1|0|0"
    finally:
        pg("ALTER ROLE empire_crm_auth_login NOLOGIN")


def test_only_exact_membership_table_update_permitted():
    sql=ACTIVATE.read_text()
    assert sql.count("UPDATE public.empire_crm_tenant_memberships") == 1
    assert "WHERE tenant_id=tenant AND subject=person" in sql
    assert "AND evidence_ref=original_evidence" in sql
    assert "GET DIAGNOSTICS affected = ROW_COUNT" in sql
    assert "IF affected <> 1" in sql
    assert "LOCK TABLE public.empire_crm_tenant_memberships" in sql
    assert "CRM_IDENTITY_ROLES_NOT_DORMANT" in sql
    assert "BEGIN;" in sql and "COMMIT;" in sql
    assert "tenant_business_entity_bindings" not in sql
    for forbidden in (
        "ALTER ROLE", "GRANT ", "INSERT INTO",
        "DELETE FROM", "CREATE ROLE", "DROP TABLE",
        "UPDATE public.empire_crm_login_credentials",
    ):
        assert forbidden not in sql
