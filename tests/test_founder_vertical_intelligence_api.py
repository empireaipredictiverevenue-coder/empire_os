import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.founder_vertical_intelligence_api import (
    create_founder_vertical_intelligence_router,
)


def client(tmp_path):
    inbox = tmp_path / "runtime" / "acquisition"
    inbox.mkdir(parents=True)
    (inbox / "signal_inbox.json").write_text(json.dumps({
        "permit-1": {
            "source": "permits_nyc",
            "status": "resolved",
            "metro": "NYC",
            "last_seen_at": "2026-10-02T21:11:31+00:00",
            "url": "https://example.test/permit/1",
            "raw": {"job__": "P-1"},
        }
    }))
    vi = tmp_path / "runtime" / "vertical_intelligence"
    vi.mkdir(parents=True)
    (vi / "private_capital_latest.json").write_text(json.dumps({
        "generated_at": "2026-10-02T22:00:00+00:00",
        "canonical_signal_count": 0,
        "canonical_fact_count": 0,
        "segment_membership_count": 0,
        "latest_observed_at": None,
    }))
    app = FastAPI()
    app.include_router(create_founder_vertical_intelligence_router(tmp_path))
    return TestClient(app)


def test_permit_runtime_route_exposes_observed_read_only_truth(tmp_path):
    r = client(tmp_path).get("/v1/founder-vertical-intelligence/permit")
    assert r.status_code == 200
    data = r.json()
    assert data["signal_count"] == 1
    assert data["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert data["execution_authority"] == "none"
    assert data["actual_revenue"] is False


def test_property_runtime_route_reuses_permit_evidence_without_revenue_claim(tmp_path):
    r = client(tmp_path).get("/v1/founder-vertical-intelligence/property")
    assert r.status_code == 200
    data = r.json()
    assert data["permit_signal_count"] == 1
    assert data["evidence_state"] == "EVIDENCE_AVAILABLE"
    assert data["execution_authority"] == "none"
    assert data["actual_revenue"] is False


def test_private_capital_unknown_stays_unknown(tmp_path):
    r = client(tmp_path).get("/v1/founder-vertical-intelligence/private-capital")
    assert r.status_code == 200
    data = r.json()
    assert data["snapshot_available"] is True
    assert data["evidence_count"] == 0
    assert data["evidence_state"] == "UNKNOWN"
    assert data["execution_authority"] == "none"
    assert data["actual_revenue"] is False
