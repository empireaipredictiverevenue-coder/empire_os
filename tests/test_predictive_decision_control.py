from datetime import datetime, timedelta, timezone

import pytest

from empire_os.predictive_decision_control import (
    ACTION_SNAPSHOT_MAX_AGE,
    REVENUE_PULSE_MAX_AGE,
    MAX_ITEMS,
    build_predictive_decision_control,
)

NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


def _next_best(actions=None, **overrides):
    result = {
        "available": True,
        "schema_version": "empire.next_best_action_snapshot.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "outreach_authorized": False,
        "payment_authorized": False,
        "generated_at": NOW.isoformat(),
        "actions": [] if actions is None else actions,
    }
    result.update(overrides)
    return result


def _queue_item(**overrides):
    result = {
        "entity_id": "entity-a",
        "company_name": "Company A",
        "prospect_id": "prospect-a",
        "current_commercial_state": "READY",
        "recommended_action": "verify_decision_maker",
        "next_reversible_internal_action": "verify_decision_maker",
        "blocker": "decision_maker_identity_unverified",
        "reason": "identity has not been proved",
        "authority": "internal_write",
        "founder_gate_required": False,
        "waiting_external": False,
        "evidence_refs": ["business_entity:entity-a"],
        "external_execution_authorized": False,
        "payment_authorized": False,
    }
    result.update(overrides)
    return result


def _queue(items=None, **overrides):
    result = {
        "schema_version": "empire.revenue_command_queue.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "external_execution_authorized": False,
        "payment_authorized": False,
        "database_mutation_authorized": False,
        "recognized_revenue_cents": 12345,
        "realized_gp_cents": 4000,
        "items": [_queue_item()] if items is None else items,
    }
    result.update(overrides)
    return result


def _executive(actions=None, **overrides):
    result = {
        "available": True,
        "schema_version": "empire.founder.executive_roles_status.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "chief_of_staff": {
            "top_three_review_actions": [] if actions is None else actions,
        },
    }
    result.update(overrides)
    return result


def _pulse():
    return {
        "available": True,
        "schema_version": "empire.revenue-pulse.v3",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "execution_allowed": False,
        "payment_mutation": False,
        "revenue_mutation": False,
        "accounting_mutation": False,
        "generated_at": NOW.isoformat(),
        "recognized_revenue_truth": {
            "recognized_revenue_cents": 12345,
            "realized_gp_cents": 4000,
            "forecast_included_in_truth": False,
        },
    }


def _build(*, queue=None, next_best=None, executive=None, pulse=None, **overrides):
    queue = _queue() if queue is None else queue
    if next_best is None:
        next_best = _next_best(actions=[
            {
                "entity_id": row.get("entity_id"),
                "prospect_id": row.get("prospect_id"),
                "recommended_action": row.get("recommended_action"),
                "current_factual_state": row.get("current_commercial_state"),
            }
            for row in queue.get("items", [])
        ])
    return build_predictive_decision_control(
        queue=queue,
        next_best=next_best,
        executive=_executive() if executive is None else executive,
        revenue_pulse=_pulse() if pulse is None else pulse,
        as_of=NOW,
        **overrides,
    )


def test_fresh_canonical_internal_review_is_ranked_but_never_executed():
    data = _build()
    assert data["status"] == "REVIEW_READY"
    task = data["items"][0]
    assert task["lane"] == "INTERNAL_PREPARATION"
    assert task["can_prepare_internal_work"] is True
    assert task["can_execute"] is False
    assert task["task_id"].startswith("buyer-")
    assert "Company" not in task["task_id"]
    assert data["recognized_revenue_cents"] == 12345
    assert data["realized_gp_cents"] == 4000
    assert data["sources"]["revenue_pulse"] == "FRESH"
    assert data["estimated_revenue_from_scores"] is None
    assert data["task_dispatch_performed"] is False
    assert data["outbound_authorized"] is False
    assert data["payment_authorized"] is False


