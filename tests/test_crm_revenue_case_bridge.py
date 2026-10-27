"""V11 original signed CRM connection: offline owner-interface contract tests."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

import empire_os.crm_revenue_case_bridge as bridge
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from empire_os.revenue_crm_transport import RevenueCrmTransportError
from tests.test_crm_scoped_lineage_reader_20261026 import signed_auth
from tests.test_canonical_order_lineage_review_20261026 import (
    ORDER, OPPORTUNITY,
)
from tests.test_canonical_prospect_tenant_handoff_20261026 import (
    PROSPECT, ENTITY, TENANT, NOW,
)

BUYER = "00000000-0000-0000-0000-0000000000a2"
OTHER = "00000000-0000-0000-0000-0000000000e1"


def rpc_receipt():
    return dict(
        schema_version="empire.crm.scoped_lineage_review.v1",
        status="EXACT_TENANT_SCOPED_RECEIPT_OBSERVED_NOT_PROMOTED",
        mode="OBSERVE", tenant_id=TENANT, receipt_id=ORDER,
        prospect_id=PROSPECT, entity_id=ENTITY, buyer_id=BUYER,
        opportunity_id=OPPORTUNITY, receipt_kind="order",
        signed_crm_membership_verified=True,
        original_db_tenant_scope_checked=True,
        real_database_connector_used=True,
        source_rights_verified=False, buyer_terms_verified=False,
        buyer_capacity_verified=False, settlement_verified=False,
        recognised_revenue_verified=False, database_writes=False,
        outbound_authorized=False, execution_authority="NONE",
    )


def crm_view(state="accepted"):
    return dict(
        tenant_id=TENANT, prospect_id=PROSPECT, buyer_id=BUYER,
        fulfilment_order_id=ORDER, fulfilment_state=state,
    )


def prepare(monkeypatch, *, rpc=None, view=None):
    reads = {"rpc": [], "view": []}
    if rpc is None:
        rpc = rpc_receipt()
    if view is None:
        view = crm_view()
    def fake_rpc(**kwargs):
        reads["rpc"].append(kwargs)
        return deepcopy(rpc)
    class ScopedView:
        def __init__(self, dsn, *, tenant_id):
            reads["view"].append(("connect", dsn, tenant_id))
            assert dsn == "TEST_ONLY"
            assert tenant_id == TENANT
        def prospect(self, prospect_id):
            reads["view"].append(("prospect", prospect_id))
            assert prospect_id == PROSPECT
            return deepcopy(view)
    monkeypatch.setattr(bridge, "review_signed_scoped_lineage", fake_rpc)
    monkeypatch.setattr(bridge, "PostgresRevenueCrmRepository", ScopedView)
    return reads


def review(signed_auth):
    verifier, token = signed_auth
    return bridge.review_signed_crm_revenue_case(
        signed_crm_bearer=token, crm_verifier=verifier,
        dedicated_crm_dsn="TEST_ONLY",
        prospect_id=PROSPECT, opportunity_id=OPPORTUNITY,
        fulfilment_order_id=ORDER, as_of=NOW,
    )


@pytest.mark.parametrize("state", ("raw", "accepted", "paid", "settled", "outcome_captured"))
def test_one_genuine_owner_interface_receipt_shows_only_unverified_order_state(
    monkeypatch, signed_auth, state
):
    reads = prepare(monkeypatch, view=crm_view(state))
    report = review(signed_auth)
    assert report["schema_version"] == bridge.SCHEMA
    assert report["status"] == "ORIGINAL_SIGNED_CRM_ORDER_OBSERVED_REVIEW_ONLY"
    assert report["revenue_case"]["original_crm_order_state_reported"] == state
    assert report["revenue_case"]["authenticated_crm_order_observed"] is True
    assert report["revenue_case"]["next_missing_stage"] == "BUYER_ACCEPTANCE"
    assert report["revenue_case"]["source_reported_recognizer_event"] is False
    assert report["revenue_case"]["eligible_for_learning"] is False
    assert report["revenue_case"]["revenue_recognized_here"] is False
    assert len(report["revenue_case"]["source_handoff_stages"]) == 5
    assert all(s["status"] == "NOT_OBSERVED"
               for s in report["revenue_case"]["source_handoff_stages"])
    assert report["database_writes"] is False
    assert report["payments_executed"] is False
    assert reads["rpc"][0]["evidence_kind"] == "order"
    assert reads["rpc"][0]["evidence_id"] == ORDER
    assert "connect_factory" not in reads["rpc"][0]
    assert reads["view"] == [("connect", "TEST_ONLY", TENANT), ("prospect", PROSPECT)]


@pytest.mark.parametrize("field,bad", [
    ("status", "INJECTED_SCOPED_RPC_TEST_ONLY"),
    ("mode", "EXECUTE"),
    ("receipt_kind", "event"),
    ("receipt_id", OTHER),
    ("prospect_id", OTHER),
    ("opportunity_id", OTHER),
    ("signed_crm_membership_verified", False),
    ("original_db_tenant_scope_checked", False),
    ("real_database_connector_used", False),
    ("source_rights_verified", True),
    ("buyer_terms_verified", True),
    ("settlement_verified", True),
    ("outbound_authorized", True),
    ("database_writes", True),
    ("execution_authority", "EXECUTE"),
])
def test_untrusted_original_rpc_never_queries_crm_view(
    monkeypatch, signed_auth, field, bad
):
    rpc = rpc_receipt()
    rpc[field] = bad
    reads = prepare(monkeypatch, rpc=rpc)
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_SIGNED_ORDER_RPC_NOT_ATTESTED"):
        review(signed_auth)
    assert reads["view"] == []


@pytest.mark.parametrize("field,bad", [
    ("tenant_id", OTHER),
    ("prospect_id", OTHER),
    ("buyer_id", OTHER),
    ("fulfilment_order_id", OTHER),
])
def test_prospect_view_cannot_rebind_another_tenant_buyer_or_order(
    monkeypatch, signed_auth, field, bad
):
    view = crm_view()
    view[field] = bad
    prepare(monkeypatch, view=view)
    with pytest.raises(ProspectHandoffHold, match="CRM_VIEW_AND_SIGNED_ORDER_IDENTITY_MISMATCH"):
        review(signed_auth)


def test_missing_restricted_crm_rpc_fails_closed_before_view(
    monkeypatch, signed_auth
):
    reads = prepare(monkeypatch)
    def held(**_):
        raise ProspectHandoffHold("ORIGINAL_TENANT_SCOPED_RPC_NOT_RELEASED")
    monkeypatch.setattr(bridge, "review_signed_scoped_lineage", held)
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_TENANT_SCOPED_RPC_NOT_RELEASED"):
        review(signed_auth)
    assert reads["view"] == []


def test_original_prospect_view_unavailable_never_infers_order(
    monkeypatch, signed_auth
):
    prepare(monkeypatch)
    class FailReader:
        def __init__(self, *args, **kwargs):
            pass
        def prospect(self, *_):
            raise RevenueCrmTransportError("no authorised read")
    monkeypatch.setattr(bridge, "PostgresRevenueCrmRepository", FailReader)
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_TENANT_SCOPED_PROSPECT_VIEW_UNAVAILABLE"):
        review(signed_auth)


def test_missing_prospect_is_not_an_order(monkeypatch, signed_auth):
    prepare(monkeypatch, view=False)
    class EmptyReader:
        def __init__(self, *_a, **_kw):
            pass
        def prospect(self, _):
            return None
    monkeypatch.setattr(bridge, "PostgresRevenueCrmRepository", EmptyReader)
    with pytest.raises(ProspectHandoffHold, match="EXACT_ORIGINAL_CRM_PROSPECT_VIEW_ROW_REQUIRED"):
        review(signed_auth)


@pytest.mark.parametrize("state", ("unknown", True, 7, "INJECTED_PAYMENT_COMPLETE"))
def test_unrecognized_crm_order_state_never_proves_revenue(
    monkeypatch, signed_auth, state
):
    prepare(monkeypatch, view=crm_view(state))
    with pytest.raises(ProspectHandoffHold, match="INVALID_ORIGINAL_CRM_ORDER_STATE"):
        review(signed_auth)


def test_bad_ids_and_non_original_verifier_fail_before_authentication(
    monkeypatch, signed_auth
):
    reads = prepare(monkeypatch)
    verifier, token = signed_auth
    with pytest.raises(ProspectHandoffHold, match="EXACT_CANONICAL_CRM_CASE_IDS_REQUIRED"):
        bridge.review_signed_crm_revenue_case(
            signed_crm_bearer=token, crm_verifier=verifier,
            dedicated_crm_dsn="TEST_ONLY",
            prospect_id="research:unverified", opportunity_id=OPPORTUNITY,
            fulfilment_order_id=ORDER, as_of=NOW,
        )
    with pytest.raises(ProspectHandoffHold, match="ORIGINAL_SIGNED_CRM_VERIFIER_REQUIRED"):
        bridge.review_signed_crm_revenue_case(
            signed_crm_bearer=token, crm_verifier=SimpleNamespace(),
            dedicated_crm_dsn="TEST_ONLY", prospect_id=PROSPECT,
            opportunity_id=OPPORTUNITY, fulfilment_order_id=ORDER,
            as_of=NOW,
        )
    assert reads["rpc"] == []
    assert reads["view"] == []
