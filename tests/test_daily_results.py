import json
from datetime import datetime, timezone

from empire_os.daily_results import build_daily_results


def dump(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_daily_results_keeps_commercial_truth_separate(tmp_path):
    runtime = tmp_path / "runtime"
    dump(runtime / "commercial_loop/latest.json", {
        "loop_complete": False,
        "stages": [
            {"stage": "omega_projection", "observed": True, "detail": "53 Omega observations"},
            {"stage": "buyer_candidate_approved", "observed": True, "detail": "15 approved buyers"},
            {"stage": "outbound_sent", "observed": True, "detail": "15 sent"},
            {"stage": "buyer_conversation", "observed": False, "detail": "0 commercial buyer replies"},
            {"stage": "recognized_revenue", "observed": False, "detail": "0 recognized revenue events"},
        ],
    })
    dump(runtime / "ops_control/latest.json", {
        "healthy": True,
        "conveyor": {
            "current_blocker": "buyer_conversation",
            "owner_component": "conversation_os",
            "authority": "internal_write",
        },
    })
    payload = build_daily_results(
        tmp_path,
        now=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc),
    )
    assert payload["commercial_funnel"]["omega_observations"] == 53
    assert payload["commercial_funnel"]["approved_buyers"] == 15
    assert payload["commercial_funnel"]["commercial_buyer_replies"] == 0
    assert payload["commercial_funnel"]["recognized_revenue_events"] == 0
    assert payload["headline"]["commercial_blocker"] == "buyer_conversation"
    assert payload["controls_execution"] is False


def test_missing_metrics_stay_none(tmp_path):
    payload = build_daily_results(tmp_path)
    assert payload["commercial_funnel"]["verified_payments"] is None
    assert payload["acquisition"]["accepted"] is None


def test_daily_results_surfaces_rls_classification_counts(tmp_path):
    runtime = tmp_path / "runtime"
    dump(runtime / "security/rls_classification_latest.json", {
        "table_count": 222,
        "counts": {
            "privileged_operator": 33,
            "tenant_owned_candidate": 14,
            "public_read_candidate": 11,
            "server_only_review": 164,
        },
    })
    payload = build_daily_results(tmp_path)
    assert payload["security"]["rls_classification_available"] is True
    assert payload["security"]["rls_table_count"] == 222
    assert payload["security"]["rls_classes"]["privileged_operator"] == 33


def test_daily_results_surfaces_revenue_pulse_and_control_fabric(tmp_path):
    runtime = tmp_path / "runtime"
    dump(runtime / "revenue_pulse/latest.json", {
        "pulse_state": "conversation_blocked",
        "highest_priority_blocker": "buyer_conversation",
        "current_window": {
            "acquisitions": 306,
            "qualified": 109,
            "buyer_reviews": 16,
            "delivered_outreach": 16,
            "commercial_replies": 0,
            "recognized_revenue_cents": 0,
            "realized_gp_cents": 0,
        },
        "conversion": {
            "delivered_outreach_to_commercial_reply": 0.0,
        },
        "recognized_revenue_truth": {
            "recognized_revenue_cents": 0,
            "realized_gp_cents": 0,
            "forecast_included_in_truth": False,
        },
        "forecast": {
            "separate_from_revenue_truth": True,
            "items": [],
        },
    })
    dump(runtime / "control_fabric/latest.json", {
        "component_count": 16,
        "authority_counts": {
            "observe": 3,
            "internal_write": 10,
            "governed_external": 2,
            "founder_gate": 1,
        },
        "external_execution_enabled": False,
        "founder_gates_preserved": True,
    })
    payload = build_daily_results(tmp_path)
    assert payload["revenue_pulse"]["available"] is True
    assert payload["revenue_pulse"]["pulse_state"] == "conversation_blocked"
    assert payload["revenue_pulse"]["current_window"]["acquisitions"] == 306
    assert payload["revenue_pulse"]["current_window"]["commercial_replies"] == 0
    assert payload["revenue_pulse"]["recognized_revenue_truth"][
        "forecast_included_in_truth"
    ] is False
    assert payload["control_fabric"]["available"] is True
    assert payload["control_fabric"]["component_count"] == 16
    assert payload["control_fabric"]["external_execution_enabled"] is False


def test_daily_results_surfaces_conversation_recovery_gap(tmp_path):
    runtime = tmp_path / "runtime"
    dump(runtime / "revenue_pulse/latest.json", {
        "current_window": {"delivered_outreach": 16},
    })
    dump(runtime / "conversation_recovery/latest.json", {
        "delivered_first_touches": 16,
        "followup_eligible_delivered": 15,
        "suppressed_after_delivery": 1,
        "due_now": 0,
        "due_within_24h": 0,
        "recoverable": 15,
        "blocked_missing_context": 0,
        "legacy_generic_subjects": 15,
        "next_due_in_hours": 52.5,
        "send_executed": False,
        "proposal_created": False,
    })
    payload = build_daily_results(tmp_path)
    recovery = payload["conversation_recovery"]
    assert recovery["available"] is True
    assert recovery["recoverable"] == 15
    assert recovery["followup_eligible_delivered"] == 15
    assert recovery["suppressed_after_delivery"] == 1
    assert recovery["pulse_delivery_gap"] == 0
    assert recovery["send_executed"] is False


def test_daily_results_surfaces_buyer_capacity_truth(tmp_path):
    runtime = tmp_path / "runtime"
    dump(runtime / "buyer_capacity/latest.json", {
        "buyers_seen": 1057,
        "status_active": 169,
        "is_active_true": 168,
        "commercially_activated": 0,
        "reviewed": 1,
        "terms_verified": 0,
        "capacity_verified": 0,
        "delivery_verified": 0,
        "fully_activated": 0,
        "highest_priority_blocker": "verified_commercial_terms",
        "allocation_ready": False,
        "activation_blockers": {
            "buyer_inactive": 889,
            "buyer_not_commercially_activated": 168,
        },
    })
    payload = build_daily_results(tmp_path)
    buyer = payload["buyer_capacity"]
    assert buyer["available"] is True
    assert buyer["buyers_seen"] == 1057
    assert buyer["status_active"] == 169
    assert buyer["terms_verified"] == 0
    assert buyer["capacity_verified"] == 0
    assert buyer["delivery_verified"] == 0
    assert buyer["fully_activated"] == 0
    assert buyer["highest_priority_blocker"] == "verified_commercial_terms"
    assert buyer["allocation_ready"] is False
