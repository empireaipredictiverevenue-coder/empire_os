from empire_os.data_backends.empiredb import (
    EmpireDbProvider,
    _RPC_PARAMS,
    _RPC_SQL_CASTS,
)


class Cursor:
    def fetchone(self):
        return ({
            "decision": "test",
        },)


class Connection:
    def __init__(self):
        self.calls = []
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, sql, params):
        self.calls.append(
            (sql, params)
        )
        return Cursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class Connector:
    config_snapshot = {
        "dsn_configured": True,
    }

    def __init__(self):
        self.connection = Connection()

    def _open_connection(self):
        return self.connection

    def adapt_value(self, value):
        return value


def test_buyer_scout_promotion_rpc_is_mapped_with_uuid_cast():
    assert (
        _RPC_PARAMS[
            "promote_buyer_scout_candidate_to_prospect"
        ]
        == (
            "p_candidate_id",
            "p_actor",
        )
    )

    assert (
        _RPC_SQL_CASTS[
            "promote_buyer_scout_candidate_to_prospect"
        ]
        == {
            "p_candidate_id": "uuid",
        }
    )


def test_buyer_scout_promotion_rpc_executes_exact_contract():
    connector = Connector()

    provider = EmpireDbProvider(
        connector
    )

    result = provider.rpc(
        "promote_buyer_scout_candidate_to_prospect",
        {
            "p_candidate_id":
                "4fb00bfd-8219-49b8-8442-36cf3f926742",
            "p_actor":
                "empire_autonomous_commercial_progression",
        },
    )

    assert result == {
        "decision": "test",
    }

    assert connector.connection.calls == [(
        (
            'SELECT public.'
            '"promote_buyer_scout_candidate_to_prospect"'
            '(%s::uuid, %s)'
        ),
        (
            "4fb00bfd-8219-49b8-8442-36cf3f926742",
            "empire_autonomous_commercial_progression",
        ),
    )]

    assert (
        connector.connection.committed
        is True
    )

    assert (
        connector.connection.rolled_back
        is False
    )

    assert (
        connector.connection.closed
        is True
    )
