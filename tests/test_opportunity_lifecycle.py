from empire_os.opportunity_evidence_router import build_evidence_routes
from empire_os.opportunity_lifecycle import derive_opportunity_lifecycle


def candidate(**overrides):
    row = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "niche": "roofing",
        "metro": "denver",
        "trigger": "observed_market_evidence",
        "offer_key": "managed_service",
        "evidence_refs": ["canonical:a", "canonical:b"],
    }
    row.update(overrides)
    return row


def intake(**overrides):
    row = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "offer_key": "managed_service",
        "evidence_count": 2,
        "factory_ready": False,
        "blockers": [
            "buyer_intent_normalized_score_required",
            "demand_normalized_score_required",
            "fulfilment_readiness_normalized_score_required",
        ],
        "normalization": {"score_evidence": {}},
    }
    row.update(overrides)
    return row


def test_research_signal_can_qualify_without_becoming_commercially_validated():
    life = derive_opportunity_lifecycle(candidate(), intake())
    assert life.current_stage == "QUALIFY"
    assert life.qualified is True
    assert life.validated is False
    assert life.factory_ready is False


def test_observed_commercial_stage_advances_to_validate_not_experiment():
    row = intake(
        normalization={
            "score_evidence": {
                "buyer_intent": {
                    "semantic_class": "observed_stage",
                    "observed_truth": True,
                }
            }
        }
    )
    life = derive_opportunity_lifecycle(candidate(), row)
    assert life.current_stage == "VALIDATE"
    assert life.commercial_validation_observed is True
    assert life.experiment_ready is False


def test_blocker_router_separates_internal_work_from_commercial_observation():
    payload = build_evidence_routes(
        {"candidates": [candidate()]},
        {"items": [intake()]},
    )
    item = payload["items"][0]
    by_blocker = {
        route["blocker"]: route
        for route in item["routes"]
    }
    assert by_blocker[
        "buyer_intent_normalized_score_required"
    ]["blocker_can_be_satisfied_by_public_search"] is False
    assert by_blocker[
        "fulfilment_readiness_normalized_score_required"
    ]["capability"] == "commercial_product_catalog_and_fulfilment"
    assert payload["stage_counts"] == {"QUALIFY": 1}
    assert payload["execution_authority"] == "none"
