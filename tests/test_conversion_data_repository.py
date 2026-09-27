from empire_os.conversion_data_repository import CanonicalConversionRepository


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
        self.calls.append((table, columns, tuple(filters), limit))
        return []


def test_conversion_repository_reads_all_canonical_surfaces():
    gateway = FakeGateway()
    repository = CanonicalConversionRepository(gateway)

    repository.approved_reviews()
    repository.delivered_or_replied_intents()
    repository.commercial_replies()
    repository.closer_cases()
    repository.commercial_terms()
    repository.accepted_orders()
    repository.payment_evidence()
    repository.commercial_outcomes()

    assert [call[0] for call in gateway.calls] == [
        "buyer_candidate_reviews",
        "outbound_intents",
        "outbound_replies",
        "closer_cases",
        "commercial_terms_reviews",
        "fulfilment_orders",
        "bsc_payment_evidence",
        "commercial_outcomes",
    ]
    assert all(call[3] == 5000 for call in gateway.calls)
