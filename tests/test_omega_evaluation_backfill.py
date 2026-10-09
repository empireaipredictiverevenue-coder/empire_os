import pytest
from empire_os.intelligence.omega import analyze
from empire_os.omega_evaluation_backfill import BackfillConflict, plan_enrichment


def fixture():
    lead = {"business_name": "Example Roofing", "niche": "roofing"}
    prediction = analyze(lead)
    score = {"entity_id": "entity-1", "scored_at": "2026-10-09T00:00:00Z", "score_type": "omega_opportunity", "model_key": prediction.model_version, "score": prediction.opportunity_score, "features": {}, "explanation": {}}
    return score, lead


def test_additive_plan_never_writes():
    score, lead = fixture()
    plan = plan_enrichment(score, lead)
    assert plan["needs_enrichment"] is True
    assert plan["feature_additions"]["evaluation_grade"]
    assert plan["database_write_authorized"] is False
    assert score["features"] == {}


def test_idempotent_plan():
    score, lead = fixture()
    plan = plan_enrichment(score, lead)
    score["features"].update(plan["feature_additions"])
    score["explanation"].update(plan["explanation_additions"])
    assert plan_enrichment(score, lead)["needs_enrichment"] is False


def test_model_drift_fails_closed():
    score, lead = fixture()
    score["score"] += 1
    with pytest.raises(BackfillConflict, match="differs"):
        plan_enrichment(score, lead)


def test_conflicting_existing_fields_fail_closed():
    score, lead = fixture()
    score["features"]["evaluation_grade"] = "WRONG"
    with pytest.raises(BackfillConflict, match="conflicting"):
        plan_enrichment(score, lead)
