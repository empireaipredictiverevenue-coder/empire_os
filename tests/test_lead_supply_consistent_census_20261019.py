"""Prove the private collector does not claim a coherent census from races."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json

import pytest

from scripts.report_niche_lead_supply_empiredb import (
    COLUMNS, IncompleteCanonicalRead, run,
)


def _fixture_rows():
    return {
        "prospects": [
            {"id": "p1", "niche": "roofing", "metro": "Chicago", "status": "new"},
            {"id": "p2", "niche": "solar", "metro": "Bolton", "status": "new"},
        ],
        "prospect_acquisitions": [
            {"id": "a1", "prospect_id": "p1", "source": "permits"},
        ],
        "prospect_qualifications": [
            {
                "id": "q1", "prospect_id": "p1", "entity_id": "entity1",
                "scoring_engine": "empire_os.lead_scoring",
                "scoring_version": "v2", "status": "scored",
                "evidence_confidence": 0.9, "score": 80, "tier": "hot",
                "scored_at": "2026-10-19T08:00:00Z",
                "result_payload": {"enrichment": {"evidence": [{"source": "website"}]}},
            },
        ],
        "prospect_entity_links": [
            {"id": "link1", "prospect_id": "p1", "entity_id": "entity1", "active": True},
        ],
        "intelligence_scores": [
            {
                "id": "o1", "entity_type": "company", "entity_id": "entity1",
                "score_type": "omega_opportunity",
                "model_key": "omega-2.0-baseline", "score": 88,
                "confidence": 0.9, "features": {"prospect_id": "p1", "qualification_id": "q1"},
            },
        ],
        "strike_packs": [
            {"id": "pack1", "slug": "historical", "name": "Historical",
             "niches": ["roofing"], "tier": "standard",
             "monthly_price_cents": 9900, "is_public": True, "is_active": True},
        ],
        "buyer_subscriptions": [
            {"id": "sub1", "buyer_id": "buyer1", "pack_id": "pack1",
             "status": "active", "active": True,
             "monthly_price_cents": 9900, "period_start": "2026-10-01T00:00:00Z"},
        ],
    }


class SnapshotBackend:
    def __init__(self, tables, *, denied=(), mutate_during_count=False):
        self.tables = tables
        self.denied = set(denied)
        self.opens = 0
        self.closes = 0
        self.denied_attempts = []
        self.mutate_during_count = mutate_during_count

    @contextmanager
    def read_only_snapshot(self):
        self.opens += 1
        reader = SnapshotLease(
            {table: [dict(r) for r in rows] for table, rows in self.tables.items()},
            self.denied, self.denied_attempts,
        )
        try:
            yield reader
        finally:
            self.closes += 1
            if self.mutate_during_count:
                self.tables["prospects"].append({
                    "id": f"new-after-{self.opens}", "niche": "roofing",
                    "metro": "Chicago", "status": "new",
                })


class SnapshotLease:
    def __init__(self, tables, denied, denied_attempts):
        self.tables = tables
        self.denied = denied
        self.denied_attempts = denied_attempts

    def count(self, table):
        if table in self.denied:
            self.denied_attempts.append(table)
            raise PermissionError("not authorized")
        return len(self.tables[table])

    def query(self, table, columns, *, order, offset, limit):
        if table in self.denied:
            raise PermissionError("not authorized")
        assert columns == COLUMNS[table]
        rows = sorted(self.tables[table], key=lambda r: r["id"])
        return rows[offset:offset + limit]


def _root(tmp_path):
    path = tmp_path / "runtime" / "commercial_exchange"
    path.mkdir(parents=True)
    (path / "latest.json").write_text(json.dumps({
        "canonical_backend": "empiredb",
        "source": "canonical_empiredb_projection",
        "observed_at": "2026-10-19T09:52:00Z",
        "buyer_seats": [{
            "buyer_id": "buyer1",
            "niche_family": "roofing", "metro": "Chicago",
            "seat_state": "blocked_missing_evidence",
        }],
        "inventory": [], "inventory_count": 0,
        "corridor_count": 1, "allocation_candidate_count": 0,
    }))
    return tmp_path


def test_snapshot_keeps_required_counts_consistent_even_during_ingest(tmp_path):
    backend = SnapshotBackend(_fixture_rows(), mutate_during_count=True)
    report = run(
        backend, root=_root(tmp_path), page_size=1,
        snapshot_factory=backend.read_only_snapshot,
    )
    assert backend.opens == 4
    assert backend.closes == 4
    assert report["unique_prospects_observed"] == 2
    assert len(backend.tables["prospects"]) == 6
    assert report["qualified_with_evidence_observed"] == 1
    assert report["scoring_coverage"]["counts"]["omega_evidence_matched"] == 1
    assert report["territory_mrr"]["buyer_subscription_record_count"] == 1
    assert report["transactionally_consistent_snapshot_proven"] is True
    assert report["snapshot_consistency"]["cross_source_commercial_consistency_proven"] is False
    markets = report["territory_mrr"]
    assert markets["complete_canonical_niche_supply_join_available"] is True
    assert markets["canonical_unique_prospects_reconciled"] == 2
    assert markets["canonical_qualified_with_evidence_reconciled"] == 1
    assert markets["markets_without_exchange_corridor_count"] == 2
    assert {m["niche"] for m in markets["territory_markets"]} == {"roofing", "solar"}
    assert not any(m["sale_ready"] for m in markets["territory_markets"])


def test_optional_permission_denial_does_not_fabricate_zero(tmp_path):
    backend = SnapshotBackend(_fixture_rows(), denied={
        "intelligence_scores", "buyer_subscriptions",
    })
    report = run(
        backend, root=_root(tmp_path), page_size=1,
        snapshot_factory=backend.read_only_snapshot,
    )
    assert backend.opens == backend.closes == 4
    assert not report["scoring_coverage"]["available"]
    assert report["scoring_coverage"]["error_class"] == "PermissionError"
    assert report["territory_mrr"]["buyer_subscription_record_count"] is None
    assert report["territory_mrr"]["optional_reader_error_classes"] == {
        "buyer_subscriptions": "PermissionError",
    }
    assert report["territory_mrr"]["strike_pack_record_count"] == 1
    assert report["transactionally_consistent_snapshot_proven"]


def test_required_reader_denial_aborts_entire_census(tmp_path):
    backend = SnapshotBackend(
        _fixture_rows(), denied={"prospect_acquisitions"},
    )
    with pytest.raises(PermissionError):
        run(
            backend, root=_root(tmp_path),
            snapshot_factory=backend.read_only_snapshot,
        )
    assert backend.opens == backend.closes == 1


def test_hard_row_cap_abort_is_a_hard_error_not_partial_total(tmp_path):
    backend = SnapshotBackend(_fixture_rows())
    with pytest.raises(IncompleteCanonicalRead):
        run(
            backend, root=_root(tmp_path),
            max_rows_per_table=1,
            snapshot_factory=backend.read_only_snapshot,
        )
    assert backend.opens == backend.closes == 1
