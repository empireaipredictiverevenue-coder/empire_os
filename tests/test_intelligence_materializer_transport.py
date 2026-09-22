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


def _competitor_signal():
    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": ENTITY_ID,
        "signal_type": "competitor_audience_evidence",
        "signal_domain": "competitive_intelligence",
        "observed_at": "2026-09-21T20:00:00+00:00",
        "source_id": SOURCE_ID,
        "strength": 0.333333,
        "confidence": 0.91,
        "payload": {
            "company_name": "Acme Roofing",
            "company_domain": "acme.example",
            "competitor_keys": ["competitor-a"],
            "evidence_count": 1,
            "evidence": [{
                "competitor_key": "competitor-a",
                "evidence_type": "customer_case_study",
                "summary": "Observed public case study.",
                "source_ref": "web:competitor-a:case-study:acme",
                "observed_at": "2026-09-21T20:00:00+00:00",
                "confidence": 0.91,
            }],
            "research_candidate": True,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "outreach_enabled": False,
        },
        "persistence_performed": False,
        "prospect_created": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


class CompetitorSignalCursor(FakeCursor):
    def __init__(self, *, duplicate=False):
        super().__init__()
        self.duplicate = duplicate

    def execute(self, sql, params=None):
        text = " ".join(str(sql).split())
        self.calls.append((text, tuple(params or ())))

        if text.startswith("SET LOCAL ROLE"):
            self._set([], [])
        elif "FROM public.intelligence_sources" in text:
            self._set(["id"], [(SOURCE_ID,)])
        elif (
            text.startswith("SELECT payload")
            and "FROM public.intelligence_signals" in text
        ):
            if self.duplicate:
                self._set(
                    ["payload"],
                    [(_competitor_signal()["payload"],)],
                )
            else:
                self._set(["payload"], [])
        elif text.startswith(
            "INSERT INTO public.intelligence_signals"
        ):
            self._set(["id"], [("signal-inserted-id",)])
        else:
            raise AssertionError(f"unexpected SQL: {text}")


def _competitor_writer(*, duplicate=False):
    cursor = CompetitorSignalCursor(duplicate=duplicate)
    connect = FakeConnect(cursor)
    writer = PostgresIntelligenceMaterializer(
        "postgresql://materializer@example/db",
        connect_factory=connect,
    )
    return writer, cursor


def test_competitor_signal_persists_fixed_observe_only_shape():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_audience_signal,
    )

    writer, cursor = _competitor_writer()
    result = persist_competitor_audience_signal(
        writer,
        _competitor_signal(),
    )

    assert result["inserted"] is True
    assert result["existing"] is False
    assert result["execution_authority"] == "none"

    insert_sql = next(
        sql for sql, _ in cursor.calls
        if sql.startswith("INSERT INTO public.intelligence_signals")
    )
    assert "'competitor_audience_evidence'" in insert_sql
    assert "'competitive_intelligence'" in insert_sql

    assert not any(
        sql.startswith(("UPDATE ", "DELETE "))
        for sql, _ in cursor.calls
    )


def test_competitor_signal_is_idempotent_by_evidence_refs():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_audience_signal,
    )

    writer, cursor = _competitor_writer(duplicate=True)
    result = persist_competitor_audience_signal(
        writer,
        _competitor_signal(),
    )

    assert result["inserted"] is False
    assert result["existing"] is True

    assert not any(
        sql.startswith("INSERT INTO public.intelligence_signals")
        for sql, _ in cursor.calls
    )


def test_competitor_signal_rejects_execution_authority():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_audience_signal,
    )

    writer, _ = _competitor_writer()
    signal = _competitor_signal()
    signal["execution_authority"] = "outbound"

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="execution authority",
    ):
        persist_competitor_audience_signal(writer, signal)


def test_competitor_signal_rejects_wrong_canonical_source():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_audience_signal,
    )

    writer, _ = _competitor_writer()
    signal = _competitor_signal()
    signal["source_id"] = (
        "00000000-0000-0000-0000-000000000099"
    )

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="source mismatch",
    ):
        persist_competitor_audience_signal(writer, signal)


def test_competitor_dedupe_ignores_observed_at():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_audience_signal,
    )

    writer, cursor = _competitor_writer(duplicate=True)
    result = persist_competitor_audience_signal(
        writer,
        _competitor_signal(),
    )

    assert result["existing"] is True

    select_sql = next(
        sql for sql, _ in cursor.calls
        if sql.startswith("SELECT payload")
    )
    assert "observed_at=%s" not in select_sql


def test_competitor_evidence_fingerprint_distinguishes_same_page_relationships():
    from empire_os.intelligence_materializer_transport import (
        _competitor_evidence_fingerprints,
    )

    payload_a = _competitor_signal()["payload"]
    payload_b = {
        **payload_a,
        "competitor_keys": ["competitor-b"],
        "evidence": [{
            **payload_a["evidence"][0],
            "competitor_key": "competitor-b",
        }],
    }

    assert (
        _competitor_evidence_fingerprints(payload_a)
        != _competitor_evidence_fingerprints(payload_b)
    )



