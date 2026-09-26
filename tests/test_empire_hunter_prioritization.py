import pytest

from empire_os.hunter.prioritization import (
    prioritize_enrichment,
    rank_enrichment_candidates,
)


def test_high_value_gap_gets_deep_enrichment():
    result = prioritize_enrichment(
        entity_id="entity-1",
        evidence_confidence=0.9,
        omega_score=88,
        omega_confidence=0.8,
        buyer_demand_strength=0.9,
        buyer_demand_confidence=0.9,
        contact_ready=False,
        modeled_expected_gp_cents=250000,
        enrichment_cost_cents=3000,
        evidence_refs=["omega:1", "buyer-demand:1"],
    )

    assert result.depth == "deep"
    assert result.priority_score >= 80
    assert result.economics_is_forecast is True
    assert result.actual_revenue_used is False


def test_contact_already_ready_reduces_enrichment_depth():
    result = prioritize_enrichment(
        entity_id="entity-1",
        evidence_confidence=0.7,
        omega_score=55,
        omega_confidence=0.6,
        contact_ready=True,
        evidence_refs=["contact:verified:1"],
    )

    assert result.depth in {"stop", "shallow"}
    assert "contact_already_ready" in result.reasons


def test_unknown_gp_stays_unknown():
    result = prioritize_enrichment(
        entity_id="entity-1",
        evidence_confidence=0.8,
        omega_score=70,
        omega_confidence=0.7,
        contact_ready=False,
        evidence_refs=["omega:1"],
    )

    assert result.modeled_expected_gp_cents is None
    assert result.economics_is_forecast is False
    assert result.actual_revenue_used is False


def test_requires_evidence_refs():
    with pytest.raises(ValueError, match="evidence refs"):
        prioritize_enrichment(
            entity_id="entity-1",
            evidence_confidence=0.8,
            evidence_refs=[],
        )


def test_rank_orders_highest_priority_first():
    ranked = rank_enrichment_candidates([
        {
            "entity_id": "low",
            "evidence_confidence": 0.4,
            "omega_score": 35,
            "omega_confidence": 0.5,
            "contact_ready": False,
            "evidence_refs": ["a"],
        },
        {
            "entity_id": "high",
            "evidence_confidence": 0.9,
            "omega_score": 90,
            "omega_confidence": 0.9,
            "buyer_demand_strength": 0.8,
            "buyer_demand_confidence": 0.9,
            "contact_ready": False,
            "evidence_refs": ["b"],
        },
    ])

    assert ranked[0].entity_id == "high"
    assert ranked[0].priority_score > ranked[1].priority_score
