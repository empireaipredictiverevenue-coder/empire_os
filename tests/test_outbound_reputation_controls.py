from empire_os.outbound_remediation_planner import plan_remediation
from empire_os.outbound_reputation_escrow import update_reputation_credit
from empire_os.outbound_verification_depth import verification_plan


def test_remediation_planner_never_authorizes_mutation():
    result = plan_remediation([
        {"kind": "recipient_source_changed", "score": 0.9}
    ])
    assert result["posture"] == "REMEDIATE"
    assert all(task["mutation_authorized"] is False for task in result["tasks"])


def test_reputation_credit_falls_faster_than_it_grows():
    healthy = update_reputation_credit(
        {"credit": 20},
        {"green_window": True, "positive_replies": 1},
    )
    damaged = update_reputation_credit(
        {"credit": healthy["credit"]},
        {"hard_bounces": 1},
    )
    assert healthy["credit"] == 23
    assert damaged["credit"] == 15


def test_complaint_can_quarantine_low_credit_sender():
    result = update_reputation_credit({"credit": 20}, {"complaints": 1})
    assert result["credit"] == 0
    assert result["state"] == "QUARANTINED"


def test_high_value_increases_verification_depth_not_permission():
    result = verification_plan({
        "predicted_value": 20000,
        "contact_confidence": 0.9,
        "historical_domain_bounce_rate": 0.0,
        "catch_all": False,
    })
    assert "manual_or_agentic_identity_crosscheck" in result["checks"]
    assert result["principle"] == "value_increases_verification_depth_not_send_permission"
