"""Provider lifecycle/security tests; no database connectivity."""
import pytest

from empire_os import sb
from empire_os.canonical_data_gateway import CanonicalDataGateway, DataGatewayOperationUnsupported
from empire_os.data_backends.empiredb import EmpireDbProvider
from empire_os.data_cloud_contract import DataBackend
from test_data_cloud_empiredb_provider import FakeConnection, FakeConnector


def test_transaction_reuses_sql_and_defers_all_crud_lifecycle():
    connection = FakeConnection()
    provider = EmpireDbProvider(FakeConnector(connection))
    with provider.transaction() as transaction:
        transaction.insert("prospects", {"id": "one"})
        transaction.update("prospects", {"id": "one", "contact_name": None}, {"contact_name": "Adam"})
        transaction.query("prospects", "id")
        transaction.delete("prospects", {"id": "one"})
        assert connection.commits == 0 and not connection.closed
    assert connection.commits == 1 and connection.closed
    assert transaction.state == "committed"
    update, params = next(call for call in connection.calls if call[0].startswith("UPDATE"))
    assert '"contact_name" IS NULL' in update and '"id" = %s' in update
    assert params == ("Adam", "one")
    with pytest.raises(RuntimeError):
        transaction.query("prospects", "id")


@pytest.mark.parametrize("failure", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_any_escaping_exception_rolls_back(failure):
    connection = FakeConnection()
    provider = EmpireDbProvider(FakeConnector(connection))
    with pytest.raises(failure):
        with provider.transaction() as transaction:
            transaction.insert("prospects", {"id": "one"})
            raise failure()
    assert connection.commits == 0 and connection.rollbacks == 2
    assert transaction.state == "rolled_back" and connection.closed


def test_swallowed_sql_error_cannot_commit():
    class FailedConnection(FakeConnection):
        def execute(self, sql, params=()):
            if sql.startswith("INSERT"):
                raise RuntimeError("write failed")
            return super().execute(sql, params)
    connection = FailedConnection()
    with pytest.raises(RuntimeError, match="transaction has failed"):
        with EmpireDbProvider(FakeConnector(connection)).transaction() as transaction:
            with pytest.raises(RuntimeError):
                transaction.insert("prospects", {"id": "one"})
    assert connection.commits == 0
    assert transaction.state == "rolled_back"


@pytest.mark.parametrize("method,path,payload", [
    ("PATCH", "/rest/v1/prospects", {"contact_name": "Adam"}),
    ("DELETE", "/rest/v1/prospects", None),
    ("PATCH", "/rest/v1/prospects?id=ilike.*", {"contact_name": "Adam"}),
    ("POST", "/rest/v1/prospects;DROP", {"id": "one"}),
    ("POST", "/rest/v1/prospects", {"id;DROP": "one"}),
    ("POST", "/rest/v1/prospects?on_conflict=id;DROP", {"id": "one"}),
    ("POST", "/rest/v1/rpc/propose_outbound_intent", {}),
])
def test_transaction_does_not_bypass_gateway_security(monkeypatch, method, path, payload):
    connection = FakeConnection()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: CanonicalDataGateway(EmpireDbProvider(FakeConnector(connection))))
    with pytest.raises((ValueError, DataGatewayOperationUnsupported)):
        with sb.empiredb_transaction() as request:
            request(method, path, payload=payload)
    assert not any(sql.startswith(("INSERT", "UPDATE", "DELETE", "SELECT")) for sql, _ in connection.calls)
    assert connection.commits == 0


def test_transaction_parameterizes_values_and_keeps_equality(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(sb, "_runtime_gateway", lambda: CanonicalDataGateway(EmpireDbProvider(FakeConnector(connection))))
    from urllib.parse import urlencode
    dangerous = "O'Brien'; DROP TABLE prospects; --"
    with sb.empiredb_transaction() as request:
        request("PATCH", "/rest/v1/prospects?" + urlencode({"id": "eq.one", "contact_source": "eq." + dangerous}),
                payload={"contact_name": dangerous})
    sql, params = next(call for call in connection.calls if call[0].startswith("UPDATE"))
    assert dangerous not in sql
    assert '"contact_source" = %s' in sql
    assert params == (dangerous, "one", dangerous)


def test_non_empiredb_gateway_cannot_begin_transaction():
    class Legacy:
        backend = DataBackend.SUPABASE_LEGACY
        def configured(self):
            return True
        def transaction(self):
            raise AssertionError("legacy backend accessed")
    with pytest.raises(DataGatewayOperationUnsupported):
        with CanonicalDataGateway(Legacy()).transaction():
            pass


def test_nested_transaction_is_rejected():
    connection = FakeConnection()
    with pytest.raises(DataGatewayOperationUnsupported):
        with EmpireDbProvider(FakeConnector(connection)).transaction() as transaction:
            transaction.transaction()
    assert not connection.commits


@pytest.mark.parametrize("next_action", ["read", "commit"])
def test_expired_transaction_rolls_back_before_next_action(monkeypatch, next_action):
    import empire_os.data_backends.empiredb as module
    clock = [0]
    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    connection = FakeConnection()
    with pytest.raises(TimeoutError):
        with EmpireDbProvider(FakeConnector(connection)).transaction() as transaction:
            transaction.insert("prospects", {"id": "one"})
            clock[0] = 61
            if next_action == "read":
                transaction.query("prospects", "id")
    assert connection.commits == 0 and connection.closed
    assert transaction.state == "rolled_back"


def test_failed_rollback_does_not_mask_original_error_or_claim_commit():
    class BrokenRollback(FakeConnection):
        def rollback(self):
            super().rollback()
            if self.rollbacks > 1:
                raise ConnectionError("private rollback error")
    connection = BrokenRollback()
    with pytest.raises(ValueError, match="original"):
        with EmpireDbProvider(FakeConnector(connection)).transaction() as transaction:
            transaction.insert("prospects", {"id": "one"})
            raise ValueError("original")
    assert transaction.state == "rollback_unconfirmed"
    assert not transaction.write_outcome_unknown  # COMMIT was never attempted
    assert connection.closed and not connection.commits
