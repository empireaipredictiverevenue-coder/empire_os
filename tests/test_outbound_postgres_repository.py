import pytest

from empire_os.outbound_postgres_repository import (
    DeliverabilityRepositoryError,
    PostgresDeliverabilityEvidenceWriter,
    PostgresDeliverabilityRepository,
    configured_deliverability_repository_from_env,
)
from empire_os.outbound_state_replay import replay_health_state


class Column:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, calls):
        self.calls = calls
        self.description = [Column("id"), Column("metric_name")]
        self._rows = [("row-1", "bounce_rate")]
        self._fetchone = ("new-id",)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, params))
        if "FROM (" in normalized and "evidence_hash" in normalized:
            self.description = [Column("evidence_hash")]
            self._rows = [("row-1",)]

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._fetchone


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.calls)

    def commit(self):
        self.calls.append(("COMMIT", None))


def connect_factory(calls):
    def connect(dsn):
        calls.append(("CONNECT", dsn))
        return FakeConnection(calls)
    return connect


def test_reader_is_read_only_role_and_scope_scoped():
    calls = []
    repo = PostgresDeliverabilityRepository(
        "reader-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )
    repo.observations(limit=7)

    statements = [call for call in calls if call[0] != "CONNECT"]
    assert statements[0][0] == "SET TRANSACTION READ ONLY"
    assert statements[1][0] == "SET LOCAL ROLE empire_outbound_deliverability_reader"
    assert statements[2] == (
        "SELECT set_config('app.scope_key', %s, true)",
        ("tenant-a",),
    )
    assert "WHERE scope_key = %s" in statements[3][0]
    assert statements[3][1] == ("tenant-a", 7)


def test_writer_is_append_only_and_requires_non_mutating_decision():
    calls = []
    writer = PostgresDeliverabilityEvidenceWriter(
        "writer-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )
    result = writer.append_decision({
        "decision_key": "d1",
        "posture": "HOLD",
        "hard_holds": ["bounce"],
        "tasks": [],
        "evidence": {},
        "mutation_authorized": False,
    })
    assert result["id"] == "new-id"
    sql_text = " ".join(call[0] for call in calls if call[0] not in {"CONNECT", "COMMIT"})
    assert "INSERT INTO public.outbound_ringleader_decisions" in sql_text
    assert " UPDATE " not in f" {sql_text.upper()} "
    assert " DELETE " not in f" {sql_text.upper()} "

    with pytest.raises(
        DeliverabilityRepositoryError,
        match="mutation_authorized_false",
    ):
        writer.append_decision({
            "decision_key": "d2",
            "posture": "READY",
            "mutation_authorized": True,
        })


def test_env_repository_requires_both_bindings(monkeypatch):
    monkeypatch.delenv("EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN", raising=False)
    monkeypatch.delenv("EMPIRE_OUTBOUND_SCOPE_KEY", raising=False)
    assert configured_deliverability_repository_from_env() is None

    monkeypatch.setenv("EMPIRE_OUTBOUND_DELIVERABILITY_READER_DSN", "reader-dsn")
    assert configured_deliverability_repository_from_env() is None


def test_replay_rebuilds_latest_asset_metrics_deterministically():
    result = replay_health_state([
        {
            "id": "1",
            "observed_at": "2026-10-03T10:00:00+00:00",
            "domain": "mail.example.com",
            "metric_name": "bounce_rate",
            "metric_value": 0.01,
            "source": "resend",
        },
        {
            "id": "2",
            "observed_at": "2026-10-03T11:00:00+00:00",
            "domain": "mail.example.com",
            "metric_name": "bounce_rate",
            "metric_value": 0.02,
            "source": "resend",
        },
    ])
    asset = result["assets"]["mail.example.com"]
    assert asset["metrics"]["bounce_rate"] == 0.02
    assert result["mutation_authorized"] is False


def test_latest_evidence_head_uses_read_only_scope_contract():
    calls = []
    repo = PostgresDeliverabilityRepository(
        "reader-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )
    # Fake row maps to id/metric_name columns; enough to exercise SQL contract.
    value = repo.latest_evidence_head()
    assert value == "row-1"
    sql, params = calls[-1]
    assert "outbound_deliverability_observations" in sql
    assert "outbound_ringleader_decisions" in sql
    assert params == ("tenant-a", "tenant-a")



def test_sender_estate_inventory_is_scope_scoped_and_read_only():
    calls = []
    repo = PostgresDeliverabilityRepository(
        "reader-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )

    result = repo.sender_estate_inventory(capacity_date="2026-10-03")

    assert set(result) == {
        "transports",
        "domains",
        "mailboxes",
        "pools",
        "pool_members",
        "capacity_events",
        "seed_mailboxes",
    }

    sql_calls = [
        call for call in calls
        if call[0] not in {
            "CONNECT",
            "SET TRANSACTION READ ONLY",
            "SET LOCAL ROLE empire_outbound_deliverability_reader",
            "SELECT set_config('app.scope_key', %s, true)",
        }
    ]
    assert len(sql_calls) == 7
    assert all("WHERE scope_key = %s" in sql for sql, _ in sql_calls)
    capacity_sql, capacity_params = next(
        (sql, params)
        for sql, params in sql_calls
        if "outbound_capacity_ledger" in sql
    )
    assert "capacity_date = %s::date" in capacity_sql
    assert capacity_params == ("tenant-a", "2026-10-03")
