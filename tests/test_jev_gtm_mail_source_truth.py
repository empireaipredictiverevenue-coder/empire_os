"""Read-only JEV mail ingress truth is not original-provider authentication."""
from datetime import datetime, timezone
import json

import pytest

from empire_os.jev_gtm_mail_source_truth import assess_jev_ingress_truth
from scripts import probe_jev_mail_ingress_source_truth as probe

NOW = datetime(2026,10,14,11,tzinfo=timezone.utc)
RELAY = {
    "ok": True, "provider": "gmail_api", "mode": "OBSERVE",
    "send_authorized": False, "mutation_authorized": False,
    "sender": "SECRET-SHOULD-NOT-BE-IN-OUTPUT",
}
FOUNDER = {"provider": "owned_imap", "configured": False,
           "status": "NOT_CONFIGURED", "execution_authority": "none"}
INBOUND = {"ok": True, "provider": "resend", "mode": "OBSERVE",
           "reply_transport_configured": True,
           "provider_private_data": "SECRET-SHOULD-NOT-BE-IN-OUTPUT"}


def assess(**diff):
    values = {
        "relay_health": RELAY, "founder_readiness": FOUNDER,
        "inbound_health": INBOUND, "root_mx": ["1 smtp.google.com."],
        "reply_mx": ["10 inbound-smtp.us-east-1.amazonaws.com."],
        "canonical_release_dropin_present": False,
        "canonical_reader_credential_present": False,
        "observed_at": NOW,
    }
    values.update(diff)
    return assess_jev_ingress_truth(**values)


def test_observed_mail_mismatch_holds_first_party_buyer_promotion():
    status = assess()
    assert status["status"] == "HOLD_FIRST_PARTY_REPLY_ACTIVATION"
    assert status["reply_mx_external_ses_observed"] is True
    assert status["resend_webhook_reported_active"] is True
    assert status["source_provider_mismatch_observed"] is True
    assert status["gmail_relay_send_disabled"] is True
    assert status["canonical_reply_view_live"] is False
    assert status["signed_first_party_ingress_producer_present"] is None
    assert status["first_party_inbound_transport_verified"] is False
    assert status["independently_verified_buyer_replies"] is None
    assert status["verified_commercial_revenue"] is None
    assert status["outbound_authorized"] is False
    assert status["mail_sent"] is False
    assert status["database_reads"] is False
    for reason in (
        "REPLY_MX_POINTS_TO_EXTERNAL_SES",
        "ACTIVE_RESEND_INBOUND_SERVICE",
        "REPLY_MX_AND_WEBHOOK_PROVIDER_UNRECONCILED",
        "CANONICAL_FOUNDER_REPLY_VIEW_NOT_LIVE",
        "OWNED_IMAP_READER_NOT_CONFIGURED",
        "FIRST_PARTY_INBOUND_TRANSPORT_OWNER_NOT_AUDITED",
        "CONSENT_AND_SUPPRESSION_CLEARANCE_NOT_VERIFIED",
    ):
        assert reason in status["blocked_reasons"]
    assert "SECRET-SHOULD-NOT-BE-IN-OUTPUT" not in json.dumps(status)


def test_even_canonical_reply_view_running_is_not_buyer_authentication():
    status = assess(
        founder_readiness={
            "provider":"empiredb_canonical_replies", "configured":True,
            "read_only":True,"execution_authority":"none",
        },
        canonical_reader_credential_present=True,
        canonical_release_dropin_present=True,
        inbound_health={"ok": True,"provider":"owned_ingress",
                        "reply_transport_configured":True},
        reply_mx=["10 mx.empire-ai.co.uk."],
    )
    assert status["canonical_reply_view_live"] is True
    assert status["reply_mx_external_ses_observed"] is False
    assert status["source_provider_mismatch_observed"] is False
    assert status["first_party_inbound_transport_verified"] is False
    assert status["original_provider_receipt_identity_verified"] is False
    assert status["independently_verified_buyer_replies"] is None
    assert status["status"] == "HOLD_FIRST_PARTY_REPLY_ACTIVATION"


def test_missing_dns_and_provider_evidence_are_unknown_not_negative_counts():
    status = assess(
        root_mx=[],reply_mx=[], relay_health=None,
        founder_readiness=None,inbound_health=None,
        canonical_release_dropin_present=None,
        canonical_reader_credential_present=None,
        probe_errors=["relay","inbound","reply_mx"],
    )
    assert status["reply_domain_mx_observed"] is None
    assert status["reply_mx_external_ses_observed"] is None
    assert status["resend_webhook_reported_active"] is None
    assert status["canonical_reply_view_live"] is None
    assert status["source_provider_mismatch_observed"] is False
    assert "REPLY_DOMAIN_MX_NOT_VERIFIED" in status["blocked_reasons"]
    assert "REQUIRED_READONLY_EVIDENCE_PROBE_UNAVAILABLE" in status["blocked_reasons"]
    assert status["independently_verified_buyer_replies"] is None


