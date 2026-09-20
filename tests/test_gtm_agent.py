from datetime import datetime, timezone

from empire_os.gtm_agent import decide_next_gtm_action
from empire_os.gtm_agent_policy import GTMStandingAuthority


NOW = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)


def standing():
    return GTMStandingAuthority(
        authority_id="gtm-standing-1",
        approved_by="founder",
        approved_at="2026-09-20T12:00:00Z",
        expires_at="2026-09-21T12:00:00Z",
        capabilities=(
            "outreach.approve",
            "outreach.send",
            "buyer.activate",
            "inventory.allocate",
            "payment_request.issue",
            "fulfilment.execute",
        ),
        channels=("email", "voice"),
        offer_keys=("managed_service",),
        daily_external_action_cap=25,
    )


def test_internal_blocker_runs_without_founder_approval():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": "qualification_v2",
            "loop_complete": False,
        },
        now=NOW,
    )

    assert decision.next_action == "qualification.run"
    assert decision.action_review.permitted is True
    assert decision.action_review.requires_founder_approval is False


def test_current_unsent_outbound_blocker_uses_standing_authority():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": "outbound_sent",
            "loop_complete": False,
        },
        now=NOW,
        standing_authority=standing(),
        action_context={
            "channel": "email",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
        external_actions_used_today=3,
    )

    assert decision.next_action == "outreach.send"
    assert decision.action_review.permitted is True
    assert decision.action_review.standing_authority_used is True
    assert decision.execution_performed is False


def test_unsent_outbound_without_standing_authority_escalates():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": "outbound_sent",
            "loop_complete": False,
        },
        now=NOW,
        action_context={
            "channel": "email",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert decision.next_action == "outreach.send"
    assert decision.action_review.permitted is False
    assert decision.action_review.requires_founder_approval is True


def test_revenue_recognition_remains_hard_founder_gate():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": "recognized_revenue",
            "loop_complete": False,
        },
        now=NOW,
        standing_authority=standing(),
        action_context={
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert decision.next_action == "revenue.recognize"
    assert decision.action_review.permitted is False
    assert decision.action_review.requires_founder_approval is True
    assert decision.action_review.blockers == ("founder_gate_required",)


def test_complete_loop_has_no_next_action():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": None,
            "loop_complete": True,
        },
        now=NOW,
    )

    assert decision.next_action is None
    assert decision.action_review is None


def test_current_specific_outbound_approval_does_not_reask_founder():
    decision = decide_next_gtm_action(
        {
            "highest_priority_blocker": "outbound_sent",
            "loop_complete": False,
        },
        now=NOW,
        action_context={
            "specific_approval_present": True,
            "specific_approval_ref": "outbound_intent:a530c17a",
            "channel": "email",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert decision.next_action == "outreach.send"
    assert decision.action_review.permitted is True
    assert decision.action_review.requires_founder_approval is False
    assert decision.action_review.authority_id == "outbound_intent:a530c17a"
