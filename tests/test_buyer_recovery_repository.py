from empire_os.buyer_recovery_repository import CanonicalBuyerRecoveryRepository


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
        self.calls.append((table, columns, tuple(filters), tuple(order), limit))
        return [
            {
                "id": "p1",
                "business_name": "Roof Co",
                "niche": "roofing",
                "website": "",
                "metro": "Denver, CO",
            },
            {
                "id": "p2",
                "business_name": "Roof Two",
                "niche": "roofing",
                "website": "https://roof.example",
                "metro": "Denver, CO",
            },
        ]


def test_buyer_recovery_repository_filters_to_website_backed_seeds():
    gateway = FakeGateway()
    repository = CanonicalBuyerRecoveryRepository(gateway)

    rows = repository.prospects_for_target(
        niche="roofing",
        territory="Denver, CO",
        limit=6,
    )

    assert [row["id"] for row in rows] == ["p2"]
    call = gateway.calls[0]
    assert call[0] == "prospects"
    assert call[4] <= 100
    assert [item.column for item in call[2]] == ["niche", "metro"]