def test_unverified_gmail_relay_sending_mode_never_grants_send_authority():
    status = assess(relay_health={
        "provider":"gmail_api","ok":True,
        "mode":"GUARDED_EXECUTE","send_authorized":True,
        "mutation_authorized":True,
    })
    assert status["gmail_relay_send_disabled"] is False
    assert "OBSERVE_ONLY_RELAY_INVARIANT_UNVERIFIED" in status["blocked_reasons"]
    assert status["outbound_authorized"] is False


@pytest.mark.parametrize("bad",[
    ["smtp.google.com."],["not-an-mx"], ["10 dangerous host.com"],
    ["-1 smtp.google.com"],[None], [1], [""],
])
def test_malformed_dns_cannot_overwrite_observation(bad):
    with pytest.raises(ValueError):
        assess(reply_mx=bad)


def test_bounded_dns_inputs_reject_dos():
    with pytest.raises(ValueError,match="bounded"):
        assess(reply_mx=["1 smtp.google.com."]*21)


def test_unknown_ingress_webhook_not_trusted_as_first_party():
    status = assess(inbound_health={
        "provider":"firstparty","ok":True,"reply_transport_configured":True
    })
    assert status["resend_webhook_reported_active"] is False
    assert status["signed_first_party_ingress_producer_present"] is None
    assert status["first_party_inbound_transport_verified"] is False


def test_degraded_canonical_provider_missing_read_only_is_not_ready():
    status = assess(founder_readiness={
        "provider":"empiredb_canonical_replies","configured":True,
        "execution_authority":"none",
    },canonical_release_dropin_present=True,
    canonical_reader_credential_present=True)
    assert status["canonical_reply_view_live"] is False


def test_no_io_default_diagnostic_does_not_probe_network(monkeypatch,capsys):
    monkeypatch.setattr(probe,"inspect_public_route",
        lambda **kw: pytest.fail("default must not probe"))
    assert probe.main([])==0
    output=json.loads(capsys.readouterr().out)
    assert output["status"]=="LIVE_READONLY_NOT_REQUESTED"
    assert output["network_calls"]==0
    assert output["execution_authority"]=="none"


def test_live_probe_reuses_existing_founder_mail_helpers_and_no_secrets():
    invoked=[]
    def http(port,path):
        invoked.append(("http",port,path))
        return {
            8775:RELAY,
            8766:FOUNDER,
            8097:INBOUND,
        }[port]
    def dns(kind,name):
        invoked.append(("dns",kind,name))
        assert kind=="MX"
        return ["1 smtp.google.com."] if name=="empire-ai.co.uk" else [
            "10 inbound-smtp.us-east-1.amazonaws.com."
        ]
    def presence(path):
        invoked.append(("presence",path.name))
        return False
    status=probe.inspect_public_route(
        local_probe=http,dns_probe=dns,release_presence=presence
    )
    assert len(invoked)==7
    assert status["source_provider_mismatch_observed"] is True
    assert status["mailbox_reads"] is False
    assert status["database_reads"] is False
    assert status["production_changes_performed"] is False
    assert "SECRET-SHOULD-NOT-BE-IN-OUTPUT" not in repr(status)


def test_provider_exceptions_sanitized_and_fail_closed():
    def failure(*args,**kwargs):
        raise RuntimeError("secret-password-in-unsafe-diagnostic")
    result=probe.inspect_public_route(
        local_probe=failure,dns_probe=failure,release_presence=failure
    )
    assert "REQUIRED_READONLY_EVIDENCE_PROBE_UNAVAILABLE" in result["blocked_reasons"]
    assert result["independently_verified_buyer_replies"] is None
    assert "secret-password" not in repr(result)


def test_unknown_report_state_never_promotes_inbound_by_boolean_guessing():
    status=assess(inbound_health={"ok":"true","provider":"resend",
                                  "reply_transport_configured":"true"},
                  relay_health={"ok":"true","provider":"gmail_api",
                                "send_authorized":False,
                                "mutation_authorized":False,"mode":"OBSERVE"})
    assert status["resend_webhook_reported_active"] is False
    assert status["gmail_relay_observed"] is False
    assert status["outbound_authorized"] is False


def test_default_founder_jev_status_does_not_claim_live_route_verification():
    from fastapi.testclient import TestClient
    from empire_os.founder_dashboard_service import build_founder_dashboard_service
    state=TestClient(build_founder_dashboard_service()).get(
        "/v1/founder-jev/status"
    ).json()
    assert state["mail_ingress_source_truth_probe_implemented"] is True
    assert state["mail_ingress_source_truth_checked_by_api"] is False
    assert state["first_party_reply_ingress_production_verified"] is False
    assert state["independently_verified_buyer_replies"] is None
    assert state["verified_revenue"] is None
    assert state["send_authorized"] is False
