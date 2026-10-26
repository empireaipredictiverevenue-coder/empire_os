"""Historical 33K recovery contracts: pagination, cursor, archive provenance."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from empire_os.qualification_data_repository import QualificationDataRepository
from empire_os.qualification_historical_backfill_cursor import (
    load_cursor, save_cursor,
)
from empire_os.tam_historical_cohort import inspect_archive


class FakeGateway:
    def __init__(self, page, qualifications):
        self.page = page
        self.qualifications = qualifications
        self.queries = []

    def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
        self.queries.append({
            "table": table, "limit": limit, "offset": offset,
            "order": order,
        })
        if table == "prospects":
            return self.page[:limit]
        if table == "prospect_qualifications":
            return self.qualifications
        raise AssertionError("unexpected source table")


def prospect(pid):
    return {"id": pid, "created_at": "2026-09-01T00:00:00Z"}


def test_historical_page_escapes_newest_window_starvation():
    # Pages deliberately start at an old offset, not the current newest 40.
    gateway = FakeGateway(
        [prospect(f"p{i}") for i in range(30)],
        [{"prospect_id": "p0"}, {"prospect_id": "p2"}],
    )
    page = QualificationDataRepository(gateway).fetch_historical_pending_page(
        offset=32000, limit=2, scoring_engine="empire_os.lead_scoring",
        scoring_version="v2",
    )
    assert [r["id"] for r in page["candidate_rows"]] == ["p1", "p3"]
    assert page["scanned_rows"] == 4
    assert page["next_offset"] == 32004
    assert page["archive_exhausted"] is False
    assert gateway.queries[0]["table"] == "prospects"
    assert gateway.queries[0]["offset"] == 32000
    assert len(gateway.queries[0]["order"]) == 2
    assert gateway.queries[1]["table"] == "prospect_qualifications"


def test_pagination_advances_past_fully_scored_page():
    gateway = FakeGateway(
        [prospect(f"p{i}") for i in range(8)],
        [{"prospect_id": f"p{i}"} for i in range(8)],
    )
    page = QualificationDataRepository(gateway).fetch_historical_pending_page(
        offset=200, limit=5, scoring_engine="engine", scoring_version="v2",
    )
    assert page["candidate_rows"] == []
    assert page["scanned_rows"] == 8
    assert page["next_offset"] == 208
    assert page["archive_exhausted"] is True


def test_backfill_never_silently_skips_unvisited_pending_candidates():
    gateway = FakeGateway(
        [prospect(f"p{i}") for i in range(25)], [],
    )
    page = QualificationDataRepository(gateway).fetch_historical_pending_page(
        offset=0, limit=5, scoring_engine="engine", scoring_version="v2",
    )
    assert [r["id"] for r in page["candidate_rows"]] == [f"p{i}" for i in range(5)]
    assert page["next_offset"] == 5
    assert page["archive_exhausted"] is False


@pytest.mark.parametrize("offset,limit", [
    (-1, 10), (True, 10), (1.5, 10), (1_000_001, 10),
    (0, 0), (0, True), (0, 26),
])
def test_backfill_rejects_unbounded_cursors(offset, limit):
    gateway = FakeGateway([], [])
    with pytest.raises(ValueError):
        QualificationDataRepository(gateway).fetch_historical_pending_page(
            offset=offset, limit=limit, scoring_engine="engine", scoring_version="v2",
        )
    assert gateway.queries == []


def test_cursor_atomic_roundtrip_and_invalid_input(tmp_path):
    path = tmp_path / "runtime" / "qualification" / "cursor.json"
    assert load_cursor(path) == 0
    save_cursor(25, path=path)
    assert load_cursor(path) == 25
    assert path.stat().st_mode & 0o077 == 0
    save_cursor(50, path=path)
    assert load_cursor(path) == 50
    with pytest.raises(ValueError):
        save_cursor(True, path=path)


def test_cursor_refuses_symlink(tmp_path):
    real = tmp_path / "real.json"
    real.write_text("{}")
    link = tmp_path / "cursor.json"
    link.symlink_to(real)
    with pytest.raises(ValueError, match="unsafe"):
        load_cursor(link)
    with pytest.raises(ValueError, match="unsafe"):
        save_cursor(1, path=link)


def test_worker_historical_backfill_uses_existing_scoring_and_redacts_ids(monkeypatch):
    from empire_os import qualification_worker_v2 as worker

    class Repo:
        def fetch_historical_pending_page(self, **kwargs):
            assert kwargs["offset"] == 1000
            assert kwargs["limit"] == 2
            return {
                "candidate_rows": [{"id": "secret-person-1"}],
                "scanned_rows": 9, "next_offset": 1009, "archive_exhausted": False,
            }
    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())
    monkeypatch.setattr(worker, "_run_prospects", lambda prospects, *, schema_version: {
        "schema_version": schema_version, "ok": True, "attempted": len(prospects),
        "qualified": 1, "failed": 0, "identity_resolved": 0,
        "results": [{"prospect_id": "secret-person-1"}],
    })
    result = worker.run_historical_backfill_batch(offset=1000, limit=2)
    assert result["proposed_next_offset"] == 1009
    assert result["qualified"] == 1
    assert result["cursor_may_advance"] is True
    assert "secret-person-1" not in json.dumps(result)
    assert result["outbound_authorized"] is False


def test_historical_archive_aggregate_no_contact_export(tmp_path):
    path = tmp_path / "migration.sql"
    source = """COPY "public"."prospects" ("id", "created_at", "business_name", "niche", "metro", "phone", "website", "status", "contact_name", "contact_title") FROM stdin;
p1	2026-08-01T00:00:00Z	SECRET_FIRM	roofing	Boston	555SECRET	https://secret.example	new	SECRET_PERSON	CEO
p2	2026-08-01T00:00:00Z	Another company	solar	\\N	\\N	\\N	new	\\N	\\N
\\.
COPY "public"."prospect_qualifications" ("prospect_id", "scoring_engine", "scoring_version", "status", "tier", "evidence_confidence") FROM stdin;
p1	empire_os.lead_scoring	v2	scored	hot	0.7
\\.
COPY "public"."prospect_entity_links" ("prospect_id", "entity_id", "active") FROM stdin;
p1	e1	t
\\.
COPY "public"."prospect_acquisitions" ("prospect_id", "source") FROM stdin;
p1	public-registry
\\.
"""
    path.write_text(source, encoding="utf-8")
    report = inspect_archive(dump=path, max_bytes=20_000)
    assert report["archived_unique_prospects"] == 2
    assert report["archived_v2_qualified_count"] == 1
    assert report["archived_v2_hot_warm_evidence_candidates"] == 1
    assert report["archived_prospects_without_v2_qualification"] == 1
    assert report["archived_identity_linked_prospects"] == 1
    assert report["archived_missing_metro"] == 1
    assert "SECRET" not in json.dumps(report)
    assert report["source_is_current_empiredb_query"] is False
    assert report["outbound_authorized"] is False


def test_historical_archived_orphan_link_fails_closed(tmp_path):
    path = tmp_path / "archived.sql"
    path.write_text("""COPY "public"."prospects" ("id", "niche") FROM stdin;
p1	roofing
\\.
COPY "public"."prospect_entity_links" ("prospect_id", "entity_id", "active") FROM stdin;
p2	e2	t
\\.
""")
    with pytest.raises(ValueError, match="references outside"):
        inspect_archive(dump=path, max_bytes=20_000)
