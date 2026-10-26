"""Historical 33K recovery contracts: pagination, cursor, archive provenance."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from empire_os.qualification_data_repository import QualificationDataRepository
from empire_os.qualification_historical_backfill_cursor import (
    load_cursor, save_cursor,
)


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


def test_backfill_reports_aggregate_evidence_and_tiers_without_identity_leak(monkeypatch):
    from empire_os import qualification_worker_v2 as worker

    class Repo:
        def fetch_historical_pending_page(self, **kwargs):
            return {
                "candidate_rows": [
                    {"id": "secret-p1", "website": "https://private.example"},
                    {"id": "secret-p2", "website": ""},
                    {"id": "secret-p3", "website": "https://other.example"},
                ],
                "scanned_rows": 5,
                "next_offset": 25,
                "archive_exhausted": False,
            }
    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())
    monkeypatch.setattr(worker, "_run_prospects", lambda prospects, *, schema_version: {
        "schema_version": schema_version, "ok": True, "attempted": 3,
        "qualified": 3, "failed": 0, "identity_resolved": 0,
        "results": [
            {"prospect_id": "secret-p1", "tier": "hot", "evidence_confidence": .8},
            {"prospect_id": "secret-p2", "tier": "warm", "evidence_confidence": .2},
            {"prospect_id": "secret-p3", "tier": "dead", "evidence_confidence": .0},
        ],
    })
    report = worker.run_historical_backfill_batch(offset=20, limit=3)
    assert report["tier_counts"] == {"dead": 1, "hot": 1, "warm": 1}
    assert report["hot_warm_above_evidence_floor"] == 1
    assert report["input_website_fields_present_unverified"] == 2
    assert report["proposed_next_offset"] == 25
    assert "secret-p" not in json.dumps(report)
    assert "private.example" not in json.dumps(report)
    assert report["outbound_authorized"] is False


def test_identity_linked_archive_backfill_prioritises_existing_canonical_links():
    class LinkedGateway:
        def __init__(self):
            self.calls = []

        def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
            self.calls.append((table, limit, offset, tuple(filters), tuple(order)))
            if table == "prospect_entity_links":
                return [
                    {"id": f"link{i}", "prospect_id": f"p{i}",
                     "entity_id": f"e{i}", "active": True}
                    for i in range(30)
                ]
            if table == "prospect_qualifications":
                return [{"prospect_id": "p0"}, {"prospect_id": "p1"}]
            if table == "prospects":
                return [
                    {"id": "p4", "website": "https://verified.example"},
                    {"id": "p2", "website": None},
                    {"id": "p3", "website": None},
                ]
            raise AssertionError("unexpected DB table")
    gw = LinkedGateway()
    report = QualificationDataRepository(gw).fetch_historical_identity_linked_page(
        offset=500, limit=3, scoring_engine="empire_os.lead_scoring",
        scoring_version="v2",
    )
    assert [p["id"] for p in report["candidate_rows"]] == ["p2", "p3", "p4"]
    assert report["next_offset"] == 505
    assert report["scanned_rows"] == 5
    assert report["archive_exhausted"] is False
    assert [c[0] for c in gw.calls] == [
        "prospect_entity_links", "prospect_qualifications", "prospects",
    ]
    assert gw.calls[0][2] == 500
    assert len(gw.calls[0][4]) == 2


def test_identity_linked_archive_page_all_scored_still_progresses():
    class GW:
        def query(self, table, columns="*", *, filters=(), order=(), limit=1000, offset=0):
            if table == "prospect_entity_links":
                return [{"id": "l1", "prospect_id": "p1", "active": True}]
            if table == "prospect_qualifications":
                return [{"prospect_id": "p1"}]
            raise AssertionError("should not fetch scored prospect")
    report = QualificationDataRepository(GW()).fetch_historical_identity_linked_page(
        offset=4, limit=5, scoring_engine="empire_os.lead_scoring",
        scoring_version="v2",
    )
    assert report["candidate_rows"] == []
    assert report["next_offset"] == 5
    assert report["archive_exhausted"] is True


def test_historical_identity_linked_batch_uses_same_v2_scorer(monkeypatch):
    from empire_os import qualification_worker_v2 as worker

    class LinkedRepo:
        def fetch_historical_identity_linked_page(self, **kwargs):
            return {
                "candidate_rows": [{"id": "p1", "website": "https://private.example"}],
                "scanned_rows": 6, "next_offset": 12, "archive_exhausted": False,
            }
    monkeypatch.setattr(worker, "_qualification_repository", lambda: LinkedRepo())
    monkeypatch.setattr(worker, "_run_prospects", lambda prospects, *, schema_version: {
        "schema_version": schema_version,
        "ok": True, "attempted": 1, "qualified": 1,
        "failed": 0, "identity_resolved": 1,
        "results": [{"prospect_id": "p1", "tier": "hot", "evidence_confidence": .88}],
    })
    result = worker.run_historical_backfill_batch(
        offset=6, limit=1, identity_linked=True,
    )
    assert result["selection_cohort"] == "ACTIVE_IDENTITY_LINKED_UNSCORED"
    assert result["identity_resolved"] == 1
    assert result["hot_warm_above_evidence_floor"] == 1
    assert result["cursor_may_advance"] is True
    assert result["proposed_next_offset"] == 12
    assert result["outbound_authorized"] is False
    assert "private.example" not in json.dumps(result)


def test_backfill_reports_insufficient_evidence_as_distinct_tier(monkeypatch):
    from empire_os import qualification_worker_v2 as worker

    class Repo:
        def fetch_historical_pending_page(self, **kwargs):
            return {
                "candidate_rows": [{"id": "private-p1", "website": ""}],
                "scanned_rows": 1,
                "next_offset": 9,
                "archive_exhausted": False,
            }
    monkeypatch.setattr(worker, "_qualification_repository", lambda: Repo())
    monkeypatch.setattr(worker, "_run_prospects", lambda rows, *, schema_version: {
        "schema_version": schema_version,
        "ok": True, "attempted": 1, "qualified": 1, "failed": 0,
        "identity_resolved": 0,
        "results": [{
            "prospect_id": "private-p1", "entity_id": None,
            "tier": "insufficient_evidence", "evidence_confidence": .3,
            "identity_resolved": False,
        }],
    })
    result = worker.run_historical_backfill_batch(offset=8, limit=1)
    assert result["tier_counts"] == {"insufficient_evidence": 1}
    assert result["hot_warm_above_evidence_floor"] == 0
    assert result["omega_projection"]["scores_written"] == 0
    assert result["cortex_evidence_review"]["accounts_evidence_reviewed"] == 0
    assert "private-p1" not in json.dumps(result)