def _ecosystem_signal():
    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": ENTITY_ID,
        "signal_type": "competitor_ecosystem_evidence",
        "signal_domain": "competitive_intelligence",
        "observed_at": "2026-09-22T12:50:00+00:00",
        "source_id": SOURCE_ID,
        "strength": 1.0,
        "confidence": 0.85,
        "payload": {
            "company_name": "Acme Roofing",
            "company_domain": "acme.example",
            "surface_count": 3,
            "case_study_surface_count": 1,
            "testimonial_surface_count": 1,
            "partner_surface_count": 1,
            "surfaces": [
                {
                    "source_ref": "https://acme.example/projects",
                    "link_text": "Projects",
                    "categories": ["case_study"],
                    "first_party": True,
                    "observed": True,
                },
                {
                    "source_ref": "https://acme.example/reviews",
                    "link_text": "Reviews",
                    "categories": ["testimonial"],
                    "first_party": True,
                    "observed": True,
                },
                {
                    "source_ref": "https://acme.example/partners",
                    "link_text": "Partners",
                    "categories": ["partner"],
                    "first_party": True,
                    "observed": True,
                },
            ],
            "external_relationship_candidates": [{
                "relationship_type": "public_partner_link_candidate",
                "category": "partner",
                "external_domain": "manufacturer.example",
                "source_ref": "https://acme.example/partners",
                "partner_status_inferred": False,
            }],
            "research_candidate": True,
            "customer_relationship_inferred": False,
            "partner_relationship_inferred": False,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "outreach_enabled": False,
        },
        "persistence_performed": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


class EcosystemSignalCursor(FakeCursor):
    def __init__(self, *, duplicate=False):
        super().__init__()
        self.duplicate = duplicate

    def execute(self, sql, params=None):
        text = " ".join(str(sql).split())
        self.calls.append((text, tuple(params or ())))

        if text.startswith("SET LOCAL ROLE"):
            self._set([], [])
        elif "FROM public.intelligence_sources" in text:
            self._set(["id"], [(SOURCE_ID,)])
        elif (
            text.startswith("SELECT payload")
            and "FROM public.intelligence_signals" in text
        ):
            if self.duplicate:
                self._set(
                    ["payload"],
                    [(_ecosystem_signal()["payload"],)],
                )
            else:
                self._set(["payload"], [])
        elif text.startswith(
            "INSERT INTO public.intelligence_signals"
        ):
            self._set(["id"], [("ecosystem-signal-id",)])
        else:
            raise AssertionError(f"unexpected SQL: {text}")


def _ecosystem_writer(*, duplicate=False):
    cursor = EcosystemSignalCursor(duplicate=duplicate)
    connect = FakeConnect(cursor)
    writer = PostgresIntelligenceMaterializer(
        "postgresql://materializer@example/db",
        connect_factory=connect,
    )
    return writer, cursor


def test_ecosystem_signal_persists_fixed_observe_only_shape():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_ecosystem_signal,
    )

    writer, cursor = _ecosystem_writer()
    result = persist_competitor_ecosystem_signal(
        writer,
        _ecosystem_signal(),
    )

    assert result["inserted"] is True
    assert result["existing"] is False
    assert result["execution_authority"] == "none"

    insert_sql = next(
        sql for sql, _ in cursor.calls
        if sql.startswith("INSERT INTO public.intelligence_signals")
    )
    assert "'competitor_ecosystem_evidence'" in insert_sql
    assert "'competitive_intelligence'" in insert_sql

    assert not any(
        sql.startswith(("UPDATE ", "DELETE "))
        for sql, _ in cursor.calls
    )


def test_ecosystem_signal_dedupes_by_observed_surfaces():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_ecosystem_signal,
    )

    writer, cursor = _ecosystem_writer(duplicate=True)
    result = persist_competitor_ecosystem_signal(
        writer,
        _ecosystem_signal(),
    )

    assert result["inserted"] is False
    assert result["existing"] is True
    assert not any(
        sql.startswith("INSERT INTO public.intelligence_signals")
        for sql, _ in cursor.calls
    )


def test_ecosystem_signal_rejects_inferred_customer_relationship():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_ecosystem_signal,
    )

    writer, _ = _ecosystem_writer()
    signal = _ecosystem_signal()
    signal["payload"]["customer_relationship_inferred"] = True

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="customer relationship",
    ):
        persist_competitor_ecosystem_signal(writer, signal)


def test_ecosystem_signal_rejects_execution_authority():
    from empire_os.intelligence_materializer_transport import (
        persist_competitor_ecosystem_signal,
    )

    writer, _ = _ecosystem_writer()
    signal = _ecosystem_signal()
    signal["execution_authority"] = "outbound"

    with pytest.raises(
        IntelligenceMaterializerTransportError,
        match="execution authority",
    ):
        persist_competitor_ecosystem_signal(writer, signal)
