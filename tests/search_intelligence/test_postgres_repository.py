import pytest

from empire_os.search_intelligence.postgres_repository import (
    PostgresSearchRepository,
    SearchRepositoryError,
    configured_search_repository_from_env,
)


class Column:
    def __init__(self, name):
        self.name = name


class FakeCursor:
    def __init__(self, calls):
        self.calls = calls
        self.description = []
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.calls.append((normalized, params))
        if "SELECT (SELECT count(*)" in normalized:
            self.description = [
                Column("pages"),
                Column("opportunities"),
                Column("indexed_pages"),
                Column("open_alerts"),
                Column("revenue_cents"),
            ]
            self._rows = [(2, 3, 1, 4, 5000)]
        elif "FROM public.seo_internal_links l" in normalized:
            self.description = [
                Column("id"),
                Column("source_url"),
                Column("target_url"),
            ]
            self._rows = [(
                "link-1",
                "https://example.test/a",
                "https://example.test/b",
            )]
        elif "FROM public.seo_pages p" in normalized:
            self.description = [Column("id"), Column("url")]
            self._rows = [("page-1", "https://example.test/a")]
        else:
            self.description = []
            self._rows = []

    def fetchall(self):
        return list(self._rows)


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return FakeCursor(self.calls)


def connect_factory(calls):
    def connect(dsn):
        calls.append(("CONNECT", dsn))
        return FakeConnection(calls)
    return connect


def test_repository_requires_dedicated_dsn_and_tenant():
    with pytest.raises(SearchRepositoryError, match="DSN"):
        PostgresSearchRepository("", "tenant-a")
    with pytest.raises(SearchRepositoryError, match="tenant_key"):
        PostgresSearchRepository("test-dsn", "")


def test_pages_read_is_transaction_read_only_role_and_tenant_scoped():
    calls = []
    repository = PostgresSearchRepository(
        "test-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )

    rows = repository.pages(limit=7)
    assert rows == [{
        "id": "page-1",
        "url": "https://example.test/a",
    }]

    statements = [
        call for call in calls
        if isinstance(call, tuple) and call[0] != "CONNECT"
    ]
    assert statements[0][0] == "SET TRANSACTION READ ONLY"
    assert statements[1][0] == "SET LOCAL ROLE empire_search_reader"
    assert statements[2] == (
        "SELECT set_config('app.tenant_key', %s, true)",
        ("tenant-a",),
    )
    assert "WHERE s.tenant_key = %s" in statements[3][0]
    assert statements[3][1] == ("tenant-a", 7)


def test_summary_uses_tenant_scoped_read_contract():
    calls = []
    repository = PostgresSearchRepository(
        "test-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )
    assert repository.summary() == {
        "pages": 2,
        "opportunities": 3,
        "indexed_pages": 1,
        "open_alerts": 4,
        "revenue_cents": 5000,
    }
    assert calls[-1][1] == ("tenant-a",) * 5


def test_configured_repository_requires_both_env_bindings(monkeypatch):
    monkeypatch.delenv("EMPIRE_SEARCH_READER_DSN", raising=False)
    monkeypatch.delenv("EMPIRE_SEARCH_TENANT_KEY", raising=False)
    assert configured_search_repository_from_env() is None

    monkeypatch.setenv("EMPIRE_SEARCH_READER_DSN", "test-dsn")
    assert configured_search_repository_from_env() is None

    monkeypatch.setenv("EMPIRE_SEARCH_TENANT_KEY", "tenant-a")
    repository = configured_search_repository_from_env(
        connect_factory=connect_factory([])
    )
    assert repository is not None
    assert repository.tenant_key == "tenant-a"


def test_internal_links_read_is_tenant_scoped_and_bounded():
    calls = []
    repository = PostgresSearchRepository(
        "test-dsn",
        "tenant-a",
        connect_factory=connect_factory(calls),
    )
    rows = repository.internal_links(limit=11)
    assert rows == [{
        "id": "link-1",
        "source_url": "https://example.test/a",
        "target_url": "https://example.test/b",
    }]
    sql, params = calls[-1]
    assert "FROM public.seo_internal_links l" in sql
    assert "WHERE s.tenant_key = %s" in sql
    assert params == ("tenant-a", 11)
