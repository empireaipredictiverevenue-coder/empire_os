"""Real PostgreSQL 18, real psycopg and signed bearer; DISPOSABLE fixture only.

No EmpireDB credentials, original CRM customer data, payments, or production
privilege changes. The original login guard is borrowed from the pre-existing
suppression evidence reader, not copied from another owner's dirty source.
"""
from datetime import datetime, timezone
from inspect import getclosurevars

import pytest

from empire_os import revenue_crm_transport as transport
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.crm_scoped_lineage_reader import review_signed_scoped_lineage
from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
from empire_os.revenue_crm_suppression_evidence_reader import CRM_LOGIN_AUTHORITY_SQL
from tests.test_crm_scoped_lineage_sql_ephemeral import pg, P, O, OA, OB, TA, TB
from tests.test_revenue_crm_signed_auth import (
    NOW as AUTH_NOW, live_membership, signed, token,
)

WHEN = datetime(2026, 10, 27, 22, 0, tzinfo=timezone.utc)


def run_original_reader(pg, signed, monkeypatch, *, tenant=TA, order=OA, login="crm_fixture_a"):
    """Create only test signed creds; use actual installed driver on PG fixture."""
    key, pinned = signed
    verifier = SignedCrmTenantVerifier(
        pinned, load_membership=live_membership, now=lambda: AUTH_NOW,
    )
    bearer = token(key, claims={"tenant_id": tenant})
    # This exact existing owner contract exists independently of the unpublished
    # CRM transport module and cannot provide any tenant data itself.
    monkeypatch.setattr(transport, "CRM_LOGIN_AUTHORITY_SQL", CRM_LOGIN_AUTHORITY_SQL, raising=False)
    db = getclosurevars(pg).nonlocals
    assert db["address"].startswith("/tmp/empire-lineage-fixture-")
    assert 1024 <= db["port"] <= 65535
    dsn = (
        f"host={db['address']} port={db['port']} "
        f"dbname=crm_exact_lineage_fixture user={login}"
    )
    return review_signed_scoped_lineage(
        signed_crm_bearer=bearer,
        crm_verifier=verifier,
        dedicated_crm_dsn=dsn,
        prospect_id=P,
        opportunity_id=O,
        evidence_id=order,
        evidence_kind="order",
        as_of=WHEN,
    )


def test_real_original_crm_signed_reader_and_exact_order_rpc(pg, signed, monkeypatch):
    receipt = run_original_reader(pg, signed, monkeypatch)
    assert receipt["schema_version"] == "empire.crm.scoped_lineage_review.v1"
    assert receipt["status"] == "EXACT_TENANT_SCOPED_RECEIPT_OBSERVED_NOT_PROMOTED"
    assert receipt["tenant_id"] == TA
    assert receipt["receipt_id"] == OA
    assert receipt["receipt_kind"] == "order"
    assert receipt["signed_crm_membership_verified"] is True
    assert receipt["original_db_tenant_scope_checked"] is True
    assert receipt["real_database_connector_used"] is True
    for key in ("buyer_terms_verified", "buyer_capacity_verified",
                "source_rights_verified", "settlement_verified",
                "recognised_revenue_verified", "database_writes",
                "outbound_authorized"):
        assert receipt[key] is False


def test_second_signed_tenant_cannot_read_first_tenants_order(
    pg, signed, monkeypatch,
):
    with pytest.raises(ProspectHandoffHold, match="ONE_EXACT_AUTHORIZED_LINEAGE_RECEIPT_REQUIRED"):
        run_original_reader(pg, signed, monkeypatch, tenant=TB, order=OA,
                            login="crm_fixture_b")


def test_cross_tenant_order_hidden_even_with_valid_signed_tenant(
    pg, signed, monkeypatch,
):
    with pytest.raises(ProspectHandoffHold, match="ONE_EXACT_AUTHORIZED_LINEAGE_RECEIPT_REQUIRED"):
        run_original_reader(pg, signed, monkeypatch, order=OB)


def test_signed_tenant_and_database_session_user_must_match(
    pg, signed, monkeypatch,
):
    with pytest.raises(ProspectHandoffHold, match="CRM_SESSION_TENANT_SCOPE_MISMATCH"):
        run_original_reader(pg, signed, monkeypatch, tenant=TB,
                            login="crm_fixture_a", order=OB)


def test_valid_signed_tenant_without_database_tenant_binding_is_held(
    pg, signed, monkeypatch,
):
    with pytest.raises(ProspectHandoffHold, match="CRM_SESSION_TENANT_SCOPE_MISMATCH"):
        run_original_reader(pg, signed, monkeypatch,
                            login="crm_fixture_unbound")


def test_revoked_original_binding_immediately_hides_signed_order(
    pg, signed, monkeypatch,
):
    run_original_reader(pg, signed, monkeypatch)
    try:
        pg(sql=f"UPDATE public.empire_tenant_role_bindings SET active=false WHERE tenant_id='{TA}'::uuid")
        with pytest.raises(ProspectHandoffHold, match="CRM_SESSION_TENANT_SCOPE_MISMATCH"):
            run_original_reader(pg, signed, monkeypatch)
    finally:
        pg(sql=f"UPDATE public.empire_tenant_role_bindings SET active=true WHERE tenant_id='{TA}'::uuid")
    run_original_reader(pg, signed, monkeypatch)


