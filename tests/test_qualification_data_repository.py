import pytest

from empire_os.data_query import ConflictAction, FilterOperator
from empire_os.data_values import JsonValue, unwrap_data_value
from empire_os.qualification_data_repository import QualificationDataRepository


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
        self.query_results = []
        self.queries = []
        self.upserts = []
        self.inserts = []
        self.updates = []
        self._query_index = 0

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
        if self._query_index >= len(self.query_results):
            return []
        rows = self.query_results[self._query_index]
        self._query_index += 1
        return rows

    def upsert(self, table, row, *, conflict_columns, action, return_repr=True):
        self.upserts.append((table, dict(row), tuple(conflict_columns), action, return_repr))
        return [unwrap_data_value(dict(row))]

    def insert_ignore_conflicts(
        self,
        table,
        row,
        *,
        conflict_columns=(),
        return_repr=False,
    ):
        self.inserts.append(
            (table, dict(row), tuple(conflict_columns), return_repr)
        )
        return []

    def update(self, table, match, values):
        self.updates.append((table, dict(match), dict(values)))
        return [{**match, **values}]

    def snapshot(self):
        return Snapshot()


def _prospect(prospect_id):
    return {
        "id": prospect_id,
        "created_at": "2026-09-27T00:00:00+00:00",
        "business_name": "Example",
    }


def test_pending_prospects_preserve_order_and_exclude_existing_scores():
    gateway = FakeGateway()
    gateway.queue_query([_prospect("p3"), _prospect("p2"), _prospect("p1")])
    gateway.queue_query([{"prospect_id": "p2"}])
    repository = QualificationDataRepository(gateway)

    rows = repository.fetch_pending_prospects(
        limit=2,
        scoring_engine="engine",
        scoring_version="v2",
    )

    assert [row["id"] for row in rows] == ["p3", "p1"]
    filters = gateway.queries[1]["filters"]
    assert any(
        item.column == "prospect_id"
        and item.operator is FilterOperator.IN
        and item.value == ("p3", "p2", "p1")
        for item in filters
    )


def test_unlinked_candidates_skip_previously_attempted_identity_and_keep_order():
    gateway = FakeGateway()
    gateway.queue_query([
        {
            "prospect_id": "attempted",
            "scored_at": "3",
            "result_payload": {"identity_resolution": {"attempted": True}},
        },
        {"prospect_id": "p2", "scored_at": "2", "result_payload": {}},
        {"prospect_id": "p1", "scored_at": "1", "result_payload": {}},
    ])
    gateway.queue_query([_prospect("p1"), _prospect("p2")])
    repository = QualificationDataRepository(gateway)

    rows = repository.fetch_unlinked_allocatable_prospects(
        limit=2,
        scoring_engine="engine",
        scoring_version="v2",
    )

    assert [row["id"] for row in rows] == ["p2", "p1"]
    filters = gateway.queries[0]["filters"]
    assert any(
        item.column == "entity_id"
        and item.operator is FilterOperator.IS_NULL
        for item in filters
    )


def test_active_identity_link_fails_on_multiple_active_rows():
    gateway = FakeGateway()
    gateway.queue_query([
        {"prospect_id": "p1", "entity_id": "e1"},
        {"prospect_id": "p1", "entity_id": "e2"},
    ])
    repository = QualificationDataRepository(gateway)

    with pytest.raises(RuntimeError, match="multiple active"):
        repository.fetch_active_identity_link("p1")


def test_identity_writes_are_conflict_ignored_and_verified_externally():
    gateway = FakeGateway()
    repository = QualificationDataRepository(gateway)

    repository.insert_identity_entity({"id": "e1"})
    repository.insert_identity_link({"prospect_id": "p1", "entity_id": "e1"})

    assert gateway.inserts == [
        ("business_entities", {"id": "e1"}, ("id",), False),
        (
            "prospect_entity_links",
            {"prospect_id": "p1", "entity_id": "e1"},
            ("prospect_id",),
            False,
        ),
    ]


