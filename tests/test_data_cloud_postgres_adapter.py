import pytest

from empire_os.data_backends.postgres import (
    PostgresConnectionConfig,
    PostgresConnector,
)


class FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, row=("empire", False), fail=False):
        self.row = row
        self.fail = fail
        self.executed = []
        self.closed = False

    def execute(self, query, params=()):
        self.executed.append((query, params))
        if self.fail:
            raise RuntimeError("boom")
        if "current_database" in query:
            return FakeResult(self.row)
        return FakeResult(None)

    def close(self):
        self.closed = True


def test_config_never_exposes_dsn():
    config = PostgresConnectionConfig(dsn="postgresql://secret@example/db")
    snapshot = config.safe_snapshot()
    assert "dsn" not in snapshot
    assert snapshot["dsn_configured"] is True


def test_public_database_port_configuration_fails_closed():
    with pytest.raises(ValueError, match="public EmpireDB"):
        PostgresConnectionConfig(
            dsn="postgresql://example/db",
            public_database_port_allowed=True,
        ).validate()


def test_from_env_requires_empiredb_dsn():
    with pytest.raises(ValueError, match="DSN"):
        PostgresConnectionConfig.from_env({})


def test_connector_applies_statement_timeout_and_reports_health():
    fake = FakeConnection()
    seen = {}

    def factory(**kwargs):
        seen.update(kwargs)
        return fake

    connector = PostgresConnector(
        PostgresConnectionConfig(
            dsn="postgresql://private/empire",
            statement_timeout_ms=2500,
        ),
        connect_factory=factory,
    )
    result = connector.health()

    assert result["healthy"] is True
    assert result["database"] == "empire"
    assert result["in_recovery"] is False
    assert seen["application_name"] == "empire-data-cloud"
    assert fake.executed[0] == (
        "SELECT set_config('statement_timeout', %s, false)",
        ("2500",),
    )
    assert fake.closed is True


def test_failed_health_is_bounded_and_does_not_leak_dsn():
    fake = FakeConnection(fail=True)
    connector = PostgresConnector(
        PostgresConnectionConfig(dsn="postgresql://secret/private"),
        connect_factory=lambda **_: fake,
    )
    result = connector.health()

    assert result["healthy"] is False
    assert result["error_class"] == "RuntimeError"
    assert "secret" not in str(result)
    assert result["authority"]["production_cutover"] is False
    assert fake.closed is True
