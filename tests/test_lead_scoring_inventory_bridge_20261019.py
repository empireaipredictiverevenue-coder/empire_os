from datetime import datetime, timezone
import json

from empire_os.lead_scoring_inventory_bridge import (
    build_scoring_coverage,
    cortex_runtime_summary,
)
from empire_os.intelligence.omega import MODEL_VERSION


def sample():
    prospects = [
        {"id": "p1", "niche": "roofing"},
        {"id": "p2", "niche": "solar"},
        {"id": "p3", "niche": "solar"},
    ]
    q1 = {
        "id": "q1",
        "prospect_id": "p1",
        "entity_id": "e1",
        "status": "scored",
        "scoring_version": "v2",
        "scoring_engine": "empire_os.lead_scoring",
        "evidence_confidence": 0.85,
        "tier": "hot",
        "result_payload": {"enrichment": {"evidence": [{"source": "website"}]}},
        "scored_at": "2026-10-19T08:00:00+00:00",
    }
    q2 = {
        "id": "q2",
        "prospect_id": "p2",
        "entity_id": None,
        "status": "insufficient_evidence",
        "scoring_version": "v2",
        "scoring_engine": "empire_os.lead_scoring",
        "tier": "insufficient_evidence",
        "scored_at": "2026-10-19T08:00:00+00:00",
    }
    links = [{"prospect_id": "p1", "entity_id": "e1", "active": True}]
    score = {
        "id": "s1",
        "entity_type": "company",
        "entity_id": "e1",
        "score_type": "omega_opportunity",
        "model_key": MODEL_VERSION,
        "score": 82,
        "confidence": 0.85,
        "features": {"prospect_id": "p1", "qualification_id": "q1"},
    }
    return prospects, [q1, q2], links, [score]


def test_scoring_coverage_is_independently_evidence_matched():
    p, q, links, scores = sample()
    result = build_scoring_coverage(
        prospects=p, qualifications=q,
        identity_links=links, intelligence_scores=scores,
    )
    assert result["prospect_count"] == 3
    assert result["counts"]["tier_hot"] == 1
    assert result["counts"]["unscored"] == 1
    assert result["counts"]["insufficient_evidence"] == 1
    assert result["counts"]["enrichment_evidence_present"] == 1
    assert result["omega_evidence_matched_unique_prospects"] == 1
    assert result["omega_probabilities_outcome_calibrated"] is False
    assert result["commercial_authority"] == "none"


def test_old_or_wrong_omega_score_is_not_current_readiness():
    p, q, links, scores = sample()
    scores[0]["features"]["qualification_id"] = "obsolete"
    result = build_scoring_coverage(
        prospects=p, qualifications=q,
        identity_links=links, intelligence_scores=scores,
    )
    assert result["counts"]["omega_evidence_matched"] == 0
    assert result["counts"]["omega_stale_or_mismatched"] == 1


def test_unknown_enrichment_is_not_a_zero_score():
    p, q, links, scores = sample()
    q[0].pop("result_payload")
    result = build_scoring_coverage(
        prospects=p, qualifications=q,
        identity_links=links, intelligence_scores=scores,
    )
    assert result["counts"]["enrichment_evidence_present"] == 0
    assert result["counts"]["v2_scored_rows"] == 2


def test_cortex_snapshot_is_stale_not_live_lead_scoring(tmp_path):
    f = tmp_path / "cortex.json"
    f.write_text(json.dumps({
        "schema_version": "empire.cortex_learning_snapshot.v1",
        "generated_at": "2026-09-22T23:16:26+00:00",
        "packet_count": 2,
        "learning_ready_count": 0,
        "verified_customer_learning_count": 0,
    }))
    result = cortex_runtime_summary(
        f, now=datetime(2026, 10, 19, tzinfo=timezone.utc)
    )
    assert result["available"]
    assert result["stale_older_than_24h"]
    assert not result["connected_to_niche_aggregate"]
    assert result["verified_customer_learning_count"] == 0
