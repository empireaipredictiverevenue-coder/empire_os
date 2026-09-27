from empire_os.identity_promotion_repository import IdentityPromotionRepository


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
        self.calls.append(("query", table, tuple(filters), limit))
        return [
            {"prospect_id": "p1", "entity_id": "e1"},
            {"prospect_id": "p2", "entity_id": "e2"},
        ]

    def insert_ignore_conflicts(
        self,
        table,
        row,
        *,
        conflict_columns=(),
        return_repr=False,
    ):
        self.calls.append((
            "insert_ignore",
            table,
            dict(row),
            tuple(conflict_columns),
            return_repr,
        ))
        return []


def test_identity_promotion_repository_uses_gateway_semantics():
    gateway = FakeGateway()
    repository = IdentityPromotionRepository(gateway)

    links = repository.existing_links(["p1", "p2"], batch_size=200)
    repository.ensure_entity({"id": "e1"})
    repository.ensure_link({"prospect_id": "p1", "entity_id": "e1"})

    assert links == {"p1": "e1", "p2": "e2"}
    assert gateway.calls[0][0:2] == ("query", "prospect_entity_links")
    assert gateway.calls[1][0:2] == ("insert_ignore", "business_entities")
    assert gateway.calls[1][3] == ("id",)
    assert gateway.calls[2][0:2] == ("insert_ignore", "prospect_entity_links")
    assert gateway.calls[2][3] == ("prospect_id",)
