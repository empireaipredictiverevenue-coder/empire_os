from empire_os.buyer_discovery_repository import BuyerDiscoveryRepository
from empire_os.data_query import FilterOperator


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
        self.calls.append((table, columns, tuple(filters), tuple(order), limit, offset))
        if offset:
            return []
        return [{"id": "1"}]


def test_buyer_discovery_repository_uses_canonical_query_semantics():
    gateway = FakeGateway()
    repository = BuyerDiscoveryRepository(gateway)

    repository.prospects()
    repository.active_entity_links()
    repository.acquisitions()

    assert gateway.calls[0][0] == "prospects"
    assert gateway.calls[1][0] == "prospect_entity_links"
    assert gateway.calls[1][2][0].column == "active"
    assert gateway.calls[1][2][0].operator is FilterOperator.EQ
    assert gateway.calls[1][2][0].value is True
    assert gateway.calls[2][0] == "prospect_acquisitions"
    assert gateway.calls[2][3][0].column == "created_at"
    assert gateway.calls[2][3][0].descending is True
