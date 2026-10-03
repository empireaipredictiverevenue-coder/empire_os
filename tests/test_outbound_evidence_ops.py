from empire_os.outbound_evidence_normalizer import normalize_evidence
from empire_os.outbound_failover_drill import plan_failover_drill, evaluate_failover_drill
from empire_os.outbound_founder_alerts import build_founder_alert


def test_normalizer_maps_resend_to_canonical_metrics():
    rows = normalize_evidence("resend", {
        "observed_at": "2026-10-03T12:00:00Z",
        "domain": "mail.example.com",
        "sent": 10,
        "delivered": 9,
        "bounced": 1,
    })
    names = {row["metric_name"] for row in rows}
    assert names == {"sent", "delivered", "bounced"}


def test_failover_drill_is_seed_only_and_never_auto_switches():
    plan = plan_failover_drill(
        [
            {"transport": "a", "enabled": True, "provider_policy_compatible": True, "auth_ready": True},
            {"transport": "b", "enabled": True, "provider_policy_compatible": True, "auth_ready": True},
        ],
        [{"recipient_key": "seed:gmail:1", "recipient_class": "empire_seed"}],
    )
    assert plan["posture"] == "READY_FOR_CONTROLLED_TEST"
    assert all(row["recipient_class"] == "empire_seed" for row in plan["assignments"])

    result = evaluate_failover_drill([
        {
            "transport": "a",
            "recipient_class": "empire_seed",
            "provider_policy_compatible": True,
            "placement": "inbox",
            "latency_ms": 100,
        },
        {
            "transport": "b",
            "recipient_class": "empire_seed",
            "provider_policy_compatible": True,
            "placement": "spam",
            "latency_ms": 100,
        },
    ])
    assert result["preferred_transport"] == "a"
    assert result["automatic_transport_switch"] is False


def test_founder_alert_dedupes_by_stable_fingerprint():
    snapshot = {
        "posture": "HOLD",
        "hard_holds": ["bounce_rate_red"],
        "tasks": [{"action": "STOP_SEND"}],
    }
    one = build_founder_alert(snapshot)
    two = build_founder_alert(snapshot)
    assert one["severity"] == "CRITICAL"
    assert one["fingerprint"] == two["fingerprint"]


def test_no_alert_for_clean_ready_state():
    assert build_founder_alert({"posture": "READY", "hard_holds": []}) is None


def test_normalizer_maps_arf_complaint_to_canonical_complaint_metric():
    rows = normalize_evidence("arf", {
        "observed_at": "2026-10-03T12:00:00Z",
        "domain": "mail.example.com",
        "complaint": True,
        "feedback_type": "abuse",
    })
    values = {row["metric_name"]: row["metric_value"] for row in rows}
    assert values["complained"] == 1
    assert values["arf_report"] == 1
