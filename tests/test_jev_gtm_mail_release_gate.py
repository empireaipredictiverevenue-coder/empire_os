"""JEV mail truth attachment cannot turn route status into a buyer verdict."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from empire_os.jev_gtm_v2 import build_jev_gtm_decision
from empire_os.jev_gtm_mail_source_truth import assess_jev_ingress_truth
from empire_os.jev_gtm_mail_release_gate import attach_jev_ingress_release_gate

NOW=datetime(2026,10,14,11,tzinfo=timezone.utc)


def decision():
    return build_jev_gtm_decision(
        account={
            "entity_id":"entity:fictional-roofing",
            "tenant_id":"tenant:fictional",
            "opportunity_key":"opportunity:fictional",
            "entity_verified":False,
            "tenant_binding_verified":False,
            "business_name":"Fictional Test Ltd",
            "description":"fictional roofing",
            "target_buyer_pools":["local_and_smb_buyers"],
            "target_product_codes":["managed_service"],
            "first_party_people":[{"title":"owner"}],
        },
        signals=[],outreach={},as_of=NOW,
    )


def route_truth():
    return assess_jev_ingress_truth(
        relay_health={
            "ok":True,"provider":"gmail_api","mode":"OBSERVE",
            "send_authorized":False,"mutation_authorized":False,
        },
        founder_readiness={"provider":"owned_imap","configured":False},
        inbound_health={"ok":True,"provider":"resend","reply_transport_configured":True},
        root_mx=["1 smtp.google.com."],
        reply_mx=["10 inbound-smtp.us-east-1.amazonaws.com."],
        canonical_release_dropin_present=False,
        canonical_reader_credential_present=False,
        observed_at=NOW,
    )


def test_release_gate_does_not_modify_jev_decision_or_claim_buyer():
    data=decision()
    before=deepcopy(data)
    output=attach_jev_ingress_release_gate(data,route_truth())
    assert data==before
    assert output["decision_fingerprint"]==data["decision_fingerprint"]
    assert output["jev_action_unchanged"]==data["action"]
    assert output["mail_source_truth_status"]=="HOLD_FIRST_PARTY_REPLY_ACTIVATION"
    assert "REPLY_MX_POINTS_TO_EXTERNAL_SES" in output["mail_source_blockers"]
    assert output["original_provider_reply_verified"] is False
    assert output["revenue_eligible"] is False
    assert output["realized_revenue"] is None
    assert output["outbound_authorized"] is False
    assert output["database_write"] is False
    assert output["execution_authority"]=="none"
    assert "Fictional Test Ltd" not in repr(output)


@pytest.mark.parametrize("override",[
    {"status":"READY"},
    {"mode":"EXECUTE"},
    {"execution_authority":"send"},
    {"production_changes_performed":True},
    {"mail_sent":True},
    {"dns_modified":True},
    {"mailbox_reads":True},
    {"database_reads":True},
    {"outbound_authorized":True},
    {"first_party_inbound_transport_verified":True},
    {"original_provider_receipt_identity_verified":True},
    {"canonical_contact_verified":True},
    {"independently_verified_buyer_replies":1},
    {"verified_commercial_revenue":100},
])
def test_forged_source_readiness_can_never_escalate_rights(override):
    data={**route_truth(),**override}
    with pytest.raises(ValueError,match="untrusted"):
        attach_jev_ingress_release_gate(decision(),data)


def test_source_cannot_put_customer_pii_in_blocker():
    report=route_truth()
    report["blocked_reasons"].append("private@example.invalid")
    with pytest.raises(ValueError,match="blockers"):
        attach_jev_ingress_release_gate(decision(),report)


def test_source_evidence_absent_does_not_count_zero_verified_buyers():
    report=route_truth()
    report["independently_verified_buyer_replies"]=0
    with pytest.raises(ValueError,match="untrusted"):
        attach_jev_ingress_release_gate(decision(),report)
