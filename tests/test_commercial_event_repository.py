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
    def __init__(self, rows=None):
        self.rows = [] if rows is None else rows
        self.calls = []

    def insert_ignore_conflicts(self, table, row, *, return_repr=False):
        self.calls.append((table, dict(row), return_repr))
        return list(self.rows)

    def snapshot(self):
        return Snapshot()


def _event():
    return {
        "event_type": "prospect_qualified_v2",
        "actor": "qualification_worker_v2",
        "idempotency_key": "prospect:p1:qualified:v2",
        "payload": {"score": 90},
    }


def test_append_uses_untargeted_conflict_ignore():
    gateway = FakeGateway(rows=[{"id": "e1"}])
    repository = CommercialEventRepository(gateway)

    inserted = repository.append_idempotent(_event())

    assert inserted is True
    assert gateway.calls == [
        ("commercial_events", _event(), True),
    ]


def test_existing_idempotency_key_is_successful_noop():
    repository = CommercialEventRepository(FakeGateway(rows=[]))
    assert repository.append_idempotent(_event()) is False


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
