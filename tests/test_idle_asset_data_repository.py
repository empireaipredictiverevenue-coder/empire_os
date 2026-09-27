import inspect

import empire_os.agents.idle_asset_sniper_agent as sniper
from empire_os.data_query import FilterOperator
from empire_os.idle_asset_data_repository import IdleAssetDataRepository


class Snapshot:
    def as_dict(self):
        return {
            "primary_backend": "supabase_legacy",
            "configured": True,
            "dual_write_enabled": False,
            "write_fallback_enabled": False,
        }


class FakeGateway:
    configured = True

    def __init__(self):
        self.queries = []
        self.inserts = []
        self.results = []

    def queue(self, rows):
        self.results.append(rows)

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append((table, columns, tuple(filters), limit, offset))
        return self.results.pop(0) if self.results else []

    def insert(self, table, row, *, return_repr=True):
        self.inserts.append((table, dict(row), return_repr))
        return []

    def snapshot(self):
        return Snapshot()


def test_repository_reads_pending_review_urls_semantically():
    gateway = FakeGateway()
    gateway.queue([
        {"payload": {"url": "https://example/a"}},
        {"payload": {"url": "https://example/b"}},
    ])
    repo = IdleAssetDataRepository(gateway)

    assert repo.pending_review_urls() == {
        "https://example/a",
        "https://example/b",
    }

    table, _, filters, limit, _ = gateway.queries[0]
    assert table == "empire_tasks"
    assert limit == 5000
    assert any(
        item.column == "task_type"
        and item.operator is FilterOperator.EQ
        and item.value == "idle_asset_review"
        for item in filters
    )


def test_enriched_candidates_use_score_filter():
    gateway = FakeGateway()
    gateway.queue([{"compound_id": "c1"}])
    repo = IdleAssetDataRepository(gateway)

    assert repo.enriched_candidates(minimum_score=0.6, limit=20) == [
        {"compound_id": "c1"}
    ]

    _, _, filters, limit, _ = gateway.queries[0]
    assert limit == 20
    assert any(
        item.column == "lead_gen_score"
        and item.operator is FilterOperator.GTE
        and item.value == 0.6
        for item in filters
    )


def test_review_queue_is_bounded_and_never_outbound():
    gateway = FakeGateway()
    repo = IdleAssetDataRepository(gateway)

    repo.queue_review({
        "task_type": "idle_asset_review",
        "status": "pending",
        "payload": {"url": "https://example/a"},
    })

    assert gateway.inserts[0][0] == "empire_tasks"
    snapshot = repo.snapshot()
    assert snapshot["repository_authority"] == "idle_asset_review_only"
    assert snapshot["outreach_authority"] is False
    assert snapshot["dual_write_enabled"] is False


def test_agent_has_no_direct_vendor_database_transport():
    source = inspect.getsource(sniper)

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "_sb_insert" not in source
    # urllib remains intentionally for public RSS feeds.
    assert "urllib.request" in source


def test_queue_review_uses_supplied_repository(monkeypatch):
    sniper._seen_urls.clear()
    seen = []

    class Repo:
        def pending_review_urls(self):
            return set()

        def queue_review(self, row):
            seen.append(dict(row))

    result = sniper._queue_review(
        {"url": "https://example/a", "title": "Vacant warehouse"},
        "logistics_waste",
        0.75,
        Repo(),
    )

    assert result["status"] == "review_queued"
    assert seen[0]["task_type"] == "idle_asset_review"
    assert seen[0]["payload"]["url"] == "https://example/a"
