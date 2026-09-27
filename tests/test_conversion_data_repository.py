from empire_os.conversion_data_repository import ConversionDataRepository
from empire_os.data_query import FilterOperator


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
        self.queries = []

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append({
            "table": table,
            "columns": columns,
            "filters": tuple(filters),
            "limit": limit,
        })
        return []

    def snapshot(self):
        return Snapshot()


def test_conversion_repository_uses_semantic_filters():
    gateway = FakeGateway()
    repository = ConversionDataRepository(gateway)

    repository.approved_buyer_reviews()
    repository.delivered_or_replied_intents()
    repository.commercial_replies()
    repository.accepted_paid_fulfilled_orders()

    by_table = {query["table"]: query for query in gateway.queries}

    assert any(
        item.column == "status"
        and item.operator is FilterOperator.EQ
        and item.value == "approved"
        for item in by_table["buyer_candidate_reviews"]["filters"]
    )
    assert any(
        item.column == "status"
        and item.operator is FilterOperator.IN
        and item.value == ("delivered", "replied")
        for item in by_table["outbound_intents"]["filters"]
    )
    assert any(
        item.column == "classification"
        and item.operator is FilterOperator.IN
        for item in by_table["outbound_replies"]["filters"]
    )
    assert any(
        item.column == "state"
        and item.operator is FilterOperator.IN
        and item.value == ("accepted", "paid", "fulfilled")
        for item in by_table["fulfilment_orders"]["filters"]
    )


def test_conversion_repository_is_read_only():
    snapshot = ConversionDataRepository(FakeGateway()).snapshot()

    assert snapshot["repository_authority"] == "read_only"
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False