@pytest.mark.parametrize("delta,status", [
    (ACTION_SNAPSHOT_MAX_AGE + timedelta(seconds=1), "STALE"),
    (-timedelta(seconds=1), "FUTURE_HELD"),
])
def test_stale_and_future_data_cannot_be_prepared(delta, status):
    next_best = _next_best(generated_at=(NOW - delta).isoformat())
    data = _build(next_best=next_best)
    assert data["sources"]["buyer_next_best_action"] == status
    task = data["items"][0]
    assert task["lane"] == "EVIDENCE_HOLD"
    assert task["can_prepare_internal_work"] is False
    assert task["can_execute"] is False


def test_missing_snapshot_leaves_commercial_items_held():
    data = _build(next_best={"available": False})
    assert data["status"] == "EVIDENCE_HOLD"  # No actionable fresh evidence.
    assert data["sources"]["buyer_next_best_action"] == "MISSING"
    assert data["items"][0]["lane"] == "EVIDENCE_HOLD"


def test_untrusted_snapshot_cannot_authorize_internal_preparation():
    data = _build(next_best=_next_best(payment_authorized=True))
    assert data["sources"]["buyer_next_best_action"] == "UNTRUSTED"
    assert data["internal_preparation"] == []


def test_queue_granted_external_execution_is_not_trusted():
    data = _build(queue=_queue(external_execution_authorized=True))
    assert data["priority_count"] == 0
    assert data["sources"]["revenue_command_queue"] == "UNTRUSTED"
    assert data["recognized_revenue_cents"] is None


@pytest.mark.parametrize("changes", [
    {"authority": "observe"},
    {"founder_gate_required": True},
    {"waiting_external": True},
    {"payment_authorized": True},
    {"next_reversible_internal_action": "other"},
    {"external_execution_authorized": True},
    {"entity_id": None, "prospect_id": None},
    {"evidence_refs": []},
])
def test_inconsistent_or_incomplete_internal_action_fails_closed(changes):
    item = _build(queue=_queue(items=[_queue_item(**changes)]))["items"][0]
    assert item["can_prepare_internal_work"] is False
    assert item["can_execute"] is False


def test_founder_gate_is_reported_not_approved():
    action = _queue_item(
        current_commercial_state="TERMS",
        recommended_action="payment_review",
        next_reversible_internal_action=None,
        authority="founder_gate",
        founder_gate_required=True,
    )
    data = _build(queue=_queue(items=[action]))
    assert len(data["founder_decisions"]) == 1
    assert data["founder_decisions"][0]["can_execute"] is False
    assert data["payment_authorized"] is False


def test_external_follow_up_requires_review_and_never_sends():
    action = _queue_item(
        current_commercial_state="CONVERSATION",
        recommended_action="conversation_follow_up",
        next_reversible_internal_action=None,
        authority="governed_external",
    )
    data = _build(queue=_queue(items=[action]))
    assert data["items"][0]["lane"] == "GOVERNED_REVIEW"
    assert data["external_execution_authorized"] is False


def test_unknown_action_is_not_treated_as_new_execution_capability():
    action = _queue_item(recommended_action="send_1000_emails",
                         next_reversible_internal_action="send_1000_emails")
    item = _build(queue=_queue(items=[action]))["items"][0]
    assert item["lane"] == "EVIDENCE_HOLD"
    assert item["can_prepare_internal_work"] is False


def test_duplicate_identity_with_conflicting_actions_is_held():
    item1 = _queue_item()
    item2 = _queue_item(recommended_action="research_more",
                        next_reversible_internal_action="research_more")
    data = _build(queue=_queue(items=[item1, item2]))
    assert data["priority_count"] == 2
    assert all(x["lane"] == "EVIDENCE_HOLD" for x in data["items"])
    assert all(x["hold_or_gate_reason"] == "conflicting_actions_for_entity"
               for x in data["items"])


