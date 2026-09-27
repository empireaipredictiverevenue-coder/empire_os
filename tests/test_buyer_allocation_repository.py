import inspect

import empire_os.buyer_allocation as allocation
from empire_os.buyer_allocation_repository import BuyerAllocationDataRepository
from empire_os.data_query import FilterOperator


class Snapshot:
    def as_dict(self):
        return {
            "primary_backend": "supabase_legacy",
            "configured": True,
            "dual_write_enabled": False,
            "write_fallback_enabled": False,
        }


class FakeGateway:
    def __init__(self):
        self.queries = []
        self.rpc_calls = []
        self.query_results = []

    def queue_query(self, rows):
        self.query_results.append(rows)

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append({
            "table": table,
            "columns": columns,
            "filters": tuple(filters),
            "order": tuple(order),
            "limit": limit,
            "offset": offset,
        })
        return self.query_results.pop(0) if self.query_results else []

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, dict(params or {})))
        return {"decision": "allocated"}

    def snapshot(self):
        return Snapshot()


def test_buyer_allocation_runtime_contains_no_rest_transport():
    source = inspect.getsource(allocation)
    assert "/rest/v1/" not in source
    assert "urllib." not in source
    assert "SUPABASE_" not in source


def test_latest_qualification_uses_neutral_filters():
    gateway = FakeGateway()
    gateway.queue_query([{"prospect_id": "p1", "scoring_version": "v2"}])
    repository = BuyerAllocationDataRepository(gateway)

    rows = repository.latest_qualifications("p1")

    assert rows[0]["scoring_version"] == "v2"
    query = gateway.queries[0]
    assert query["table"] == "prospect_qualifications"
    assert query["limit"] == 2
    filters = query["filters"]
    assert any(
        item.column == "prospect_id"
        and item.operator is FilterOperator.EQ
        and item.value == "p1"
        for item in filters
    )
    assert any(
        item.column == "scoring_version"
        and item.operator is FilterOperator.IN
        and item.value == ("v2", "v1")
        for item in filters
    )


def test_active_identity_link_query_is_bounded():
    gateway = FakeGateway()
    gateway.queue_query([])
    repository = BuyerAllocationDataRepository(gateway)

    assert repository.active_identity_links("p1") == []

    query = gateway.queries[0]
    assert query["table"] == "prospect_entity_links"
    assert query["limit"] == 2
    assert any(
        item.column == "active"
        and item.operator is FilterOperator.EQ
        and item.value is True
        for item in query["filters"]
    )


def test_buyer_page_preserves_pagination():
    gateway = FakeGateway()
    gateway.queue_query([{"id": "b1"}])
    repository = BuyerAllocationDataRepository(gateway)

    assert repository.buyer_page(page_size=50, offset=100) == [{"id": "b1"}]

    query = gateway.queries[0]
    assert query["table"] == "buyers"
    assert query["limit"] == 50
    assert query["offset"] == 100


def test_atomic_allocation_stays_explicit_rpc_boundary():
    gateway = FakeGateway()
    repository = BuyerAllocationDataRepository(gateway)

    result = repository.allocate_atomic({"p_prospect_id": "p1"})

    assert result == {"decision": "allocated"}
    assert gateway.rpc_calls == [
        ("allocate_prospect_atomic", {"p_prospect_id": "p1"})
    ]


def test_repository_snapshot_preserves_single_primary_semantics():
    gateway = FakeGateway()
    snapshot = BuyerAllocationDataRepository(gateway).snapshot()

    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False
    assert snapshot["atomic_allocator"] == "allocate_prospect_atomic"
