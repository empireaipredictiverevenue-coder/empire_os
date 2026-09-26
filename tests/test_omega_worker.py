from uuid import uuid4

import pytest

import empire_os.omega_worker as worker


def qualification(**overrides):
    prospect_id = str(uuid4())
    entity_id = str(uuid4())
    row = {
        "id": str(uuid4()),
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "score": 72.0,
        "tier": "warm",
        "status": "scored",
        "scoring_engine": "empire_os.lead_scoring",
        "scoring_version": "v2",
        "evidence_confidence": 0.60,
        "input_snapshot": {
            "business_name": "Real Roofing",
            "niche": "roofing",
            "metro": "Houston, TX",
            "phone": "7135550101",
        },
        "scored_at": "2026-09-20T12:00:00+00:00",
    }
    row.update(overrides)
    return row
def identity_link(row):
    return {
        "prospect_id": row["prospect_id"],
        "entity_id": row["entity_id"],
        "match_method": "singleton_evidence_v1",
        "match_score": 1.0,
        "active": True,
    }


def test_omega_row_uses_evidence_confidence_not_model_confidence():
    q = qualification()
    row = worker.build_omega_score_row(q, identity_link(q))

    assert row["score_type"] == "omega_opportunity"
    assert row["model_key"] == "omega-2.0-baseline"
    assert row["confidence"] == 0.60
    assert row["features"]["model_feature_confidence"] != row["confidence"]
    assert row["explanation"]["score_semantics"].endswith("not revenue")


def test_unknown_commercial_value_remains_unknown():
    q = qualification()
    row = worker.build_omega_score_row(q, identity_link(q))

    assert row["features"]["expected_revenue"] is None
    assert row["features"]["expected_gross_profit"] is None
    assert row["explanation"]["commercial_value_known"] is False
    assert row["explanation"]["gross_profit_known"] is False
def test_identity_mismatch_fails_closed():
    q = qualification()
    link = identity_link(q)
    link["entity_id"] = str(uuid4())

    with pytest.raises(worker.OmegaWorkerError, match="entity mismatch"):
        worker.build_omega_score_row(q, link)


def test_evidence_below_floor_fails_closed():
    q = qualification(evidence_confidence=0.49)

    with pytest.raises(worker.OmegaWorkerError, match="below decision floor"):
        worker.build_omega_score_row(q, identity_link(q))


def test_cycle_skips_existing_score(monkeypatch):
    q = qualification()
    monkeypatch.setattr(worker, "fetch_omega_candidates", lambda limit: [q])
    monkeypatch.setattr(
        worker,
        "fetch_identity_link",
        lambda prospect_id: identity_link(q),
    )
    monkeypatch.setattr(worker, "score_exists", lambda row: True)

    def fail_persist(row):
        raise AssertionError("existing score must not be written")

    monkeypatch.setattr(worker, "persist_score", fail_persist)
    result = worker.run_omega_cycle(limit=5)

    assert result["scores_written"] == 0
    assert result["skipped_existing"] == 1
    assert result["failed"] == 0
    assert result["recognized_revenue_written"] is False
