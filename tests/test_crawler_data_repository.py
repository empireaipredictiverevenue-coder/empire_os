from empire_os.crawler_data_repository import CrawlerProspectRepository


class FakeBackend:
    value = "test_backend"


class FakeGateway:
    backend = FakeBackend()

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
        self.calls.append(("query", table, tuple(filters), tuple(order), limit, offset))
        return []

    def rpc(self, name, params=None):
        self.calls.append(("rpc", name, dict(params or {})))
        return {
            "decision": "created",
            "prospect_id": "p1",
        }


def test_crawler_repository_lookup_and_ingest_are_vendor_neutral():
    gateway = FakeGateway()
    repository = CrawlerProspectRepository(gateway)
    prepared = {
        "prospect": {
            "business_name": "Roof Co",
            "metro": "austin",
            "niche": "roofing",
        },
        "evidence": {"source": "test"},
        "ingest_key": "k",
    }

    lookup = repository.lookup_existing(prepared)
    result = repository.ingest_atomic({
        "prospect": prepared["prospect"],
        "evidence": prepared["evidence"],
        "ingest_key": "k",
        "identity_keys": ["name_metro:roof co|austin"],
    })

    assert lookup["decision"] == "new"
    assert result["decision"] == "created"
    assert gateway.calls[0][0:2] == ("query", "prospects")
    assert gateway.calls[1][0:2] == ("rpc", "ingest_prospect_atomic")
    assert repository.backend_name == "test_backend"
