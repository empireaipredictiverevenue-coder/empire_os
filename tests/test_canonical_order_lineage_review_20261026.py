"""Exactly linked original GTM/order and prospect/entity/tenant READ ONLY.

Fixture IDs and synthetic source data are never inserted into EmpireDB.
"""
import pytest
from datetime import datetime, timezone, timedelta
from empire_os.canonical_order_lineage_review import (
    review_existing_order_opportunity_lineage,
)
from empire_os.canonical_prospect_tenant_handoff import ProspectHandoffHold
from tests.test_canonical_prospect_tenant_handoff_20261026 import (
    FakeReadOnlyCursor, TENANT, ENTITY, PROSPECT, NOW,
)

OPPORTUNITY = "44444444-4444-4444-8444-444444444444"
ORDER = "55555555-5555-4555-8555-555555555555"

class OriginalOrderReadOnlyCursor(FakeReadOnlyCursor):
    def __init__(self, *, orders=None, opportunities=None, **kwargs):
        super().__init__(**kwargs)
        self.orders = [(ORDER, OPPORTUNITY, PROSPECT, ENTITY, None, "raw")] if orders is None else orders
        self.opportunities = [(OPPORTUNITY, "discovered")] if opportunities is None else opportunities
    def fetchall(self):
        stmt=self.queries[-1][0].lower()
        if "from public.gtm_opportunities" in stmt:
            return self.opportunities
        if "from public.fulfilment_orders" in stmt:
            return self.orders
        return super().fetchall()

def run(cursor=None, **changes):
    params=dict(
        cursor=cursor if cursor is not None else OriginalOrderReadOnlyCursor(),
        order_id=ORDER, opportunity_id=OPPORTUNITY,
        prospect_id=PROSPECT, entity_id=ENTITY,
        authenticated_tenant_id=TENANT, as_of=NOW,
    )
    params.update(changes)
    return review_existing_order_opportunity_lineage(**params)

def test_exact_existing_order_triple_has_source_and_tenant_continuity():
    cur=OriginalOrderReadOnlyCursor()
    r=run(cur)
    assert r["source_and_order_record_identity_consistent"] is True
    assert (r["opportunity_id"],r["fulfilment_order_id"]) == (OPPORTUNITY,ORDER)
    assert len(cur.queries) == 5
    assert r["original_order_state_reported"] == "raw"
    assert r["original_gtm_status_reported"] == "discovered"
    assert r["original_crm_reader_login_attested_by_this_function"] is False
    for name in ("buyer_capacity_verified","fulfilment_verified",
                 "payment_receipt_verified","settlement_finality_verified",
                 "realised_revenue_verified","outbound_authorized",
                 "database_writes"):
        assert r[name] is False
    assert r["execution_authority"] == "NONE"

@pytest.mark.parametrize("changes, expected", [
    ({"orders":[]}, "EXACT_EXISTING_FULFILMENT_ORDER_REQUIRED"),
    ({"opportunities":[]}, "EXACT_EXISTING_GTM_OPPORTUNITY_REQUIRED"),
    ({"orders":[(ORDER,OPPORTUNITY,PROSPECT,"99999999-9999-4999-8999-999999999999",None,"raw")]}, "CANONICAL_ORDER_LINEAGE_MISMATCH"),
    ({"orders":[(ORDER,"99999999-9999-4999-8999-999999999999",PROSPECT,ENTITY,None,"raw")]}, "CANONICAL_ORDER_LINEAGE_MISMATCH"),
    ({"orders":[(ORDER,OPPORTUNITY,None,ENTITY,None,"raw")]}, "CANONICAL_ORDER_LINEAGE_MISMATCH"),
    ({"orders":[(ORDER,OPPORTUNITY,PROSPECT,ENTITY,None,"invented_state")]}, "CANONICAL_ORDER_LINEAGE_MISMATCH"),
    ({"orders":[(ORDER,OPPORTUNITY,PROSPECT,ENTITY,None,"raw"),(ORDER,OPPORTUNITY,PROSPECT,ENTITY,None,"raw")]}, "EXACT_EXISTING_FULFILMENT_ORDER_REQUIRED"),
])
def test_missing_ambiguous_and_cross_entity_order_not_promoted(changes,expected):
    with pytest.raises(ProspectHandoffHold,match=expected):
        run(OriginalOrderReadOnlyCursor(**changes))

