import pytest

from empire_os.data_cloud_contract import DataBackend
from empire_os.commercial_event_repository import CommercialEventRepository


class Snapshot:
    def as_dict(self):
        return {
            "primary_backend": DataBackend.SUPABASE_LEGACY.value,
            "configured": True,
            "dual_write_enabled": False,
            "write_fallback_enabled": False,
        }


class FakeGateway:
    def __init__(self):
        self.existing = []
        self.insert_rows = [{"id": "e1"}]
        self.insert_error = None
        self.queries = []
        self.inserts = []

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append((table, columns, tuple(filters), limit))
        return list(self.existing)

    def insert(self, table, row, *, return_repr=True):
        self.inserts.append((table, dict(row), return_repr))
        if self.insert_error is not None:
            raise self.insert_error
        return list(self.insert_rows)

    def snapshot(self):
        return Snapshot()


def _event():
    return {
        "event_type": "prospect_qualified_v2",
        "actor": "qualification_worker_v2",
        "idempotency_key": "prospect:p1:qualified:v2",
        "payload": {"score": 90},
    }


def test_append_inserts_after_exact_idempotency_check():
    gateway = FakeGateway()
    repository = CommercialEventRepository(gateway)

    inserted = repository.append_idempotent(_event())

    assert inserted is True
    assert gateway.inserts == [
        ("commercial_events", _event(), True),
    ]
    assert len(gateway.queries) == 1


def test_existing_idempotency_key_is_successful_noop():
    gateway = FakeGateway()
    gateway.existing = [{"id": "e1", "idempotency_key": _event()["idempotency_key"]}]
    repository = CommercialEventRepository(gateway)

    assert repository.append_idempotent(_event()) is False
    assert gateway.inserts == []


def test_insert_race_is_only_idempotent_when_exact_key_now_exists():
    gateway = FakeGateway()
    repository = CommercialEventRepository(gateway)
    gateway.insert_error = RuntimeError("unique violation")

    calls = {"count": 0}

    def query(table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        return [{"id": "e1", "idempotency_key": _event()["idempotency_key"]}]

    gateway.query = query

    assert repository.append_idempotent(_event()) is False
    assert calls["count"] == 2


def test_unrelated_insert_failure_is_not_swallowed():
    gateway = FakeGateway()
    gateway.insert_error = RuntimeError("check constraint failed")
    repository = CommercialEventRepository(gateway)

    with pytest.raises(RuntimeError, match="check constraint"):
        repository.append_idempotent(_event())


@pytest.mark.parametrize("field", ["event_type", "actor", "idempotency_key"])
def test_required_event_identity_fields_fail_closed(field):
    event = _event()
    event[field] = ""
    repository = CommercialEventRepository(FakeGateway())

    with pytest.raises(ValueError, match=field):
        repository.append_idempotent(event)


def test_repository_never_enables_dual_write_or_fallback():
    snapshot = CommercialEventRepository(FakeGateway()).snapshot()
    assert snapshot["append_only"] is True
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False
