"""Commercial-fit holds must stop duplicate outreach before delivery."""
import json
from datetime import datetime, timezone, timedelta
import pytest
from empire_os.commercial_outbound_holds import (
    commercial_outbound_hold, require_no_commercial_hold, CommercialOutboundHoldError,
)
from empire_os.outbound_governor import evaluate_outbound, OutboundGovernorPolicy
from empire_os.outbound_provider import build_resend_send, OutboundProviderError

def fixture(tmp_path):
    p=tmp_path/"private.json"
    p.write_text(json.dumps({
        "schema_version":"empire.commercial_relationship_registry.v1",
        "execution_authority":"NONE","outbound_authorized":False,
        "new_engaged_publisher_supply_review_queue":[{
            "domain":"roofpitch.net","role_hypothesis":"TRAFFIC_SUPPLY_HYPOTHESIS_NOT_VERIFIED",
            "last_reply_id":"1a1286f08693e96d",
            "next_action":"HOLD_PERFORMANCE_PARTNERSHIP_NO_REPEAT_EMAIL",
            "reported_constraint":"SPONSORED_PLACEMENTS_ONLY_REPORTED",
            "outbound_authorized":False,"execution_authority":"NONE",
        }],
    }))
    p.chmod(0o600)
    return p

def test_exact_domain_has_provenanced_block(tmp_path):
    path=fixture(tmp_path)
    r=commercial_outbound_hold("contact@roofpitch.net",path=path)
    assert r["blocked"] and r["evidence_ref"]=="gmail:1a1286f08693e96d"
    assert not commercial_outbound_hold("contact@example.com",path=path)["blocked"]
    with pytest.raises(CommercialOutboundHoldError,match="commercial_fit_no_repeat_outbound"):
        require_no_commercial_hold("partners@roofpitch.net",path=path)

def test_missing_corrupt_or_unreadable_registry_fails_closed(tmp_path):
    path=fixture(tmp_path)
    path.chmod(0o644)
    with pytest.raises(CommercialOutboundHoldError):
        require_no_commercial_hold("buyer@example.com",path=path)
    path.chmod(0o600)
    path.write_text("{not-json")
    with pytest.raises(CommercialOutboundHoldError):
        require_no_commercial_hold("buyer@example.com",path=path)
    path.unlink()
    with pytest.raises(CommercialOutboundHoldError):
        require_no_commercial_hold("buyer@example.com",path=path)

def test_governor_even_approved_intent_holds_responded_domain(monkeypatch,tmp_path):
    import empire_os.outbound_governor as mod
    path=fixture(tmp_path)
    monkeypatch.setattr(mod,"commercial_outbound_hold",
        lambda to: commercial_outbound_hold(to,path=path))
    review={
        "intent_id":"11111111-1111-4111-8111-111111111111",
        "channel":"email","recipient":"contact@roofpitch.net",
        "status":"approved","actual_revenue":False,"subject":"Hi",
        "expires_at":(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
        "body_text":"Partnership. Opt out. 68 Wentbridge Road, Bolton, BL1 2QR, UK",
    }
    context={"suppressed":False,"review_ready":True,"outreach_ready":True,
        "bound_to_decision_maker":True,"contact_source":"official_site",
        "contact_confidence":.99,"company_score":99,"provider_ready":True}
    policy=OutboundGovernorPolicy(mode="GUARDED_EXECUTE",allow_auto_send=True)
    result=evaluate_outbound(review,context,policy=policy)
    assert result["decision"]=="HOLD" and not result["mutation_authorized"]
    assert "commercial_fit_no_repeat_outbound" in result["checks"]["hard_holds"]
    review["recipient"]="buyer@example.com"
    assert evaluate_outbound(review,context,policy=policy)["decision"]=="AUTO_SEND_ELIGIBLE"


def test_database_send_claim_fails_before_provider_payload(monkeypatch,tmp_path):
    import empire_os.outbound_provider as provider
    path=fixture(tmp_path)
    monkeypatch.setattr(provider,"require_no_commercial_hold",
        lambda to: require_no_commercial_hold(to,path=path))
    claim={
        "decision":"authorized_send","actual_revenue":False,
        "intent_id":"11111111-1111-4111-8111-111111111111",
        "channel":"email","recipient":"contact@roofpitch.net","subject":"Hi",
        "body_text":"Partnership. Opt out. 68 Wentbridge Road, Bolton, BL1 2QR, UK",
    }
    with pytest.raises(OutboundProviderError,match="commercial_fit_outbound_held"):
        build_resend_send(claim,sender="Founder <founder@empire-ai.co.uk>",
                         reply_to="reply@mail.empire-ai.co.uk")


def test_direct_postal_provider_never_attempts_network_on_commercial_hold(monkeypatch,tmp_path):
    import empire_os.outbound_email_transport as senders
    path=fixture(tmp_path)
    monkeypatch.setattr(senders,"require_no_commercial_hold",
        lambda to: require_no_commercial_hold(to,path=path))
    attempts=[]
    def opener(*args,**kwargs):
        attempts.append(1)
        raise AssertionError("must never send")
    transport=senders.PostalEmailTransport(
        base_url="https://postal.example.com",api_key="test-only",opener=opener)
    with pytest.raises(OutboundProviderError,match="commercial_fit_outbound_held"):
        transport.send({
            "from":"Founder <founder@empire-ai.co.uk>",
            "to":["contact@roofpitch.net"],
            "reply_to":["reply@mail.empire-ai.co.uk"],
            "subject":"Hi","text":"Body",
            "_sender_address":"founder@empire-ai.co.uk",
            "_idempotency_key":"outbound/test",
        })
    assert attempts==[]


def test_gmail_transport_final_check_catches_hold_after_payload_build(monkeypatch,tmp_path):
    import empire_os.outbound_provider as builder
    import empire_os.commercial_outbound_holds as holds
    from empire_os.gmail_api_transport import send_with_gmail_api
    path=fixture(tmp_path)
    monkeypatch.setattr(builder,"require_no_commercial_hold",lambda to: None)
    monkeypatch.setattr(holds,"require_no_commercial_hold",
        lambda to: require_no_commercial_hold(to,path=path))
    class NoSend:
        def users(self):return self
        def messages(self):return self
        def send(self,**kwargs):raise AssertionError("must never send")
    with pytest.raises(OutboundProviderError,match="commercial_fit_outbound_held"):
        send_with_gmail_api({
            "decision":"authorized_send","actual_revenue":False,
            "intent_id":"11111111-1111-4111-8111-111111111111",
            "channel":"email","recipient":"contact@roofpitch.net",
            "subject":"Hi","body_text":
                "Partnership. Opt out. 68 Wentbridge Road, Bolton, BL1 2QR, UK",
        },sender="Founder <founder@empire-ai.co.uk>",
          reply_to="reply@mail.empire-ai.co.uk",service=NoSend())
