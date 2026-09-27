import inspect

import empire_os.gtm_standing_bridge as bridge
from empire_os.gtm_standing_bridge_repository import (
    CanonicalStandingBridgeRepository,
)


class FakeGateway:
    def __init__(self):
        self.queries = []
        self.rpcs = []

    def query(
        self,
        table,
        columns="*",
        *,
        filters=(),
        order=(),
        limit=1000,
        offset=0,
    ):
        self.queries.append({
            "table": table,
            "columns": columns,
            "filters": filters,
            "order": order,
            "limit": limit,
            "offset": offset,
        })
        return [{
            "id": "review-1",
            "status": "pending",
            "offer_key": "managed_service",
        }]

    def rpc(self, name, params=None):
        self.rpcs.append((name, dict(params or {})))
        if name == "auto_review_buyer_candidate":
            return {"status": "approved"}
        if name == "list_buyer_reviews_for_outbound":
            return [{"id": "review-1"}]
        if name == "propose_reviewed_outbound_intent":
            return {"intent_id": "intent-1"}
        raise AssertionError(name)


def test_standing_bridge_repository_uses_gateway_semantics():
    gateway = FakeGateway()
    repository = CanonicalStandingBridgeRepository(gateway)

    pending = repository.pending_reviews(limit=500)
    approval = repository.auto_review("review-1", daily_cap=500)
    ready = repository.approved_for_outbound(limit=500)
    proposal = repository.propose_outbound_intent({
        "p_review_id": "review-1",
    })

    assert pending[0]["id"] == "review-1"
    assert gateway.queries[0]["table"] == "buyer_candidate_reviews"
    assert gateway.queries[0]["limit"] == 50
    assert approval["status"] == "approved"
    assert ready[0]["id"] == "review-1"
    assert proposal["intent_id"] == "intent-1"
    assert gateway.rpcs[0][1]["p_daily_cap"] == 50
    assert gateway.rpcs[1][1]["p_limit"] == 50


def test_standing_bridge_business_module_has_no_vendor_transport_dependency():
    source = inspect.getsource(bridge)

    assert "qualification_worker_v2" not in source
    assert "/rest/v1/" not in source
    assert "SUPABASE_" not in source
    assert "urllib" not in source
