import pytest

from empire_os.outbound_governor_executor import (
    OutboundGovernorExecutionError,
    execute_governor_decision,
)


class Rpc:
    def __init__(self):
        self.calls = []

    def __call__(self, name, params):
        self.calls.append((name, params))
        if name == "approve_outbound_intent":
            return {"decision": "approved", "status": "approved", "actual_revenue": False}
        if name == "claim_outbound_send":
            return {
                "decision": "authorized_send",
                "intent_id": "00000000-0000-0000-0000-000000000001",
                "channel": "email",
                "recipient": "buyer@example.com",
                "subject": "Quick question",
                "body_text": (
                    "Hello. Reply opt out. "
                    "31 St Thomas St, Bolton, BL1 2QR, UK"
                ),
                "body_html": None,
                "actual_revenue": False,
            }
        if name == "record_outbound_delivery":
            return {"decision": "recorded", "status": "sent", "actual_revenue": False}
        raise AssertionError(name)


def guarded(action):
    return {
        "decision": action,
        "intent_id": "00000000-0000-0000-0000-000000000001",
        "mode": "GUARDED_EXECUTE",
        "mutation_authorized": True,
    }


def test_executor_rejects_observe_even_if_action_is_forged():
    with pytest.raises(OutboundGovernorExecutionError, match="GUARDED_EXECUTE"):
        execute_governor_decision(
            {**guarded("AUTO_APPROVE_ELIGIBLE"), "mode": "OBSERVE"},
            approver_rpc=Rpc(),
            actor="governor",
        )


def test_auto_approval_uses_only_approver_transport():
    approver = Rpc()
    result = execute_governor_decision(
        guarded("AUTO_APPROVE_ELIGIBLE"),
        approver_rpc=approver,
        actor="outbound_governor",
    )
    assert result["decision"] == "AUTO_APPROVED"
    assert approver.calls[0][0] == "approve_outbound_intent"


def test_non_executable_action_is_rejected():
    with pytest.raises(OutboundGovernorExecutionError, match="non-executable"):
        execute_governor_decision(
            guarded("READY_FOR_SEND_GATE"),
            actor="outbound_governor",
        )


def test_auto_send_claims_validates_sends_and_records():
    class Emails:
        @staticmethod
        def send(payload, options=None):
            assert payload["to"] == ["buyer@example.com"]
            assert options["idempotency_key"].startswith("outbound/")
            return {"id": "em_governor_1"}

    class FakeResend:
        api_key = None

    FakeResend.Emails = Emails
    sender_rpc = Rpc()
    result = execute_governor_decision(
        guarded("AUTO_SEND_ELIGIBLE"),
        sender_rpc=sender_rpc,
        actor="outbound_governor",
        sender="Phil - Founder - Empire AI <founder@empire-ai.co.uk>",
        reply_to="reply@mail.empire-ai.co.uk",
        resend_api_key="re_test",
        resend_module=FakeResend,
    )
    assert result["decision"] == "AUTO_SENT"
    assert [name for name, _ in sender_rpc.calls] == [
        "claim_outbound_send", "record_outbound_delivery"
    ]
