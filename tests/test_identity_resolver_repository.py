from empire_os.identity_resolver_repository import IdentityResolverRepository


class FakeGateway:
    backend = type("Backend", (), {"value": "test_backend"})()

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
        self.calls.append((table, columns, limit, offset))
        if offset == 0:
            return [{"id": "1"}, {"id": "2"}]
        return []


def test_identity_repository_pages_through_gateway():
    gateway = FakeGateway()
    repository = IdentityResolverRepository(gateway)

    rows = repository.fetch_prospects(batch_size=2, max_rows=10)

    assert [row["id"] for row in rows] == ["1", "2"]
    assert gateway.calls[0][0] == "prospects"
    assert gateway.calls[0][2:] == (2, 0)
    assert gateway.calls[1][2:] == (2, 2)
    assert repository.backend_name == "test_backend"
