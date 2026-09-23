from empire_os.revenue_command_queue import (
    build_revenue_command_queue,
)


def _action(
    *,
    company,
    entity,
    prospect,
    state,
    action,
    authority,
    reason,
    founder_gate=False,
    waiting_external=False,
):
    return {
        "entity_id": entity,
        "company_name": company,
        "prospect_id": prospect,
        "current_factual_state": state,
        "recommended_action": action,
        "reason": reason,
        "authority": authority,
        "founder_gate_required": founder_gate,
        "waiting_external": waiting_external,
        "evidence": {},
    }


def test_command_queue_reuses_canonical_next_best_actions():
    queue = build_revenue_command_queue(
        next_best_actions={
            "available": True,
            "actions": [
                _action(
                    company="Buyer One",
                    entity="entity-1",
                    prospect="prospect-1",
                    state="READY",
                    action="verify_decision_maker",
                    authority="internal_write",
                    reason="decision-maker identity is not verified",
                ),
                _action(
                    company="Buyer Two",
                    entity="entity-2",
                    prospect="prospect-2",
                    state="TERMS",
                    action="payment_review",
                    authority="founder_gate",
                    reason="payment request authority is gated",
                    founder_gate=True,
                ),
            ],
        },
        commercial_funnel={
            "available": True,
            "current_stage": "buyer_conversation",
            "next_event": "open_or_advance_closer",
        },
        revenue_pulse={
            "available": True,
            "highest_priority_blocker": "buyer_conversation",
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
            },
        },
    )

    assert queue["schema_version"] == "empire.revenue_command_queue.v1"
    assert queue["current_commercial_stage"] == "buyer_conversation"
    assert queue["highest_priority_blocker"] == "buyer_conversation"
    assert queue["item_count"] == 2
    assert queue["reversible_internal_count"] == 1
    assert queue["founder_gate_count"] == 1
    assert queue["recognized_revenue_cents"] == 0

    # Later observed commercial states are surfaced first.
    assert queue["items"][0]["company_name"] == "Buyer Two"
    assert queue["items"][0]["blocker"] == "payment_request_authority_gated"
    assert queue["items"][0]["next_reversible_internal_action"] is None

    internal = queue["items"][1]
    assert internal["recommended_action"] == "verify_decision_maker"
    assert internal["next_reversible_internal_action"] == "verify_decision_maker"
    assert internal["blocker"] == "decision_maker_identity_unverified"
    assert internal["evidence_refs"] == [
        "business_entity:entity-1",
        "prospect:prospect-1",
    ]


def test_unknown_offer_remains_unknown():
    queue = build_revenue_command_queue(
        next_best_actions={
            "actions": [
                _action(
                    company="Buyer One",
                    entity="entity-1",
                    prospect="prospect-1",
                    state="RESEARCHED",
                    action="research_more",
                    authority="internal_write",
                    reason="readiness not established",
                )
            ]
        },
        commercial_funnel={},
        revenue_pulse={},
    )

    item = queue["items"][0]
    assert item["product_code"] is None
    assert item["offer_known"] is False
    assert queue["unknown_stays_unknown"] is True


def test_waiting_external_is_not_promoted_into_internal_execution():
    queue = build_revenue_command_queue(
        next_best_actions={
            "actions": [
                _action(
                    company="Buyer One",
                    entity="entity-1",
                    prospect="prospect-1",
                    state="CONTACTED",
                    action="hold",
                    authority="observe",
                    reason="waiting for engagement",
                    waiting_external=True,
                )
            ]
        },
        commercial_funnel={
            "current_stage": "outbound_delivered",
            "next_event": "await_genuine_buyer_reply",
        },
        revenue_pulse={},
    )

    item = queue["items"][0]
    assert item["waiting_external"] is True
    assert item["next_reversible_internal_action"] is None
    assert item["blocker"] == "external_event_pending"
    assert queue["external_execution_authorized"] is False
    assert queue["payment_authorized"] is False
    assert queue["database_mutation_authorized"] is False


def test_forecast_is_never_used_as_revenue_truth():
    queue = build_revenue_command_queue(
        next_best_actions={"actions": []},
        commercial_funnel={"current_stage": "acquisition"},
        revenue_pulse={
            "forecast": {
                "items": [
                    {"forecast_revenue_cents": 999999}
                ]
            },
            "recognized_revenue_truth": {
                "recognized_revenue_cents": 0,
                "realized_gp_cents": 0,
            },
        },
    )

    assert queue["recognized_revenue_cents"] == 0
    assert queue["forecast_used_as_revenue_truth"] is False
    assert queue["actual_revenue_inferred"] is False
