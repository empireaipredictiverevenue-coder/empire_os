"""Lead supply observatory: count truth and fail-closed tests."""
from datetime import datetime, timezone
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_lead_supply_api import (
    create_founder_lead_supply_router, read_lead_supply_report,
)
from empire_os.lead_supply_intelligence import (
    build_lead_supply_report, crawler_receipt_summary,
)
from scripts.report_niche_lead_supply_empiredb import (
    IncompleteCanonicalRead, read_complete_table,
)


def _sample():
    prospects = [
        {"id": "a", "niche": "roofing", "metro": "Chicago", "status": "new"},
        {"id": "b", "niche": "roof repair", "metro": "Chicago", "status": "new"},
        {"id": "c", "niche": "solar", "metro": "Bolton", "status": "new"},
        {"id": "d", "niche": None, "metro": None, "status": "unknown"},
    ]
    acquisitions = [
        {"id": "1", "prospect_id": "a", "source": "permits"},
        {"id": "2", "prospect_id": "a", "source": "overpass"},
        {"id": "3", "prospect_id": "a", "source": "permits"},
        {"id": "4", "prospect_id": "c", "source": "recc_solar"},
    ]
    quals = [
        {"prospect_id": "a", "scoring_engine": "empire_os.lead_scoring",
         "scoring_version": "v2", "tier": "hot", "status": "scored",
         "evidence_confidence": 0.9, "entity_id": "entity_a"},
    ]
    exchange = {
        "canonical_backend": "empiredb",
        "source": "canonical_empiredb_projection",
        "observed_at": "2026-10-19T09:52:00+00:00",
        "inventory": [{"niche_family": "roofing", "state": "overflow_no_capacity"}],
        "inventory_count": 1, "buyer_seats": [
            {"niche_family": "roofing", "seat_state": "blocked_missing_evidence"}
        ],
        "corridor_count": 1, "allocation_candidate_count": 0,
    }
    return prospects, acquisitions, quals, exchange


def test_counts_dedupe_acquisitions_and_keep_unknown_separate():
    p, a, q, exchange = _sample()
    report = build_lead_supply_report(
        prospects=p, acquisitions=a, qualifications=q,
        exchange=exchange, counts_complete=True,
        scanned_tables={"prospects": 4, "prospect_acquisitions": 4},
        observed_at=datetime(2026, 10, 19, tzinfo=timezone.utc),
    )
    assert report["unique_prospects_observed"] == 4
    assert report["acquisition_events_for_scanned_prospects"] == 4
    assert report["source_unique_prospect_counts"] == {
        "overpass": 1, "permits": 1, "recc_solar": 1,
    }
    assert report["prospects_missing_acquisition_provenance"] == 2
    assert report["exchange"]["buyer_seat_states"]["blocked_missing_evidence"] == 1
    assert report["exchange"]["allocation_candidate_count"] == 0
    assert not report["payment_authorized"]
    assert not report["public_self_serve_raw_lead_counts_allowed"]
    assert report["source_unique_prospect_counts_overlap"]


def test_incomplete_scans_are_explicit_and_never_called_total():
    p, a, q, exchange = _sample()
    r = build_lead_supply_report(
        prospects=p[:2], acquisitions=a, qualifications=q, exchange=exchange,
        counts_complete=False, scanned_tables={"prospects": 2},
    )
    assert not r["lead_counts_complete"]
    assert r["incomplete_counts_must_not_be_presented_as_totals"]


def test_crawler_event_counts_are_not_lead_counts(tmp_path):
    path = tmp_path / "crawler_runs.jsonl"
    path.write_text(
        json.dumps({"msg": "prospect_acquired", "source": "permits"}) + "\n"
        + json.dumps({"msg": "prospect_acquired", "source": "permits"}) + "\n"
        + "{bad\n"
    )
    result = crawler_receipt_summary(path)
    assert result["event_totals"]["prospect_acquired"] == 2
    assert result["events_are_not_unique_leads"]
    assert result["malformed_rows"] == 1


class FakeGateway:
    def __init__(self, rows):
        self.rows = list(rows)

    def count(self, table):
        return len(self.rows)

    def query(self, table, columns, **kwargs):
        rows = sorted(self.rows, key=lambda r: r["id"])
        return rows[kwargs["offset"]: kwargs["offset"] + kwargs["limit"]]


def test_private_db_reader_detects_hard_cap_and_duplicate_ids():
    import pytest
    gateway = FakeGateway([{"id": "x"}, {"id": "y"}])
    with pytest.raises(IncompleteCanonicalRead):
        read_complete_table(gateway, "prospects", page_size=1, max_rows=1)
    assert len(read_complete_table(gateway, "prospects", page_size=1, max_rows=5)) == 2
    gateway.rows.append({"id": "x"})
    with pytest.raises(IncompleteCanonicalRead):
        read_complete_table(gateway, "prospects", page_size=2, max_rows=5)


def test_founder_api_fails_closed_without_report(tmp_path):
    missing = tmp_path / "not-found.json"
    app = FastAPI()
    app.include_router(create_founder_lead_supply_router(missing))
    result = TestClient(app).get("/v1/founder-lead-supply/overview")
    assert result.status_code == 200
    assert result.json()["available"] is False


def test_founder_api_reads_only_canonical_reports(tmp_path):
    file = tmp_path / "report.json"
    file.write_text(json.dumps({"schema_version": "empire.lead_supply_intelligence.v1",
                                "canonical_backend": "empiredb", "mode": "OBSERVE",
                                "unique_prospects_observed": 25}))
    assert read_lead_supply_report(file)["unique_prospects_observed"] == 25
    file.write_text(json.dumps({"schema_version": "empire.lead_supply_intelligence.v1",
                                "canonical_backend": "legacy", "mode": "OBSERVE"}))
    assert not read_lead_supply_report(file)["available"]