def test_website_promotion_writes_then_verifies():
    gateway = FakeGateway()
    gateway.queue_query([{"id": "p1", "website": "https://example.test"}])
    repository = QualificationDataRepository(gateway)

    result = repository.promote_verified_website(
        "p1",
        "https://example.test",
    )

    assert result == "https://example.test"
    assert gateway.updates == [
        ("prospects", {"id": "p1"}, {"website": "https://example.test"}),
    ]


def test_qualification_uses_composite_merge_upsert():
    gateway = FakeGateway()
    repository = QualificationDataRepository(gateway)
    payload = {
        "prospect_id": "p1",
        "scoring_engine": "engine",
        "scoring_version": "v2",
        "status": "scored",
        "observed_dimensions": ["market_fit"],
        "unknown_dimensions": ["engagement_potential"],
    }

    result = repository.upsert_qualification(payload)

    assert result == payload
    written = gateway.upserts[0][1]
    assert written["observed_dimensions"] == JsonValue(["market_fit"])
    assert written["unknown_dimensions"] == JsonValue(["engagement_potential"])
    assert gateway.upserts == [(
        "prospect_qualifications",
        {
            **payload,
            "observed_dimensions": JsonValue(["market_fit"]),
            "unknown_dimensions": JsonValue(["engagement_potential"]),
        },
        ("prospect_id", "scoring_engine", "scoring_version"),
        ConflictAction.MERGE,
        True,
    )]


def test_repository_snapshot_has_no_dual_write_or_fallback():
    snapshot = QualificationDataRepository(FakeGateway()).snapshot()
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False


def test_exact_prospect_fetch_is_bounded_and_requires_single_row():
    gateway = FakeGateway()
    gateway.queue_query([_prospect("p1")])
    repository = QualificationDataRepository(gateway)

    row = repository.fetch_prospect("p1")

    assert row["id"] == "p1"
    query = gateway.queries[0]
    assert query["table"] == "prospects"
    assert query["limit"] == 2
    assert any(
        item.column == "id"
        and item.operator is FilterOperator.EQ
        and item.value == "p1"
        for item in query["filters"]
    )

    gateway = FakeGateway()
    gateway.queue_query([])
    with pytest.raises(RuntimeError, match="not found or ambiguous"):
        QualificationDataRepository(gateway).fetch_prospect("missing")


def test_low_confidence_recovery_candidates_are_bounded_and_sorted_by_confidence():
    gateway = FakeGateway()
    gateway.queue_query([
        {"id":"q-high","prospect_id":"p-high","status":"insufficient_evidence","evidence_confidence":0.49},
        {"id":"q-floor","prospect_id":"p-floor","status":"insufficient_evidence","evidence_confidence":0.50},
        {"id":"q-low","prospect_id":"p-low","status":"insufficient_evidence","evidence_confidence":0.20},
    ])
    repository = QualificationDataRepository(gateway)
    rows = repository.fetch_low_confidence_recovery_candidates(
        limit=2,
        scoring_engine="empire_os.lead_scoring",
        scoring_version="v2",
        confidence_floor=0.50,
    )
    assert [row["prospect_id"] for row in rows] == ["p-high", "p-low"]
    query = gateway.queries[0]
    assert query["table"] == "prospect_qualifications"
    assert query["limit"] == 10
    assert any(item.column == "status" and item.value == "insufficient_evidence" for item in query["filters"])
    assert query["order"][0].column == "evidence_confidence"
    assert query["order"][0].descending is True


def test_recovery_metadata_updates_only_existing_qualification_payload():
    gateway = FakeGateway()
    repository = QualificationDataRepository(gateway)
    payload = {"evidence_recovery": {"recovery_attempted": True}}
    result = repository.record_recovery_metadata(
        "q1", payload, updated_at="2026-10-02T10:00:00+00:00"
    )
    assert result["id"] == "q1"
    table, match, values = gateway.updates[0]
    assert table == "prospect_qualifications"
    assert match == {"id":"q1"}
    assert values["result_payload"] == JsonValue(payload)