def test_duplicate_same_action_is_deduplicated_stably():
    data = _build(queue=_queue(items=[_queue_item(), _queue_item()]))
    assert data["priority_count"] == 1
    assert data["total_before_display_cap"] == 1
    assert data["items"][0]["task_id"] == _build()["items"][0]["task_id"]


def test_validated_executive_tasks_can_take_priority_over_low_stage_leads():
    data = _build(executive=_executive(actions=[{
        "owner": "business_development",
        "action": "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY",
        "partner": None,
        "external_action_authorized": False,
    }]))
    assert data["top_three"][0]["recommended_action"] == (
        "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY"
    )
    assert data["top_three"][0]["lane"] == "INTERNAL_REVIEW"
    assert data["top_three"][0]["can_execute"] is False


def test_untrusted_executive_cannot_smuggle_new_actions():
    data = _build(executive=_executive(actions=[
        {"owner": "coo", "action": "DEPLOY_AND_SEND", "external_action_authorized": False},
        {"owner": "coo", "action": "VERIFY_ASTRA_DISPATCHER",
         "external_action_authorized": True},
    ]))
    assert data["priority_count"] == 1


def test_empty_observations_hold_and_unknown_money_remains_unknown():
    data = _build(queue=_queue(items=[], recognized_revenue_cents=None),
                  next_best={"available": False}, executive={"available": False},
                  pulse={"available": False})
    assert data["status"] == "EVIDENCE_HOLD"
    assert data["priority_count"] == 0
    assert data["recognized_revenue_cents"] is None
    assert data["expected_revenue_claimed"] is False


def test_order_and_display_limit_and_unique_department_counts():
    a = _queue_item(entity_id="a", prospect_id="a", company_name="A")
    b = _queue_item(entity_id="b", prospect_id="b", company_name="B")
    data = _build(queue=_queue(items=[a, b]), max_items=1)
    assert data["priority_count"] == 1
    assert data["truncated_count"] == 1
    assert data["department_counts"] == {"sales_research": 1}


@pytest.mark.parametrize("size", [0, -1, MAX_ITEMS + 1, 1.4, True])
def test_unbounded_limits_are_rejected(size):
    with pytest.raises(ValueError):
        _build(max_items=size)


def test_naive_as_of_is_rejected():
    with pytest.raises(ValueError):
        build_predictive_decision_control(
            queue=_queue(), next_best=_next_best(),
            executive=_executive(), as_of=datetime(2026, 10, 18),
        )


def test_spoofed_forecast_cannot_become_recognized_revenue():
    queue = _queue(recognized_revenue_cents=None)
    queue["forecast"] = {"predicted_revenue_cents": 999_999_999}
    data = _build(queue=queue)
    assert data["recognized_revenue_cents"] is None
    assert data["estimated_revenue_from_scores"] is None


def test_buyer_capacity_blocker_becomes_priority_without_founder_manually_routing():
    executive = _executive(
        business_development={
            "downstream_buyer_capacity": {
                "status": "NO_VERIFIED_COMMERCIAL_CAPACITY",
                "specific_buybox_verified": False,
            },
        },
    )
    data = _build(executive=executive)
    assert data["top_three"][0]["recommended_action"] == (
        "VERIFY_DOWNSTREAM_BUYER_TERMS_CAPACITY"
    )
    assert data["top_three"][0]["triage_rank"] == 98
    assert data["top_three"][0]["can_execute"] is False
    assert data["top_three"][0]["reason"].startswith("observed executive blocker:")


def test_executive_health_proactively_identifies_known_failures_only():
    executive = _executive(
        coo={
            "department_cycle": "FAILED",
            "astra_dispatcher": "FAILED",
            "opportunity_proof": "STALE",
            "mailbox_observer": "HEALTHY",
        },
    )
    data = _build(executive=executive)
    actions = {row["recommended_action"] for row in data["items"]}
    assert "RESTORE_VERIFIED_DEPARTMENT_FINALISATION" in actions
    assert "VERIFY_ASTRA_DISPATCHER" in actions
    assert "RESTORE_FRESH_OPPORTUNITY_SOURCE_PROOF" in actions
    assert "RESTORE_FOUNDER_MAILBOX_READ_OBSERVABILITY" not in actions


