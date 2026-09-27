from empire_os.gtm_publisher_repository import GTMPublisherRepository


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
        return [{"id": "opp-1"}]

    def update(self, table, match, values):
        self.calls.append(("update", table, dict(match), dict(values)))
        return [dict(values)]

    def insert(self, table, row, *, return_repr=True):
        self.calls.append(("insert", table, dict(row), return_repr))
        return [{"id": "opp-2", **dict(row)}] if return_repr else []

    def insert_ignore_conflicts(
        self,
        table,
        row,
        *,
        conflict_columns=(),
        return_repr=False,
    ):
        self.calls.append(("insert_ignore", table, dict(row), tuple(conflict_columns), return_repr))
        return [{"id": "job-1", **dict(row)}] if return_repr else []


def test_gtm_repository_owns_persistence_semantics():
    gateway = FakeGateway()
    repository = GTMPublisherRepository(gateway)

    found = repository.find_opportunity("roofing", "Austin, TX")
    repository.update_opportunity("opp-1", {"status": "discovered"})
    inserted = repository.insert_opportunity({"niche": "solar"})
    job = repository.insert_job_if_new({"idempotency_key": "k"})
    repository.append_event({"event_type": "gtm_opportunity_published"})

    assert found["id"] == "opp-1"
    assert inserted["id"] == "opp-2"
    assert job["id"] == "job-1"
    assert [call[0:2] for call in gateway.calls] == [
        ("query", "gtm_opportunities"),
        ("update", "gtm_opportunities"),
        ("insert", "gtm_opportunities"),
        ("insert_ignore", "gtm_jobs"),
        ("insert", "commercial_events"),
    ]
