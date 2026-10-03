from datetime import datetime, timedelta, timezone

import pytest

from empire_os.outbound_governor import OutboundGovernorPolicy, evaluate_outbound


def review(**overrides):
    value = {
        "decision": "review",
        "intent_id": "00000000-0000-0000-0000-000000000001",
        "channel": "email",
        "recipient": "buyer@example.com",
        "subject": "Quick question",
        "body_text": (
            "Hello. Worth me sending the outline?\n\n"
            "If you'd rather not hear from me, reply opt out.\n\n"
            "Empire-AI Intelligent Systems\n"
            "31 St Thomas St\nBolton\nBL1 2QR\nUK"
        ),
        "status": "pending_approval",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "actual_revenue": False,
    }
    value.update(overrides)
    return value


def context(**overrides):
    value = {
        "suppressed": False,
        "review_ready": True,
        "outreach_ready": True,
        "bound_to_decision_maker": True,
        "contact_source": "official_site",
        "contact_confidence": 0.75,
        "company_score": 85,
        "provider_ready": True,
    }
    value.update(overrides)
    return value


def test_observe_is_fail_closed_even_when_every_check_passes():
    result = evaluate_outbound(review(), context())
    assert result["decision"] == "READY_FOR_HUMAN_APPROVAL"
    assert result["mutation_authorized"] is False


def test_guarded_execute_can_mark_low_risk_intent_auto_approval_eligible():
    result = evaluate_outbound(
        review(), context(),
        policy=OutboundGovernorPolicy(
            mode="GUARDED_EXECUTE", allow_auto_approval=True
        ),
    )
    assert result["decision"] == "AUTO_APPROVE_ELIGIBLE"
    assert result["mutation_authorized"] is True


def test_approved_intent_can_be_auto_send_without_auto_approval():
    result = evaluate_outbound(
        review(status="approved"), context(),
        policy=OutboundGovernorPolicy(
            mode="GUARDED_EXECUTE",
            allow_auto_approval=False,
            allow_auto_send=True,
        ),
    )
    assert result["decision"] == "AUTO_SEND_ELIGIBLE"


def test_missing_evidence_escalates_instead_of_auto_approving():
    result = evaluate_outbound(
        review(), context(contact_confidence=0.4),
        policy=OutboundGovernorPolicy(
            mode="GUARDED_EXECUTE", allow_auto_approval=True
        ),
    )
    assert result["decision"] == "ESCALATE"
    assert "contact_confidence_below_policy" in result["checks"]["evidence_holds"]


def test_suppression_is_hard_hold():
    result = evaluate_outbound(review(), context(suppressed=True))
    assert result["decision"] == "HOLD"
    assert "recipient_suppressed" in result["checks"]["hard_holds"]


def test_missing_optout_is_repairable_in_assist_mode():
    bad = review(body_text="Hello\n31 St Thomas St\nBolton\nBL1 2QR\nUK")
    result = evaluate_outbound(
        bad, context(), policy=OutboundGovernorPolicy(mode="ASSIST")
    )
    assert result["decision"] == "AUTO_REPAIR"
    assert "missing_visible_opt_out" in result["checks"]["repairable"]


def test_auto_flags_are_rejected_outside_guarded_execute():
    with pytest.raises(ValueError, match="GUARDED_EXECUTE"):
        OutboundGovernorPolicy(mode="OBSERVE", allow_auto_approval=True)
    with pytest.raises(ValueError, match="GUARDED_EXECUTE"):
        OutboundGovernorPolicy(mode="OBSERVE", allow_auto_send=True)


def test_fake_reply_prefix_is_hard_hold():
    result = evaluate_outbound(review(subject="Re: quick question"), context())
    assert result["decision"] == "HOLD"
    assert "deceptive_reply_or_forward_prefix" in result["checks"]["hard_holds"]


def test_deliverability_context_can_hard_hold_provider_policy_mismatch():
    result = evaluate_outbound(
        review(),
        context(
            deliverability={
                "provider_policy_permits_use_case": False,
                "spf_aligned": True,
                "dkim_aligned": True,
                "dmarc_valid": True,
                "tls_ready": True,
                "recipient_verified": True,
                "bounce_rate": 0.01,
                "complaint_rate": 0.0,
                "daily_cap": 30,
                "volume_spike_ratio": 1.0,
            }
        ),
    )
    assert result["decision"] == "HOLD"
    assert "provider_policy_prohibits_use_case" in result["checks"]["hard_holds"]



def test_verified_claim_evidence_does_not_block_green_intent():
    result = evaluate_outbound(
        review(),
        context(
            claim_evidence={
                "claims": [{
                    "text": "Buyer has a current public permit",
                    "kind": "observed_fact",
                    "evidence_ref": "permit:1",
                }],
                "evidence_index": {
                    "permit:1": {
                        "verified": True,
                        "source_kind": "public_record",
                        "canonical": False,
                        "expires_at": "2099-01-01T00:00:00+00:00",
                    }
                },
            }
        ),
    )
    assert result["decision"] == "READY_FOR_HUMAN_APPROVAL"
    assert result["checks"]["claim_evidence"]["decision"] == "VERIFIED"


def test_unsupported_claim_is_hard_hold_at_governor():
    result = evaluate_outbound(
        review(),
        context(
            claim_evidence={
                "claims": [{
                    "text": "Buyer is definitely losing £100k",
                    "kind": "performance_outcome",
                    "evidence_ref": "missing:1",
                }],
                "evidence_index": {},
            }
        ),
    )
    assert result["decision"] == "HOLD"
    assert "claim_evidence_ref_unresolved" in result["checks"]["hard_holds"]


def test_noncanonical_sensitive_claim_is_hard_hold_at_governor():
    result = evaluate_outbound(
        review(),
        context(
            claim_evidence={
                "claims": [{
                    "text": "Price is £5,000 per month",
                    "kind": "pricing",
                    "evidence_ref": "price:1",
                }],
                "evidence_index": {
                    "price:1": {
                        "verified": True,
                        "source_kind": "official_site_current",
                        "canonical": False,
                    }
                },
            }
        ),
    )
    assert result["decision"] == "HOLD"
    assert (
        "sensitive_claim_requires_canonical_evidence"
        in result["checks"]["hard_holds"]
    )
