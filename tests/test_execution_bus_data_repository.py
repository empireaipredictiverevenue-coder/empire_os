import pytest

from empire_os.data_query import FilterOperator
from empire_os.execution_bus_data_repository import ExecutionBusDataRepository


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
        self.inserts = []
        self.insert_error = None
        self.rpc_calls = []

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

    def insert(self, table, row, *, return_repr=True):
        self.inserts.append((table, dict(row), return_repr))
        if self.insert_error is not None:
            raise self.insert_error
        return [{**row, "id": row.get("id") or "job-1"}]

    def rpc(self, name, params=None):
        self.rpc_calls.append((name, dict(params or {})))
        return {"ok": True}

    def snapshot(self):
        return Snapshot()


def test_qualification_candidates_use_neutral_query_semantics():
    gateway = FakeGateway()
    gateway.queue_query([{"id": "p1"}])
    repository = ExecutionBusDataRepository(gateway)

    rows = repository.qualification_candidates(
        aliases=("roofing", "roofer"),
        metro="austin",
        limit=5,
    )

    assert rows == [{"id": "p1"}]
    query = gateway.queries[0]
    assert query["table"] == "prospects"
    assert query["limit"] == 5
    assert any(
        item.column == "niche"
        and item.operator is FilterOperator.IN
        and item.value == ("roofing", "roofer")
        for item in query["filters"]
    )
    assert any(
        item.column == "metro"
        and item.operator is FilterOperator.ILIKE
        and item.value == "austin"
        for item in query["filters"]
    )
    assert any(
        item.column == "status"
        and item.operator is FilterOperator.NE
        and item.value == "archived"
        for item in query["filters"]
    )


def test_active_fulfilment_ids_exclude_terminal_states():
    gateway = FakeGateway()
    gateway.queue_query([{"prospect_id": "p2"}])
    repository = ExecutionBusDataRepository(gateway)

    result = repository.active_fulfilment_prospect_ids(("p1", "p2"))

    assert result == {"p2"}
    filters = gateway.queries[0]["filters"]
    assert any(
        item.column == "state"
        and item.operator is FilterOperator.NOT_IN
        and item.value == ("rejected", "cancelled")
        for item in filters
    )


def test_ensure_gtm_job_returns_existing_without_insert():
    gateway = FakeGateway()
    gateway.queue_query([{"id": "job-existing"}])
    repository = ExecutionBusDataRepository(gateway)

    row, created = repository.ensure_gtm_job(
        {"idempotency_key": "qualification:p1:v1"}
    )

    assert row == {"id": "job-existing"}
    assert created is False
    assert gateway.inserts == []


def test_ensure_gtm_job_handles_insert_race_by_exact_key_recheck():
    gateway = FakeGateway()
    gateway.queue_query([])
    gateway.queue_query([{"id": "job-existing"}])
    gateway.insert_error = RuntimeError("unique violation")
    repository = ExecutionBusDataRepository(gateway)

    row, created = repository.ensure_gtm_job(
        {"idempotency_key": "qualification:p1:v1"}
    )

    assert row == {"id": "job-existing"}
    assert created is False
    assert len(gateway.queries) == 2


def test_ensure_gtm_job_does_not_swallow_unrelated_failure():
    gateway = FakeGateway()
    gateway.queue_query([])
    gateway.queue_query([])
    gateway.insert_error = RuntimeError("foreign key violation")
    repository = ExecutionBusDataRepository(gateway)

    with pytest.raises(RuntimeError, match="foreign key violation"):
        repository.ensure_gtm_job(
            {"idempotency_key": "qualification:p1:v1"}
        )


def test_ensure_gtm_job_requires_idempotency_key():
    repository = ExecutionBusDataRepository(FakeGateway())

    with pytest.raises(ValueError, match="idempotency_key"):
        repository.ensure_gtm_job({"job_type": "x"})


def test_canonical_prospect_ingest_stays_explicit_rpc_boundary():
    gateway = FakeGateway()
    repository = ExecutionBusDataRepository(gateway)

    repository.ingest_prospect_atomic(
        prospect={"id": "p1"},
        evidence={"source": "public_record"},
        ingest_key="ingest-1",
        identity_keys=["phone:+1"],
    )

    assert gateway.rpc_calls == [(
        "ingest_prospect_atomic",
        {
            "p_prospect": {"id": "p1"},
            "p_evidence": {"source": "public_record"},
            "p_ingest_key": "ingest-1",
            "p_identity_keys": ["phone:+1"],
        },
    )]


def test_repository_snapshot_preserves_single_primary_semantics():
    snapshot = ExecutionBusDataRepository(FakeGateway()).snapshot()

    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False
    assert snapshot["repository_authority"] == "execution_bus_bounded"
