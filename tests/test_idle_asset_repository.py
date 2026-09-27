from empire_os.data_query import FilterOperator
from empire_os.idle_asset_repository import IdleAssetRepository


class FakeGateway:
    def __init__(self):
        self.calls = []

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
        self.calls.append((
            "query",
            table,
            columns,
            tuple(filters),
            limit,
        ))
        if table == "empire_tasks":
            return [
                {"id": "1", "payload": {"url": "https://example.test/a"}},
                {"id": "2", "payload": {"url": "https://example.test/b"}},
            ]
        if table == "idle_asset_enriched":
            return [{
                "compound_id": "asset-1",
                "business_name": "Example Logistics",
                "industry": "logistics",
                "lead_gen_score": 0.8,
            }]
        raise AssertionError(table)

    def insert(self, table, row, *, return_repr=True):
        self.calls.append(("insert", table, dict(row), return_repr))
        return []


def test_pending_review_dedup_uses_canonical_query():
    gateway = FakeGateway()
    repository = IdleAssetRepository(gateway)

    assert repository.pending_review_exists("https://example.test/b") is True
    call = gateway.calls[0]
    assert call[0] == "query"
    assert call[1] == "empire_tasks"
    assert [item.column for item in call[3]] == ["task_type", "status"]
    assert all(item.operator is FilterOperator.EQ for item in call[3])


def test_queue_review_uses_canonical_insert_without_representation():
    gateway = FakeGateway()
    repository = IdleAssetRepository(gateway)

    repository.queue_review({
        "task_type": "idle_asset_review",
        "status": "pending",
        "payload": {"url": "https://example.test/a"},
    })

    assert gateway.calls == [(
        "insert",
        "empire_tasks",
        {
            "task_type": "idle_asset_review",
            "status": "pending",
            "payload": {"url": "https://example.test/a"},
        },
        False,
    )]


def test_enriched_candidates_are_bounded_and_vendor_neutral():
    gateway = FakeGateway()
    repository = IdleAssetRepository(gateway)

    rows = repository.enriched_candidates(limit=500)

    assert rows[0]["compound_id"] == "asset-1"
    call = gateway.calls[0]
    assert call[1] == "idle_asset_enriched"
    assert call[4] == 100
    assert call[3][0].column == "lead_gen_score"
    assert call[3][0].operator is FilterOperator.GTE
