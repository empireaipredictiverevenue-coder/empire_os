import pytest

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway,
    DataGatewayUnavailable,
    gateway_from_environment,
)
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import ConflictAction, DataFilter, OrderSpec


class FakeProvider:
    backend = DataBackend.SUPABASE_LEGACY

    def __init__(self, configured=True):
        self._configured = configured
        self.calls = []

    def configured(self):
        return self._configured

    def select(self, table, columns="*", filters=None, order=None, limit=1000, offset=0):
        self.calls.append(("select", table))
        return [{"id": "1"}]

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.calls.append(("query", table, tuple(filters), tuple(order)))
        return [{"id": "q1"}]

    def count(self, table, filters=None):
        self.calls.append(("count", table))
        return 7

    def insert(self, table, row, *, return_repr=True):
        self.calls.append(("insert", table))
        return [dict(row)] if return_repr else []

    def upsert(self, table, row, *, conflict_columns, action, return_repr=True):
        self.calls.append(("upsert", table, tuple(conflict_columns), action))
        return [dict(row)] if return_repr else []

    def insert_ignore_conflicts(self, table, row, *, return_repr=False):
        self.calls.append(("insert_ignore_conflicts", table))
        return [dict(row)] if return_repr else []

    def update(self, table, match, values):
        self.calls.append(("update", table))
        return [dict(values)]

    def delete(self, table, match):
        self.calls.append(("delete", table))

    def rpc(self, name, params=None):
        self.calls.append(("rpc", name))
        return {"ok": True}


def test_gateway_is_single_primary_without_write_fallback():
    gateway = CanonicalDataGateway(FakeProvider())
    snapshot = gateway.snapshot().as_dict()

    assert snapshot["primary_backend"] == "supabase_legacy"
    assert snapshot["dual_write_enabled"] is False
    assert snapshot["write_fallback_enabled"] is False


def test_gateway_delegates_without_exposing_vendor_details():
    provider = FakeProvider()
    gateway = CanonicalDataGateway(provider)

    assert gateway.select("prospects") == [{"id": "1"}]
    assert gateway.count("prospects") == 7
    assert gateway.insert("prospects", {"id": "2"}) == [{"id": "2"}]
    assert gateway.update("prospects", {"id": "2"}, {"status": "x"}) == [{"status": "x"}]
    gateway.delete("prospects", {"id": "2"})
    assert gateway.rpc("claim_next_gtm_job") == {"ok": True}

    assert provider.calls == [
        ("select", "prospects"),
        ("count", "prospects"),
        ("insert", "prospects"),
        ("update", "prospects"),
        ("delete", "prospects"),
        ("rpc", "claim_next_gtm_job"),
    ]


def test_unconfigured_backend_fails_closed_instead_of_falling_back():
    gateway = CanonicalDataGateway(FakeProvider(configured=False))

    with pytest.raises(DataGatewayUnavailable, match="not configured"):
        gateway.insert("commercial_events", {"event_type": "test"})


def test_expected_backend_mismatch_is_rejected():
    with pytest.raises(ValueError, match="provider/backend mismatch"):
        CanonicalDataGateway(
            FakeProvider(),
            expected_backend=DataBackend.EMPIREDB,
        )


def test_environment_defaults_to_current_legacy_backend():
    provider = FakeProvider()
    gateway = gateway_from_environment(
        {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SERVICE_KEY": "key"},
        legacy_provider_factory=lambda _: provider,
    )
    assert gateway.backend is DataBackend.SUPABASE_LEGACY


def test_empiredb_selection_fails_closed_until_provider_is_registered():
    with pytest.raises(DataGatewayUnavailable, match="verified runtime provider"):
        gateway_from_environment({"EMPIRE_DATA_BACKEND": "empiredb"})


def test_unknown_backend_selection_fails_closed():
    with pytest.raises(DataGatewayUnavailable, match="unsupported canonical"):
        gateway_from_environment({"EMPIRE_DATA_BACKEND": "mystery"})


def test_gateway_exposes_neutral_query_and_conflict_semantics():
    provider = FakeProvider()
    gateway = CanonicalDataGateway(provider)

    filters = (
        DataFilter.eq("status", "scored"),
        DataFilter.in_("tier", ("hot", "warm")),
        DataFilter.is_null("entity_id"),
    )
    order = (OrderSpec("scored_at", descending=True),)

    assert gateway.query(
        "prospect_qualifications",
        "prospect_id,scored_at",
        filters=filters,
        order=order,
        limit=25,
    ) == [{"id": "q1"}]

    assert gateway.upsert(
        "prospect_qualifications",
        {"prospect_id": "p1", "scoring_engine": "e", "scoring_version": "v2"},
        conflict_columns=("prospect_id", "scoring_engine", "scoring_version"),
        action=ConflictAction.MERGE,
    )[0]["prospect_id"] == "p1"

    assert gateway.insert_ignore_conflicts(
        "commercial_events",
        {"idempotency_key": "k1"},
    ) == []

    assert provider.calls[-3][0] == "query"
    assert provider.calls[-2][:3] == (
        "upsert",
        "prospect_qualifications",
        ("prospect_id", "scoring_engine", "scoring_version"),
    )
    assert provider.calls[-1] == ("insert_ignore_conflicts", "commercial_events")
