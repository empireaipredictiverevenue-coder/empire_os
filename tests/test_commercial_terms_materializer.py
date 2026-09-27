from urllib.parse import parse_qs, urlparse

from empire_os.commercial_terms_materializer import (
    run_commercial_terms_materializer,
)


class FakeRequest:
    def __init__(
        self,
        *,
        include_price=True,
        catalog_ready=True,
        product_id="product-1",
        order_buyer_id="buyer-1",
    ):
        self.include_price = include_price
        self.catalog_ready = catalog_ready
        self.product_id = product_id
        self.order_buyer_id = order_buyer_id
        self.calls = []

    def __call__(self, method, path, payload=None, **kwargs):
        self.calls.append((method, path, payload))
        if method == "GET":
            parsed = urlparse(path)
            params = parse_qs(parsed.query)
            if parsed.path == "/rest/v1/closer_cases":
                return [{
                    "id": "case-1",
                    "state": "engaged",
                    "buyer_id": "buyer-1",
                    "prospect_id": "prospect-1",
                    "fulfilment_order_id": "order-1",
                    "updated_at": "2026-09-20T19:00:00+00:00",
                }]
            if parsed.path == "/rest/v1/fulfilment_orders":
                return [{
                    "id": "order-1",
                    "state": "qualified",
                    "buyer_id": self.order_buyer_id,
                    "prospect_id": "prospect-1",
                    "product_id": self.product_id,
                }]
            if parsed.path == "/rest/v1/buyer_capacity_intakes":
                return [{
                    "id": "capacity-1",
                    "state": "complete",
                    "territory": "Austin",
                    "daily_cap": 10,
                    "delivery_route": "webhook",
                    "delivery_reference": "https://acme.test/leads",
                }]
            if parsed.path == "/rest/v1/commercial_products":
                if not self.product_id:
                    return []
                return [{
                    "id": self.product_id,
                    "product_code": "managed_service",
                    "active": True,
                }]
            raise AssertionError((parsed.path, params))

        if path == "/rest/v1/rpc/get_commercial_product_readiness":
            assert payload["p_product_code"] == "managed_service"
            if self.catalog_ready:
                return {
                    "exists": True,
                    "binding_terms_ready": True,
                    "blockers": [],
                }
            return {
                "exists": True,
                "binding_terms_ready": False,
                "blockers": ["acquisition_cost_basis_unverified"],
            }

        if path == "/rest/v1/rpc/get_verified_terms_evidence":
            return {
                "price": (
                    {
                        "evidence_id": "price-1",
                        "amount_cents": 12000,
                        "unit": "per_lead",
                    }
                    if self.include_price
                    else None
                ),
                "acquisition_cost": {
                    "evidence_id": "acq-1",
                    "amount_cents": 2500,
                    "unit": "per_lead",
                },
                "fulfilment_cost": {
                    "evidence_id": "fulfil-1",
                    "amount_cents": 1500,
                    "unit": "per_lead",
                },
            }

        if path == "/rest/v1/rpc/propose_commercial_terms":
            assert payload["p_price_cents"] == 12000
            assert payload["p_acquisition_cost_cents"] == 2500
            assert payload["p_fulfilment_cost_cents"] == 1500
            assert payload["p_terms"]["product_id"] == "product-1"
            assert payload["p_terms"]["product_code"] == "managed_service"
            assert payload["p_terms"]["settlement_asset"] == "USDT"
            assert payload["p_terms"]["settlement_chain"] == "BSC"
            assert payload["p_terms"]["binding"] is False
            return {
                "decision": "proposed",
                "review_id": "review-1",
                "status": "pending",
                "actual_revenue": False,
            }

        raise AssertionError((method, path, payload))


def test_materializer_proposes_only_when_all_evidence_is_verified():
    request = FakeRequest()
    result = run_commercial_terms_materializer(request)

    assert result.scanned == 1
    assert result.ready == 1
    assert result.proposed == 1
    assert result.blocked == 0
    assert result.errors == ()
    assert any(
        path == "/rest/v1/rpc/propose_commercial_terms"
        for method, path, _ in request.calls
        if method == "POST"
    )


def test_materializer_blocks_when_verified_price_is_missing():
    request = FakeRequest(include_price=False)
    result = run_commercial_terms_materializer(request)

    assert result.scanned == 1
    assert result.ready == 0
    assert result.proposed == 0
    assert result.blocked == 1
    assert dict(result.blocker_counts)["verified_price_missing"] == 1
    assert not any(
        path == "/rest/v1/rpc/propose_commercial_terms"
        for method, path, _ in request.calls
        if method == "POST"
    )


def test_materializer_blocks_when_catalog_economics_are_unverified():
    request = FakeRequest(catalog_ready=False)
    result = run_commercial_terms_materializer(request)

    assert result.scanned == 1
    assert result.ready == 0
    assert result.proposed == 0
    assert result.blocked == 1
    assert (
        dict(result.blocker_counts)[
            "catalog_acquisition_cost_basis_unverified"
        ]
        == 1
    )
    assert not any(
        path == "/rest/v1/rpc/get_verified_terms_evidence"
        for method, path, _ in request.calls
        if method == "POST"
    )
    assert not any(
        path == "/rest/v1/rpc/propose_commercial_terms"
        for method, path, _ in request.calls
        if method == "POST"
    )



def test_materializer_blocks_when_order_has_no_product_binding():
    request = FakeRequest(product_id=None)
    result = run_commercial_terms_materializer(request)

    assert result.ready == 0
    assert result.proposed == 0
    assert result.blocked == 1
    assert dict(result.blocker_counts)["fulfilment_order_product_missing"] == 1
    assert not any(
        path == "/rest/v1/rpc/get_commercial_product_readiness"
        for method, path, _ in request.calls
        if method == "POST"
    )


def test_materializer_blocks_cross_buyer_order_binding():
    request = FakeRequest(order_buyer_id="different-buyer")
    result = run_commercial_terms_materializer(request)

    assert result.ready == 0
    assert result.proposed == 0
    assert result.blocked == 1
    assert dict(result.blocker_counts)["fulfilment_order_binding_mismatch"] == 1