def test_paid_text_does_not_confirm_money_or_customer_delivery():
    r=run(OriginalOrderReadOnlyCursor(
        orders=[(ORDER,OPPORTUNITY,PROSPECT,ENTITY,TENANT,"settled")]))
    assert r["original_order_state_reported"]=="settled"
    assert r["buyer_id_present_on_order"] is True
    assert r["payment_receipt_verified"] is False
    assert r["realised_revenue_verified"] is False
    assert r["fulfilment_verified"] is False

def test_source_link_conflict_or_wrong_tenant_blocks_even_real_order():
    with pytest.raises(ProspectHandoffHold,match="OPEN_IDENTITY_CONFLICT_HOLD"):
        run(OriginalOrderReadOnlyCursor(conflicts=[("unresolved",)]))
    with pytest.raises(ProspectHandoffHold,match="ACTIVE_TENANT_BUSINESS_BINDING_REQUIRED"):
        run(OriginalOrderReadOnlyCursor(bindings=[]))

def test_missing_order_uuid_fails_before_cursor_query():
    cur=OriginalOrderReadOnlyCursor()
    with pytest.raises(ProspectHandoffHold,match="INVALID_ORDER_ID"):
        run(cur,order_id="research_review:not-a-order")
    assert cur.queries==[]

def test_signed_crm_adapter_requires_complete_exact_order_pair():
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    with pytest.raises(ProspectHandoffHold,match="EXACT_ORDER_AND_GTM_ID_PAIR_REQUIRED"):
        review_signed_crm_prospect_tenant(
            signed_crm_bearer="bad",crm_verifier=object(),
            dedicated_crm_dsn="TEST_ONLY",prospect_id=PROSPECT,
            entity_id=ENTITY,as_of=NOW,order_id=ORDER,
        )


EVENT = "66666666-6666-4666-8666-666666666666"

class OriginalEventReadOnlyCursor(OriginalOrderReadOnlyCursor):
    def __init__(self, *, events=None, **kwargs):
        super().__init__(**kwargs)
        self.events = [(EVENT,"opportunity_reviewed",OPPORTUNITY,PROSPECT,ENTITY,None)] if events is None else events
    def fetchall(self):
        stmt=self.queries[-1][0].lower()
        if "from public.commercial_events" in stmt:
            return self.events
        return super().fetchall()

def test_existing_pre_order_commercial_event_is_valid_intermediate_receipt():
    from empire_os.canonical_order_lineage_review import review_existing_commercial_event_lineage
    c=OriginalEventReadOnlyCursor()
    r=review_existing_commercial_event_lineage(
        c,event_id=EVENT,opportunity_id=OPPORTUNITY,
        prospect_id=PROSPECT,entity_id=ENTITY,
        authenticated_tenant_id=TENANT,as_of=NOW,
    )
    assert len(c.queries)==5
    assert r["source_and_event_record_identity_consistent"] is True
    assert r["event_type_reported"]=="opportunity_reviewed"
    assert r["existing_order_verified"] is False
    assert r["commercial_terms_approved"] is False
    assert r["revenue_verified"] is False
    assert r["execution_authority"]=="NONE"

@pytest.mark.parametrize("events,expected",[
    ([], "EXACT_EXISTING_COMMERCIAL_EVENT_REQUIRED"),
    ([(EVENT,"opportunity_reviewed",OPPORTUNITY,PROSPECT,
       "77777777-7777-4777-8777-777777777777",None)],
       "COMMERCIAL_EVENT_CANONICAL_LINEAGE_MISMATCH"),
    ([(EVENT,"opportunity_reviewed",
       "77777777-7777-4777-8777-777777777777",PROSPECT,ENTITY,None)],
       "COMMERCIAL_EVENT_CANONICAL_LINEAGE_MISMATCH"),
    ([(EVENT,"",OPPORTUNITY,PROSPECT,ENTITY,None)],
       "COMMERCIAL_EVENT_CANONICAL_LINEAGE_MISMATCH"),
])
def test_pre_order_event_missing_or_cross_entity_held(events,expected):
    from empire_os.canonical_order_lineage_review import review_existing_commercial_event_lineage
    with pytest.raises(ProspectHandoffHold, match=expected):
        review_existing_commercial_event_lineage(
            OriginalEventReadOnlyCursor(events=events),
            event_id=EVENT, opportunity_id=OPPORTUNITY,
            prospect_id=PROSPECT, entity_id=ENTITY,
            authenticated_tenant_id=TENANT, as_of=NOW,
        )

