from datetime import datetime, timezone

from empire_os.digital_avatar_canonical_evidence import (
    CanonicalCommercialEvidenceResolver,
    CanonicalCommercialOutcomeResolver,
    CanonicalCommercialProductResolver,
    CanonicalCommercialTermsResolver,
)


EVIDENCE_ID = "11111111-1111-4111-8111-111111111111"
REVIEW_ID = "22222222-2222-4222-8222-222222222222"


class Gateway:
    def __init__(self, *, rows=None, rpc_value=None):
        self.rows = list(rows or [])
        self.rpc_value = rpc_value
        self.query_calls = []
        self.rpc_calls = []

    def query(self, table, columns, **kwargs):
        self.query_calls.append((table, columns, kwargs))
        return list(self.rows)

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        return self.rpc_value


def price_row(**overrides):
    row = {
        "id": EVIDENCE_ID,
        "evidence_kind": "price",
        "niche": "roofing",
        "metro": "London",
        "amount_cents": 49900,
        "currency": "USD",
        "unit": "per_month",
        "source_type": "founder_approved",
        "status": "verified",
        "valid_until": "2027-01-01T00:00:00+00:00",
        "verified_at": "2026-10-01T12:00:00+00:00",
    }
    row.update(overrides)
    return row


def terms_row(**overrides):
    row = {
        "review_id": REVIEW_ID,
        "fulfilment_order_id": "33333333-3333-4333-8333-333333333333",
        "status": "approved",
        "price_cents": 500000,
        "acquisition_cost_cents": 100000,
        "fulfilment_cost_cents": 75000,
        "expected_margin_cents": 325000,
        "terms": {
            "currency": "USD",
            "settlement_asset": "USDT",
            "settlement_chain": "BSC",
            "product_id": "44444444-4444-4444-8444-444444444444",
            "product_code": "PREDICTIVE-REVENUE-PILOT",
            "territory": "UK",
            "daily_cap": 25,
            "delivery_route": "api",
            "price_cents": 500000,
            "acquisition_cost_cents": 100000,
            "fulfilment_cost_cents": 75000,
            "expected_margin_cents": 325000,
            "buyer_capacity_evidence_ref": "capacity:1",
            "verified_price_evidence_ref": (
                f"commercial_evidence:{EVIDENCE_ID}"
            ),
        },
        "commercial_terms_sha256": "a" * 64,
        "decided_by": "founder",
        "decided_at": "2026-10-02T12:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_verified_price_evidence_resolves_buyer_safe_content():
    gateway = Gateway(rows=[price_row()])
    resolver = CanonicalCommercialEvidenceResolver(
        gateway,
        now=lambda: datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    value = resolver.resolve(f"commercial_evidence:{EVIDENCE_ID}")
    assert value["verified"] is True
    assert value["truth_class"] == "VERIFIED"
    assert "$499.00 USD" in value["content"]
    assert "roofing London" in value["content"]
    assert gateway.query_calls[0][0] == "commercial_evidence_registry"


def test_expired_or_internal_price_is_not_buyer_safe():
    expired = Gateway(rows=[price_row(
        valid_until="2026-10-01T00:00:00+00:00"
    )])
    resolver = CanonicalCommercialEvidenceResolver(
        expired,
        now=lambda: datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    assert resolver.resolve(f"commercial_evidence:{EVIDENCE_ID}") is None

    internal = Gateway(rows=[price_row(source_type="internal_actual")])
    resolver = CanonicalCommercialEvidenceResolver(
        internal,
        now=lambda: datetime(2026, 10, 2, tzinfo=timezone.utc),
    )
    assert resolver.resolve(f"commercial_evidence:{EVIDENCE_ID}") is None


def test_approved_terms_strip_internal_cost_and_margin():
    gateway = Gateway(rpc_value=terms_row())
    resolver = CanonicalCommercialTermsResolver(gateway)
    value = resolver.resolve(f"commercial_terms_review:{REVIEW_ID}")
    assert value["verified"] is True
    assert value["truth_class"] == "VERIFIED"
    assert "PREDICTIVE-REVENUE-PILOT" in value["content"]
    assert '"price_cents":500000' in value["content"]
    assert "acquisition_cost_cents" not in value["content"]
    assert "fulfilment_cost_cents" not in value["content"]
    assert "expected_margin_cents" not in value["content"]
    assert gateway.rpc_calls == [
        ("get_commercial_terms_review", {"p_review_id": REVIEW_ID})
    ]


def test_pending_or_unhashed_terms_do_not_resolve():
    pending = Gateway(rpc_value=terms_row(status="pending"))
    assert CanonicalCommercialTermsResolver(pending).resolve(
        f"commercial_terms_review:{REVIEW_ID}"
    ) is None

    bad_hash = Gateway(rpc_value=terms_row(commercial_terms_sha256="bad"))
    assert CanonicalCommercialTermsResolver(bad_hash).resolve(
        f"commercial_terms_review:{REVIEW_ID}"
    ) is None


def test_friendly_demo_terms_ref_is_not_treated_as_canonical():
    gateway = Gateway(rpc_value=terms_row())
    resolver = CanonicalCommercialTermsResolver(gateway)
    assert resolver.resolve("terms:pilot:v1") is None
    assert gateway.rpc_calls == []


OUTCOME_ID = "55555555-5555-4555-8555-555555555555"


def outcome_row(**overrides):
    row = {
        "id": OUTCOME_ID,
        "fulfilment_order_id": "33333333-3333-4333-8333-333333333333",
        "delivery_outcome": "confirmed",
        "conversion_outcome": "won",
        "buyer_satisfaction": 4.8,
        "evidence_kind": "buyer_feedback",
        "evidence_reference": "conversation:buyer-reply:99",
        "recorded_at": "2026-10-02T13:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_verified_commercial_outcome_resolves_without_internal_economics():
    gateway = Gateway(rows=[outcome_row()])
    resolver = CanonicalCommercialOutcomeResolver(gateway)
    value = resolver.resolve(f"canonical:commercial_outcomes:{OUTCOME_ID}")
    assert value["verified"] is True
    assert value["truth_class"] == "VERIFIED"
    assert value["source_kind"] == "commercial_outcome"
    assert '"conversion_outcome":"won"' in value["content"]
    assert '"delivery_outcome":"confirmed"' in value["content"]
    assert '"buyer_satisfaction":4.8' in value["content"]
    assert "revenue" not in value["content"].lower()
    assert "cost" not in value["content"].lower()
    assert "margin" not in value["content"].lower()


def test_unknown_outcome_does_not_become_proof():
    gateway = Gateway(rows=[outcome_row(
        delivery_outcome="unknown",
        conversion_outcome="unknown",
    )])
    resolver = CanonicalCommercialOutcomeResolver(gateway)
    assert resolver.resolve(
        f"canonical:commercial_outcomes:{OUTCOME_ID}"
    ) is None


def test_outcome_requires_provenance_and_recorded_time():
    missing_ref = Gateway(rows=[outcome_row(evidence_reference="")])
    assert CanonicalCommercialOutcomeResolver(missing_ref).resolve(
        f"canonical:commercial_outcomes:{OUTCOME_ID}"
    ) is None

    missing_time = Gateway(rows=[outcome_row(recorded_at=None)])
    assert CanonicalCommercialOutcomeResolver(missing_time).resolve(
        f"canonical:commercial_outcomes:{OUTCOME_ID}"
    ) is None


PRODUCT_ID = "66666666-6666-4666-8666-666666666666"


def product_catalog_row(**overrides):
    row = {
        "product_id": PRODUCT_ID,
        "product_code": "PREDICTIVE-REVENUE-PILOT",
        "product_name": "Predictive Revenue Pilot",
        "product_family": "predictive_revenue",
        "active": True,
        "catalog_state": "VERIFIED",
        "currency": "USD",
        "version_id": "77777777-7777-4777-8777-777777777777",
        "version": 3,
        "version_state": "VERIFIED",
        "billing_model": "flat",
        "price_basis": {
            "state": "VERIFIED",
            "amount_cents": 500000,
            "unit": "flat",
            "currency": "USD",
        },
        "acquisition_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": 100000,
            "unit": "flat",
            "currency": "USD",
        },
        "fulfilment_cost_basis": {
            "state": "VERIFIED",
            "amount_cents": 75000,
            "unit": "flat",
            "currency": "USD",
        },
        "margin_policy": {
            "state": "VERIFIED",
            "minimum_margin_bps": 3000,
        },
        "binding_terms_ready": True,
    }
    row.update(overrides)
    return row


class ProductGateway:
    def __init__(self, catalog=None):
        self.catalog = [dict(x) for x in (catalog or [product_catalog_row()])]
        self.query_calls = []
        self.rpc_calls = []

    def query(self, table, columns, **kwargs):
        self.query_calls.append((table, columns, kwargs))
        if table == "commercial_products":
            return [{
                "id": PRODUCT_ID,
                "product_code": "PREDICTIVE-REVENUE-PILOT",
            }]
        return []

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, params))
        if name == "get_commercial_product_catalog":
            return list(self.catalog)
        return None


def test_verified_product_code_resolves_public_catalog_only():
    gateway = ProductGateway()
    resolver = CanonicalCommercialProductResolver(gateway)
    value = resolver.resolve(
        "commercial_product_code:PREDICTIVE-REVENUE-PILOT"
    )
    assert value["verified"] is True
    assert value["source_kind"] == "commercial_product_catalog"
    assert "Predictive Revenue Pilot" in value["content"]
    assert '"amount_cents":500000' in value["content"]
    assert "acquisition_cost_basis" not in value["content"]
    assert "fulfilment_cost_basis" not in value["content"]
    assert "margin_policy" not in value["content"]


def test_product_uuid_resolves_to_code_then_public_catalog():
    gateway = ProductGateway()
    resolver = CanonicalCommercialProductResolver(gateway)
    value = resolver.resolve(f"commercial_product:{PRODUCT_ID}")
    assert value["verified"] is True
    assert gateway.query_calls[0][0] == "commercial_products"
    assert gateway.rpc_calls[0] == (
        "get_commercial_product_catalog",
        {
            "p_product_code": "PREDICTIVE-REVENUE-PILOT",
            "p_limit": 1,
        },
    )


def test_unverified_or_not_binding_ready_product_does_not_resolve():
    gateway = ProductGateway([
        product_catalog_row(binding_terms_ready=False)
    ])
    resolver = CanonicalCommercialProductResolver(gateway)
    assert resolver.resolve(
        "commercial_product_code:PREDICTIVE-REVENUE-PILOT"
    ) is None
