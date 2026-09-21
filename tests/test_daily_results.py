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