def test_signed_reader_requires_specific_event_pair_before_connect():
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    for extra, code in [
        ({"event_id":EVENT},"EXACT_EVENT_AND_GTM_ID_PAIR_REQUIRED"),
        ({"opportunity_id":OPPORTUNITY},"EXACT_GTM_RECEIPT_REQUIRED"),
        ({"event_id":EVENT,"order_id":ORDER,"opportunity_id":OPPORTUNITY},
         "ONE_ORIGINAL_EVENT_OR_ORDER_RECEIPT_REQUIRED"),
    ]:
        with pytest.raises(ProspectHandoffHold, match=code):
            review_signed_crm_prospect_tenant(
                signed_crm_bearer="bad",crm_verifier=object(),
                dedicated_crm_dsn="TEST_ONLY",prospect_id=PROSPECT,
                entity_id=ENTITY,as_of=NOW,**extra,
            )


def test_original_signed_crm_session_selects_exact_event_or_order_handoff(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from empire_os import revenue_crm_transport
    from empire_os.revenue_crm_signed_auth import SignedCrmTenantVerifier
    from empire_os.canonical_prospect_tenant_handoff import review_signed_crm_prospect_tenant
    from tests.test_revenue_crm_signed_auth import token, NOW as AUTH_NOW, live_membership
    from tests.test_canonical_prospect_tenant_handoff_20261026 import FakeAuthCursor, FakeConnection

    # The original CRM owner's new login guard has not yet been committed.
    # Simulate only the public interface in this fixture; no real DB claim.
    monkeypatch.setattr(revenue_crm_transport, "CRM_LOGIN_AUTHORITY_SQL",
                        "SELECT pg_catalog.pg_has_role(session_user, fake_test_role)",
                        raising=False)
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    verifier=SignedCrmTenantVerifier(
        {"issuer-1":public}, load_membership=live_membership,
        now=lambda:AUTH_NOW,
    )
    signed=token(private,claims={"tenant_id":TENANT})

    class CommerceCursor(FakeAuthCursor):
        def fetchall(self):
            query=self.queries[-1][0].lower()
            if "from public.gtm_opportunities" in query:
                return [(OPPORTUNITY,"discovered")]
            if "from public.commercial_events" in query:
                return [(EVENT,"opportunity_reviewed",OPPORTUNITY,PROSPECT,ENTITY,None)]
            if "from public.fulfilment_orders" in query:
                return [(ORDER,OPPORTUNITY,PROSPECT,ENTITY,None,"raw")]
            return super().fetchall()

    def call(**kwargs):
        return review_signed_crm_prospect_tenant(
            signed_crm_bearer=signed, crm_verifier=verifier,
            dedicated_crm_dsn="TEST_ONLY",
            prospect_id=PROSPECT,entity_id=ENTITY,as_of=NOW,
            connect_factory=lambda *a,**kw: FakeConnection(CommerceCursor()),
            opportunity_id=OPPORTUNITY,**kwargs,
        )
    event=call(event_id=EVENT)
    order=call(order_id=ORDER)
    assert event["event_id"]==EVENT
    assert order["fulfilment_order_id"]==ORDER
    for row in (event,order):
        assert row["signed_crm_active_membership_verified"] is True
        assert row["restricted_db_session_role_and_tenant_checked"] is True
        assert row["real_database_connector_independently_attested"] is False
        assert row["status"]=="INJECTED_CONNECTOR_RESEARCH_ONLY"
        assert row["outbound_authorized"] is False
        assert row["database_writes"] is False
