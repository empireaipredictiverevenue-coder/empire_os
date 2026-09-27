from empire_os.data_cloud_contract import DataBackend
from empire_os.gtm_data_repository import GTMDataRepository


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
        self.calls = []

    def select(self, table, columns="*", filters=None, order=None, limit=1000, offset=0):
        self.calls.append(("select", table, limit, offset))
        if offset == 0:
            return [{"id": "1"}, {"id": "2"}]
        return []

    def count(self, table, filters=None):
        self.calls.append(("count", table))
        return 42

    def snapshot(self):
        return Snapshot()


def test_repository_paginates_through_gateway():
    gateway = FakeGateway()
    repo = GTMDataRepository(gateway)

    rows = repo.fetch_all("prospects", "id", batch_size=2)

    assert rows == [{"id": "1"}, {"id": "2"}]
    assert gateway.calls[:2] == [
        ("select", "prospects", 2, 0),
        ("select", "prospects", 2, 2),
    ]


def test_repository_exact_count_and_snapshot_are_read_only():
    gateway = FakeGateway()
    repo = GTMDataRepository(gateway)

    assert repo.count("prospects") == 42
    snapshot = repo.snapshot()

    assert snapshot["backend"] == "supabase_legacy"
    assert snapshot["repository_authority"] == "read_only"
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False