# Test-only view with the exact original CRM prospect projection. This lives
# ONLY in the disposable instance supplied by the existing module fixture.
PROSPECT_VIEW_SQL = """
SET ROLE empiredb_migrator;
CREATE OR REPLACE VIEW public.revenue_crm_prospects AS
SELECT buyer.org_id AS tenant_id, o.prospect_id,
       'isolated_fixture_only'::text AS business_name,
       NULL::text AS niche, NULL::text AS metro,
       'fixture'::text AS prospect_status,
       NULL::text AS conversation_id, NULL::text AS conversation_channel,
       NULL::text AS conversation_state,
       NULL::timestamptz AS conversation_updated_at,
       NULL::text AS closer_case_id, NULL::text AS closer_state,
       NULL::timestamptz AS closer_updated_at,
       o.id AS fulfilment_order_id, 'paid'::text AS fulfilment_state,
       NULL::timestamptz AS fulfilment_updated_at,
       12000::int AS price_cents, o.buyer_id,
       NULL::text AS buyer_activation_state,
       NULL::int AS buyer_available_capacity,
       NULL::timestamptz AS buyer_capacity_verified_at,
       NULL::numeric AS deal_probability
FROM public.fulfilment_orders o
JOIN public.buyers buyer ON buyer.id=o.buyer_id
WHERE buyer.org_id=public.empire_current_tenant_id();
GRANT SELECT ON public.revenue_crm_prospects TO empire_revenue_crm_reader;
RESET ROLE;
"""


def test_original_signed_order_to_actual_bridge_and_redacted_founder_case(
    pg, signed, monkeypatch,
):
    from empire_os.crm_revenue_case_bridge import review_signed_crm_revenue_case
    pg(sql=PROSPECT_VIEW_SQL)
    key, pinned = signed
    verifier = SignedCrmTenantVerifier(
        pinned, load_membership=live_membership, now=lambda: AUTH_NOW,
    )
    monkeypatch.setattr(
        transport, "CRM_LOGIN_AUTHORITY_SQL", CRM_LOGIN_AUTHORITY_SQL,
        raising=False,
    )
    database = getclosurevars(pg).nonlocals
    assert database["address"].startswith("/tmp/empire-lineage-fixture-")
    dsn = (
        f"host={database['address']} port={database['port']} "
        "dbname=crm_exact_lineage_fixture user=crm_fixture_a"
    )
    report = review_signed_crm_revenue_case(
        signed_crm_bearer=token(key, claims={"tenant_id": TA}),
        crm_verifier=verifier,
        dedicated_crm_dsn=dsn,
        prospect_id=P,
        opportunity_id=O,
        fulfilment_order_id=OA,
        as_of=WHEN,
    )
    assert report["status"] == "ORIGINAL_SIGNED_CRM_ORDER_OBSERVED_REVIEW_ONLY"
    assert report["tenant_id"] == TA
    assert report["fulfilment_order_id"] == OA
    case = report["revenue_case"]
    assert case["next_missing_stage"] == "BUYER_ACCEPTANCE"
    assert case["source_reported_recognizer_event"] is False
    assert case["revenue_recognized_here"] is False
    assert case["eligible_for_learning"] is False
    display = report["founder_case_view"]
    assert display["reported_order_state"] == "paid"
    assert display["next_missing_stage"] == "BUYER_ACCEPTANCE"
    assert display["recognized_revenue_verified_here"] is False
    assert display["independent_evidence_attested_here"] is False
    assert "tenant_id" not in display
    assert "fulfilment_order_id" not in display
    assert "bearer" not in display
    assert "database_writes" in display and display["database_writes"] is False


@pytest.mark.parametrize("role_mutation,undo", [
    (
        "ALTER ROLE crm_fixture_a INHERIT",
        "ALTER ROLE crm_fixture_a NOINHERIT",
    ),
    (
        "ALTER ROLE crm_fixture_a BYPASSRLS",
        "ALTER ROLE crm_fixture_a NOBYPASSRLS",
    ),
    (
        "ALTER ROLE crm_fixture_a CREATEDB",
        "ALTER ROLE crm_fixture_a NOCREATEDB",
    ),
    (
        "REVOKE empire_revenue_crm_reader FROM crm_fixture_a",
        "GRANT empire_revenue_crm_reader TO crm_fixture_a",
    ),
])
def test_signed_order_blocks_privileged_or_unbound_dedicated_login(
    pg, signed, monkeypatch, role_mutation, undo,
):
    """Every mutation is confined to the throwaway PostgreSQL 18 fixture."""
    run_original_reader(pg, signed, monkeypatch)
    try:
        pg(sql=role_mutation)
        with pytest.raises(
            ProspectHandoffHold,
            match="RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED",
        ):
            run_original_reader(pg, signed, monkeypatch)
    finally:
        pg(sql=undo)
    run_original_reader(pg, signed, monkeypatch)


def test_signed_order_blocks_secondary_group_membership(
    pg, signed, monkeypatch,
):
    """A dedicated login cannot also inherit or switch to a second role."""
    run_original_reader(pg, signed, monkeypatch)
    pg(sql="CREATE ROLE crm_fixture_unrelated NOLOGIN")
    try:
        pg(sql="GRANT crm_fixture_unrelated TO crm_fixture_a")
        with pytest.raises(
            ProspectHandoffHold,
            match="RESTRICTED_CRM_READER_ROLE_NOT_ATTESTED",
        ):
            run_original_reader(pg, signed, monkeypatch)
    finally:
        pg(sql="REVOKE crm_fixture_unrelated FROM crm_fixture_a")
        pg(sql="DROP ROLE crm_fixture_unrelated")
    run_original_reader(pg, signed, monkeypatch)
