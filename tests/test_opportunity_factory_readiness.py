from empire_os.opportunity_factory_readiness import evaluate_factory_readiness


def complete_candidate():
    factors = {
        "demand": 0.8,
        "quality": 0.8,
        "enrichment": 0.8,
        "omega_qualification": 0.8,
        "buyer_match": 0.8,
        "outreach": 0.8,
        "conversion": 0.5,
        "terms": 1.0,
        "payment": 0.8,
        "fulfilment": 0.9,
        "ltv_cents": 150000,
    }
    return {
        "offer_key": "managed_service",
        "commercial_demand_observed": True,
        "predictive_revenue_inputs": factors,
        "predictive_revenue_evidence_refs": {
            key: [f"canonical:{key}:1"] for key in factors
        },
    }


def test_complete_explicit_evidence_is_factory_ready():
    result = evaluate_factory_readiness(complete_candidate())
    assert result["opportunity_factory_ready"] is True
    assert result["factory_blockers"] == []
    assert result["execution_authority"] == "none"


def test_partial_evidence_remains_blocked():
    candidate = complete_candidate()
    candidate["predictive_revenue_inputs"].pop("payment")
    candidate["predictive_revenue_evidence_refs"].pop("payment")
    result = evaluate_factory_readiness(candidate)
    assert result["opportunity_factory_ready"] is False
    assert "normalized_economics_required" in result["factory_blockers"]


def test_score_or_proxy_fields_cannot_create_readiness():
    result = evaluate_factory_readiness({
        "offer_key": "managed_service",
        "commercial_demand_observed": True,
        "observed_priority_score": 100,
        "buyer_capacity": 1000,
        "normalized_signals": {"demand": 1.0},
    })
    assert result["opportunity_factory_ready"] is False
    assert "qualification_evidence_required" in result["factory_blockers"]
    assert "normalized_economics_required" in result["factory_blockers"]


def test_missing_evidence_refs_cannot_create_readiness():
    candidate = complete_candidate()
    candidate["predictive_revenue_evidence_refs"] = {}
    result = evaluate_factory_readiness(candidate)
    assert result["opportunity_factory_ready"] is False
    assert result["factory_blockers"]
