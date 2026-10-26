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


def test_omega_projection_includes_read_only_evaluation_contract():
    q = qualification()
    row = worker.build_omega_score_row(q, identity_link(q))
    features = row["features"]
    assert features["evaluation_schema_version"] == "empire.omega-evaluation.v2"
    assert features["evaluation_grade"] in {"A", "B", "C", "D"}
    assert len(features["evaluation_evidence_coverage"]) == 8
    assert row["explanation"]["evaluation_only"] is True
    assert row["explanation"]["value_meter"]["verified_realized_revenue"] is None


def test_targeted_historical_omega_reuses_evidence_and_is_idempotent(monkeypatch):
    q = qualification()
    seen = []
    monkeypatch.setattr(
        worker, "fetch_omega_qualification_for_prospect",
        lambda pid: q if pid == q["prospect_id"] else None,
    )
    monkeypatch.setattr(worker, "fetch_identity_link", lambda pid: identity_link(q))
    monkeypatch.setattr(worker, "score_exists", lambda row: bool(seen))
    monkeypatch.setattr(worker, "persist_score", lambda row: seen.append(row))
    first = worker.run_targeted_omega_cycle([q["prospect_id"]])
    second = worker.run_targeted_omega_cycle([q["prospect_id"]])
    assert first["scores_written"] == 1
    assert first["failed"] == 0
    assert second["scores_written"] == 0
    assert second["skipped_existing"] == 1
    assert len(seen) == 1
    assert seen[0]["features"]["evaluation_schema_version"] == "empire.omega-evaluation.v2"
    assert first["execution_authority"] == "none"
    assert q["prospect_id"] not in str(first)


def test_targeted_omega_excludes_unqualified_evidence(monkeypatch):
    q = qualification(evidence_confidence=0.12)
    monkeypatch.setattr(worker, "fetch_omega_qualification_for_prospect", lambda pid: q)
    monkeypatch.setattr(worker, "fetch_identity_link", lambda pid: identity_link(q))
    monkeypatch.setattr(worker, "persist_score", lambda row: pytest.fail("must not persist"))
    report = worker.run_targeted_omega_cycle([q["prospect_id"]])
    assert report["scores_written"] == 0
    assert report["failed"] == 1
    assert report["ok"] is False


def test_targeted_omega_exact_qualification_reader(monkeypatch):
    q = qualification()
    seen = {}
    def reader(method, url):
        seen["url"] = url
        assert method == "GET"
        return [q]
    monkeypatch.setattr(worker, "request_json", reader)
    row = worker.fetch_omega_qualification_for_prospect(q["prospect_id"])
    assert row == q
    assert q["prospect_id"] in seen["url"]
    assert "scoring_version=eq.v2" in seen["url"]


def test_targeted_omega_missing_candidate_remains_unknown(monkeypatch):
    monkeypatch.setattr(worker, "fetch_omega_qualification_for_prospect", lambda pid: None)
    report = worker.run_targeted_omega_cycle(["prospect-x"])
    assert report["not_evidence_ready"] == 1
    assert report["scores_written"] == 0
