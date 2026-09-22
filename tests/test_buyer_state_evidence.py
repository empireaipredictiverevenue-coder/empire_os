from empire_os.buyer_state_evidence import (
    BUYER_STATES,
    build_buyer_state_for_entity,
    build_buyer_state_snapshot,
)


def _row(
    *,
    name="Golden Spike Roofing Inc",
    entity_id="entity-golden",
    prospect_id="prospect-golden",
    qualification_status="insufficient_evidence",
    qualification_tier="insufficient_evidence",
    recommended_action="Collect evidence before commercial action",
    contacted_status="not_contacted",
    contacted_at=None,
    competitive_signal_count=2,
):
    return {
        "entity_id": entity_id,
        "canonical_name": name,
        "prospect_id": prospect_id,
        "match_score": 1.0,
        "link_active": True,
        "prospect_status": "new",
        "contacted_status": contacted_status,
        "contacted_at": contacted_at,
        "qualification_score": 86.2,
        "qualification_tier": qualification_tier,
        "qualification_status": qualification_status,
        "recommended_action": recommended_action,
        "scored_at": "2026-09-22T11:00:00+00:00",
        "competitive_signal_count": competitive_signal_count,
    }


def _brief(entity_id="entity-golden"):
    return {
        "entity_id": entity_id,
        "company_name": "Golden Spike Roofing Inc",
        "claim_critic": {
            "supported_count": 3,
            "blocked_count": 0,
            "all_published_claims_supported": True,
        },
    }


def _state(result, name):
    return next(row for row in result["states"] if row["state"] == name)


def test_competitor_evidence_does_not_promote_buyer_intent():
    result = build_buyer_state_for_entity(
        _row(),
        account_brief=_brief(),
    )

    assert _state(result, "SIGNAL_ACTIVE")["observed"] is True
    assert _state(result, "RESEARCHED")["observed"] is True

    assert _state(result, "COMMERCIAL_INTENT")["observed"] is None
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["competitor_evidence_is_buyer_intent"] is False
    assert result["outreach_enabled"] is False


def test_insufficient_qualification_stays_unknown_not_ready():
    result = build_buyer_state_for_entity(
        _row(),
        account_brief=_brief(),
    )

    assert _state(result, "ICP_MATCH")["observed"] is None
    assert _state(result, "READY")["observed"] is None
    assert result["current_factual_state"] == "RESEARCHED"


def test_scored_governed_contact_can_mark_ready_without_commercial_intent():
    result = build_buyer_state_for_entity(
        _row(
            name="Colorado's Best Roofing",
            entity_id="entity-colorado",
            prospect_id="prospect-colorado",
            qualification_status="scored",
            qualification_tier="hot",
            recommended_action="Review for immediate governed contact",
        ),
        account_brief=_brief("entity-colorado"),
    )

    assert _state(result, "ICP_MATCH")["observed"] is True
    assert _state(result, "READY")["observed"] is True
    assert _state(result, "CONTACTED")["observed"] is False
    assert result["current_factual_state"] == "READY"

    assert _state(result, "COMMERCIAL_INTENT")["observed"] is None
    assert result["qualification_score_is_commercial_intent"] is False
    assert result["commercial_intent_inferred"] is False


def test_not_contacted_is_observed_false_not_unknown():
    result = build_buyer_state_for_entity(
        _row(),
        account_brief=_brief(),
    )

    contacted = _state(result, "CONTACTED")
    assert contacted["observed"] is False
    assert contacted["evidence"]["contacted_status"] == "not_contacted"


def test_downstream_states_remain_unknown_without_canonical_evidence():
    result = build_buyer_state_for_entity(
        _row(),
        account_brief=_brief(),
    )

    for state in BUYER_STATES[6:]:
        assert _state(result, state)["observed"] is None


def test_snapshot_preserves_separate_company_states():
    rows = [
        _row(),
        _row(
            name="Colorado's Best Roofing",
            entity_id="entity-colorado",
            prospect_id="prospect-colorado",
            qualification_status="scored",
            qualification_tier="hot",
            recommended_action="Review for immediate governed contact",
            competitive_signal_count=1,
        ),
    ]
    briefs = [
        _brief(),
        _brief("entity-colorado"),
    ]

    result = build_buyer_state_snapshot(
        rows,
        account_briefs=briefs,
    )

    assert result["entity_count"] == 2
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"

    by_name = {
        row["company_name"]: row
        for row in result["entities"]
    }
    assert by_name["Golden Spike Roofing Inc"]["current_factual_state"] == (
        "RESEARCHED"
    )
    assert by_name["Colorado's Best Roofing"]["current_factual_state"] == (
        "READY"
    )
