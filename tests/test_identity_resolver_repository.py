import inspect

import empire_os.identity_resolver as resolver
from empire_os.identity_resolver_repository import IdentityResolverDataRepository


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
        self.calls = []

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.calls.append((table, limit, offset))
        if offset == 0:
            return [{"id": "1"}, {"id": "2"}]
        return []

    def snapshot(self):
        return Snapshot()


def test_identity_repository_paginates_canonical_prospects():
    gateway = FakeGateway()
    repository = IdentityResolverDataRepository(gateway)

    rows = repository.fetch_prospects(batch_size=2)

    assert rows == [{"id": "1"}, {"id": "2"}]
    assert gateway.calls == [
        ("prospects", 2, 0),
        ("prospects", 2, 2),
    ]


def test_identity_repository_is_read_only():
    snapshot = IdentityResolverDataRepository(FakeGateway()).snapshot()

    assert snapshot["repository_authority"] == "read_only"
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False


def test_identity_resolver_contains_no_direct_vendor_transport():
    source = inspect.getsource(resolver)

    assert "SUPABASE_URL" not in source
    assert "SUPABASE_SERVICE_KEY" not in source
    assert "/rest/v1/" not in source
    assert "urllib.request" not in source
    assert "supabase_url" not in source


def test_fetch_prospects_uses_supplied_repository():
    class Repo:
        def fetch_prospects(self):
            return [{"id": "p1"}]

    assert resolver.fetch_prospects(Repo()) == [{"id": "p1"}]