def test_unverified_pulse_does_not_turn_default_zero_into_revenue_fact():
    pulse = {
        "available": False,
        "schema_version": "empire.revenue-pulse.v3",
        "recognized_revenue_truth": {
            "recognized_revenue_cents": 0,
            "forecast_included_in_truth": False,
        },
    }
    data = _build(queue=_queue(recognized_revenue_cents=0), pulse=pulse)
    assert data["recognized_revenue_cents"] is None
    assert data["sources"]["revenue_pulse"] == "UNAVAILABLE"


def test_revenue_source_mismatch_is_held_unknown():
    pulse = _pulse()
    pulse["recognized_revenue_truth"]["recognized_revenue_cents"] = 9999
    data = _build(pulse=pulse)
    assert data["recognized_revenue_cents"] is None


def test_missing_executive_schema_cannot_promote_health_claims():
    executive = _executive(coo={"department_cycle": "FAILED"})
    executive.pop("schema_version")
    data = _build(executive=executive)
    assert data["priority_count"] == 1
    assert all(x["source"] == "canonical_revenue_command_queue"
               for x in data["items"])


def test_revenue_queue_row_not_in_canonical_nba_is_held():
    good_source = _next_best(actions=[{
        "entity_id": "entity-a",
        "prospect_id": "prospect-a",
        "recommended_action": "research_more",
        "current_factual_state": "READY",
    }])
    data = _build(next_best=good_source)
    assert data["items"][0]["lane"] == "EVIDENCE_HOLD"
    assert data["items"][0]["hold_or_gate_reason"] == (
        "revenue_queue_does_not_match_canonical_nba_snapshot"
    )
    assert data["internal_preparation"] == []


@pytest.mark.parametrize("age,status", [
    (REVENUE_PULSE_MAX_AGE + timedelta(seconds=1), "STALE"),
    (-timedelta(seconds=1), "FUTURE_HELD"),
])
def test_revenue_truth_not_promoted_from_old_or_future_snapshot(age, status):
    pulse = _pulse()
    pulse["generated_at"] = (NOW - age).isoformat()
    data = _build(pulse=pulse)
    assert data["sources"]["revenue_pulse"] == status
    assert data["recognized_revenue_cents"] is None
    assert data["realized_gp_cents"] is None
    assert data["task_dispatch_performed"] is False


@pytest.mark.parametrize("change", [
    {"generated_at": None},
    {"payment_mutation": True},
    {"revenue_mutation": True},
    {"accounting_mutation": True},
    {"execution_allowed": True},
    {"execution_authority": "live"},
])
def test_revenue_pulse_requires_validated_observe_contract(change):
    pulse = _pulse()
    pulse.update(change)
    data = _build(pulse=pulse)
    assert data["sources"]["revenue_pulse"] == "UNTRUSTED"
    assert data["recognized_revenue_cents"] is None
    assert data["realized_gp_cents"] is None


def test_gp_disagreement_is_not_counted_as_realized_profit():
    data = _build(queue=_queue(realized_gp_cents=123))
    assert data["realized_gp_cents"] is None
    assert data["recognized_revenue_cents"] == 12345


def test_missing_gp_is_not_inferred_from_revenue_or_forecasts():
    pulse = _pulse()
    pulse["recognized_revenue_truth"]["realized_gp_cents"] = None
    data = _build(pulse=pulse, queue=_queue(realized_gp_cents=None))
    assert data["realized_gp_cents"] is None
    assert data["recognized_revenue_cents"] == 12345
    assert data["north_star"] == "verified_realized_gross_profit"
