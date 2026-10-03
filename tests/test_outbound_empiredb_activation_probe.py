from empire_os.outbound_empiredb_activation_probe import (
    REQUIRED_COLUMNS,
    REQUIRED_ROLES,
    REQUIRED_TABLES,
    probe_empiredb_deliverability,
)


class FakeCursor:
    def __init__(
        self,
        *,
        tables=True,
        columns=True,
        roles=True,
        privileges=True,
    ):
        self.tables = tables
        self.columns = columns
        self.roles = roles
        self.privileges = privileges
        self._row = None
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, params))
        if "to_regclass" in normalized:
            self._row = (self.tables,)
        elif "information_schema.columns" in normalized:
            self._row = (self.columns,)
        elif "FROM pg_roles" in normalized:
            self._row = (self.roles,)
        elif "has_table_privilege" in normalized:
            self._row = (self.privileges, self.privileges)
        else:
            self._row = None

    def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self._cursor


def factory(cursor):
    def connect(_dsn):
        return FakeConnection(cursor)
    return connect


def test_probe_is_read_only_and_ready_when_schema_roles_privileges_exist():
    cursor = FakeCursor()
    result = probe_empiredb_deliverability(
        "probe-dsn",
        connect_factory=factory(cursor),
    )
    assert result["status"] == "READY"
    assert result["mutation_authorized"] is False
    assert cursor.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert len(result["required_tables"]) == len(REQUIRED_TABLES)
    assert result["required_columns"] == {
        table: list(columns)
        for table, columns in REQUIRED_COLUMNS.items()
    }
    assert result["columns_ready"] is True
    assert result["required_roles"] == list(REQUIRED_ROLES)


def test_probe_blocks_when_roles_are_missing():
    cursor = FakeCursor(roles=False)
    result = probe_empiredb_deliverability(
        "probe-dsn",
        connect_factory=factory(cursor),
    )
    assert result["status"] == "BLOCKED"
    assert result["schema_ready"] is True
    assert result["roles_ready"] is False
    assert sorted(result["missing_roles"]) == sorted(REQUIRED_ROLES)


def test_probe_blocks_when_schema_is_missing():
    cursor = FakeCursor(tables=False)
    result = probe_empiredb_deliverability(
        "probe-dsn",
        connect_factory=factory(cursor),
    )
    assert result["status"] == "BLOCKED"
    assert result["schema_ready"] is False
    assert result["privileges_ready"] is False



def test_probe_blocks_when_required_upgrade_columns_are_missing():
    cursor = FakeCursor(columns=False)
    result = probe_empiredb_deliverability(
        "probe-dsn",
        connect_factory=factory(cursor),
    )
    assert result["status"] == "BLOCKED"
    assert result["tables_ready"] is True
    assert result["columns_ready"] is False
    assert result["schema_ready"] is False
    assert result["missing_columns"]
    assert any(
        value.endswith(".reservation_key")
        for value in result["missing_columns"]
    )
