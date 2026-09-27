from empire_os.next_best_action import (
    build_next_best_action_snapshot,
    derive_next_best_action,
)


def _entity(
    *,
    name="Golden Spike Roofing Inc",
    entity_id="entity-golden",
    current="RESEARCHED",
    ready=None,
    contacted=False,
    engaged=None,
    conversation=None,
    commercial_intent=None,
    terms=None,
    payment_pending=None,
    paid=None,
    fulfilled=None,
):
    state_values = {
        "DISCOVERED": True,
        "ICP_MATCH": None,
        "SIGNAL_ACTIVE": True,
        "RESEARCHED": True,
        "READY": ready,
        "CONTACTED": contacted,
        "ENGAGED": engaged,
        "CONVERSATION": conversation,
        "COMMERCIAL_INTENT": commercial_intent,
        "TERMS": terms,
        "PAYMENT_PENDING": payment_pending,
        "PAID": paid,
        "FULFILLED": fulfilled,
        "EXPANSION": None,
    }
    return {
        "entity_id": entity_id,
        "company_name": name,
        "prospect_id": "prospect-1",
        "current_factual_state": current,
        "unknown_states": [
            key for key, value in state_values.items()
            if value is None
        ],
        "states": [
            {"state": key, "observed": value, "evidence": {}}
            for key, value in state_values.items()
        ],
    }


def test_researched_but_not_ready_recommends_more_research():
    result = derive_next_best_action(_entity())

    assert result["recommended_action"] == "research_more"
    assert result["mutation_authorized"] is False
    assert result["outreach_authorized"] is False
    assert result["commercial_intent_inferred"] is False


def test_ready_not_contacted_requires_decision_maker_verification():
    result = derive_next_best_action(
        _entity(
            name="Colorado's Best Roofing",
            entity_id="entity-colorado",
            current="READY",
            ready=True,
        ),
        account_context={"decision_maker_verified": False},
    )

    assert result["recommended_action"] == "verify_decision_maker"
    assert result["founder_gate_required"] is False
    assert result["external_execution_authorized"] is False


def test_verified_decision_maker_allows_buyer_review_preparation_only():
    result = derive_next_best_action(
        _entity(current="READY", ready=True),
        account_context={"decision_maker_verified": True},
    )

    assert result["recommended_action"] == "prepare_buyer_review"
    assert result["authority"] == "internal_write"
    assert result["outreach_authorized"] is False
    assert result["mutation_authorized"] is False


def test_conversation_without_commercial_intent_stays_in_follow_up():
    result = derive_next_best_action(
        _entity(
            current="CONVERSATION",
            ready=True,
            contacted=True,
            engaged=True,
            conversation=True,
            commercial_intent=None,
        )
    )

    assert result["recommended_action"] == "conversation_follow_up"
    assert result["founder_gate_required"] is False
    assert result["commercial_intent_inferred"] is False


def test_commercial_intent_requires_terms_founder_gate():
    result = derive_next_best_action(
        _entity(
            current="COMMERCIAL_INTENT",
            ready=True,
            contacted=True,
            engaged=True,
            conversation=True,
            commercial_intent=True,
            terms=None,
        )
    )

    assert result["recommended_action"] == "terms_candidate"
    assert result["authority"] == "founder_gate"
    assert result["founder_gate_required"] is True
    assert result["mutation_authorized"] is False


def test_terms_require_payment_review_founder_gate():
    result = derive_next_best_action(
        _entity(
            current="TERMS",
            ready=True,
            contacted=True,
            engaged=True,
            conversation=True,
            commercial_intent=True,
            terms=True,
            payment_pending=None,
        )
    )

    assert result["recommended_action"] == "payment_review"
    assert result["founder_gate_required"] is True
    assert result["payment_authorized"] is False


def test_payment_pending_waits_for_external_payment():
    result = derive_next_best_action(
        _entity(
            current="PAYMENT_PENDING",
            ready=True,
            contacted=True,
            engaged=True,
            conversation=True,
            commercial_intent=True,
            terms=True,
            payment_pending=True,
            paid=None,
        )
    )

    assert result["recommended_action"] == "hold"
    assert result["waiting_external"] is True
    assert result["payment_authorized"] is False


def test_paid_requires_fulfilment_review_not_auto_fulfilment():
    result = derive_next_best_action(
        _entity(
            current="PAID",
            ready=True,
            contacted=True,
            engaged=True,
            conversation=True,
            commercial_intent=True,
            terms=True,
            payment_pending=True,
            paid=True,
            fulfilled=None,
        )
    )

    assert result["recommended_action"] == "fulfilment_review"
    assert result["external_execution_authorized"] is False
    assert result["mutation_authorized"] is False


def test_snapshot_preserves_no_execution_authority():
    snapshot = {
        "entities": [
            _entity(),
            _entity(
                name="Colorado's Best Roofing",
                entity_id="entity-colorado",
                current="READY",
                ready=True,
            ),
        ]
    }

    result = build_next_best_action_snapshot(
        snapshot,
        account_contexts=[
            {
                "entity_id": "entity-colorado",
                "decision_maker_verified": False,
            }
        ],
    )

    assert result["action_count"] == 2
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_authorized"] is False
    assert result["payment_authorized"] is False
    assert result["execution_authority"] == "none"

    actions = {
        row["company_name"]: row["recommended_action"]
        for row in result["actions"]
    }
    assert actions["Golden Spike Roofing Inc"] == "research_more"
    assert actions["Colorado's Best Roofing"] == "verify_decision_maker"
