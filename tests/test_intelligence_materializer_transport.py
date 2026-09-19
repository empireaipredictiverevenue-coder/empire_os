from types import SimpleNamespace

import pytest

from empire_os.intelligence_materializer_transport import (
    IntelligenceMaterializerTransportError,
    PostgresIntelligenceMaterializer,
)


PROSPECT_ID = "00000000-0000-0000-0000-000000000001"
ENTITY_ID = "00000000-0000-0000-0000-000000000011"
QUALIFICATION_ID = "00000000-0000-0000-0000-000000000021"
SOURCE_ID = "00000000-0000-0000-0000-000000000031"


class FakeCursor:
    def __init__(self, *, links=1, existing=False, explode=False):
        self.links = links
        self.existing = existing
        self.explode = explode
        self.calls = []
        self.description = []
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def _set(self, names, rows):
        self.description = [
            SimpleNamespace(name=name) for name in names
        ]
        self._rows = list(rows)

    def execute(self, sql, params=None):
        text = " ".join(str(sql).split())
        self.calls.append((text, tuple(params or ())))
        if self.explode:
            raise RuntimeError("backend secret detail")

        if text.startswith("SET LOCAL ROLE"):
            self._set([], [])
        elif "FROM public.prospects" in text:
            self._set(
                [
                    "id","created_at","business_name","niche",
                    "metro","address","rating","review_count",
                    "runs_ads",
                ],
                [(
                    PROSPECT_ID,
                    "2026-09-19T09:00:00+00:00",
                    "Acme Ltd","roofing","London",
                    "1 Test Street",4.8,25,False,
                )],
            )
        elif "FROM public.prospect_entity_links" in text:
            self._set(
                ["prospect_id","entity_id","match_score","active"],
                [
                    (PROSPECT_ID, ENTITY_ID, 0.9, True)
                    for _ in range(self.links)
                ],
            )

        elif "FROM public.prospect_qualifications" in text:
            self._set(
                [
                    "id","prospect_id","score","tier",
                    "data_completeness_score",
                    "business_presence_score",
                    "market_fit_score",
                    "engagement_potential_score",
                    "enrichment_quality_score",
                    "recommended_action",
                    "scoring_engine","scoring_version","scored_at",
                ],
                [(
                    QUALIFICATION_ID,PROSPECT_ID,76.4,"hot",
                    60.0,80.0,70.0,0.0,20.0,
                    "Contact immediately",
                    "empire_os.lead_scoring","v1",
                    "2026-09-19T09:05:00+00:00",
                )],
            )
        elif "FROM public.intelligence_sources" in text:
            self._set(["id"], [(SOURCE_ID,)])
        elif text.startswith("INSERT INTO public.intelligence_"):
            self._set(
                ["id"],
                [] if self.existing else [("inserted-id",)],
            )
        else:
            raise AssertionError(f"unexpected SQL: {text}")

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def fetchall(self):
        rows = list(self._rows)
        self._rows = []
        return rows


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_obj = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj


class FakeConnect:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.dsns = []

    def __call__(self, dsn):
        self.dsns.append(dsn)
        return FakeConnection(self.cursor_obj)


def make_writer(*, links=1, existing=False, explode=False):
    cursor = FakeCursor(
        links=links,
        existing=existing,
        explode=explode,
    )
    connect = FakeConnect(cursor)
    writer = PostgresIntelligenceMaterializer(
        "postgresql://materializer@example/db",
        connect_factory=connect,
    )
    return writer, cursor, connect


def test_materialize_sets_role_and_inserts_only_fixed_shapes():
    writer, cursor, connect = make_writer()

    result = writer.materialize(PROSPECT_ID)

    assert connect.dsns == [
        "postgresql://materializer@example/db"
    ]
    assert cursor.calls[0][0] == (
        "SET LOCAL ROLE empire_intelligence_materializer"
    )
    assert result["prospect_id"] == PROSPECT_ID
    assert result["entity_id"] == ENTITY_ID
    assert result["facts_inserted"] == 7
    assert result["scores_inserted"] == 1
    assert result["facts_existing"] == 0
    assert result["scores_existing"] == 0
    qualification_sql = next(
        sql for sql, _ in cursor.calls
        if "FROM public.prospect_qualifications" in sql
    )
    assert "scoring_version IN (\'v2\',\'v1\')" in qualification_sql
    assert "CASE scoring_version WHEN \'v2\' THEN 0 ELSE 1 END" in qualification_sql
    assert not any(
        call[0].startswith(("UPDATE ", "DELETE "))
        for call in cursor.calls
    )


def test_idempotent_conflicts_are_counted_as_existing():
    writer, _, _ = make_writer(existing=True)

    result = writer.materialize(PROSPECT_ID)

    assert result["facts_inserted"] == 0
    assert result["facts_existing"] == 7
    assert result["scores_inserted"] == 0
    assert result["scores_existing"] == 1


def test_multiple_active_identity_links_fail_closed():
    writer, _, _ = make_writer(links=2)

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="exactly one active identity link",
    ):
        writer.materialize(PROSPECT_ID)


def test_invalid_uuid_fails_before_connect():
    writer, _, connect = make_writer()

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="invalid prospect id",
    ):
        writer.materialize("not-a-uuid")

    assert connect.dsns == []


def test_backend_error_is_sanitized():
    writer, _, _ = make_writer(explode=True)

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="dedicated Intelligence materializer failed",
    ) as raised:
        writer.materialize(PROSPECT_ID)

    assert "backend secret detail" not in str(raised.value)


def test_missing_dsn_fails_closed(monkeypatch):
    monkeypatch.delenv(
        "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
        raising=False,
    )
    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="DSN is required",
    ):
        PostgresIntelligenceMaterializer.from_env()
