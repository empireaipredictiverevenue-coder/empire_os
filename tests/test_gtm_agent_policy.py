from datetime import datetime, timezone

import pytest

from empire_os.gtm_agent_policy import (
    GTMAuthorityLane,
    GTMStandingAuthority,
    authority_lane,
    review_gtm_action,
)


NOW = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)


def grant(**overrides):
    data = {
        "authority_id": "gtm-standing-1",
        "approved_by": "founder",
        "approved_at": "2026-09-20T12:00:00Z",
        "expires_at": "2026-09-21T12:00:00Z",
        "capabilities": (
            "outreach.send",
            "voice.call",
            "inventory.allocate",
        ),
        "channels": ("email", "voice"),
        "offer_keys": ("managed_service",),
        "daily_external_action_cap": 25,
        "enabled": True,
    }
    data.update(overrides)
    return GTMStandingAuthority(**data)


@pytest.mark.parametrize(
    "action",
    [
        "evidence.read",
        "acquisition.run",
        "enrichment.run",
        "qualification.run",
        "omega.score",
        "buyer.discovery",
        "buyer.readiness.observe",
        "gtm.plan",
        "gtm.publish_internal_jobs",
        "content.draft",
        "commercial_loop.observe",
    ],
)
def test_internal_gtm_actions_are_auto_without_per_action_approval(action):
    result = review_gtm_action(action, now=NOW)

    assert result.lane is GTMAuthorityLane.AUTO
    assert result.permitted is True
    assert result.requires_founder_approval is False
    assert result.standing_authority_used is False


def test_outbound_can_run_under_one_scoped_standing_authority():
    result = review_gtm_action(
        "outreach.send",
        now=NOW,
        standing_authority=grant(),
        context={
            "channel": "email",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
        external_actions_used_today=8,
    )

    assert result.lane is GTMAuthorityLane.STANDING_AUTHORITY
    assert result.permitted is True
    assert result.requires_founder_approval is False
    assert result.authority_id == "gtm-standing-1"


def test_standing_authority_fails_closed_outside_scope():
    result = review_gtm_action(
        "outreach.send",
        now=NOW,
        standing_authority=grant(),
        context={
            "channel": "sms",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert result.permitted is False
    assert result.requires_founder_approval is True
    assert "channel_outside_standing_authority" in result.blockers


def test_standing_authority_never_overrides_evidence_or_compliance():
    result = review_gtm_action(
        "outreach.send",
        now=NOW,
        standing_authority=grant(),
        context={
            "channel": "email",
            "offer_key": "managed_service",
            "evidence_ready": False,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert result.permitted is False
    assert "evidence_not_ready" in result.blockers


def test_daily_cap_prevents_unbounded_external_execution():
    result = review_gtm_action(
        "voice.call",
        now=NOW,
        standing_authority=grant(),
        context={
            "channel": "voice",
            "offer_key": "managed_service",
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
        external_actions_used_today=25,
    )

    assert result.permitted is False
    assert "external_action_cap_reached" in result.blockers


@pytest.mark.parametrize(
    "action",
    [
        "commercial_terms.accept",
        "contract.accept",
        "payment.move",
        "revenue.recognize",
        "infrastructure.change",
        "model.promote",
        "authority.expand",
        "unknown.action",
    ],
)
def test_hard_gates_never_gain_authority_from_standing_grant(action):
    result = review_gtm_action(
        action,
        now=NOW,
        standing_authority=grant(
            capabilities=("outreach.send", action),
        ),
        context={
            "evidence_ready": True,
            "compliance_ready": True,
            "governor_ready": True,
        },
    )

    assert authority_lane(action) is GTMAuthorityLane.FOUNDER_GATE
    assert result.permitted is False
    assert result.requires_founder_approval is True
    assert result.blockers == ("founder_gate_required",)
