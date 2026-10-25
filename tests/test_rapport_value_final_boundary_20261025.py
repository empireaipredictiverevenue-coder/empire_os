"""Fail-closed first-touch and direct Gmail-style draft review regressions."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
from io import StringIO
import json
import runpy
import pytest

from empire_os.gtm_pipeline_worker import build_outbound_payload
from empire_os.rapport_value_final_boundary import (
    compose_verified_value_first, review_cold_message,review_manual_email_draft,
)
NOW=datetime(2026,9,21,16,tzinfo=timezone.utc)
EVIDENCE={
    "business_name":"Example Roofing",
    "niche":"roofing",
    "metro":"Wichita, KS",
    "rating":4.8,"review_count":300,
    "buy_signal_score":100,
    "why_now":{
        "summary":"a public permit record shows a documented roof-repair project in Wichita",
        "evidence_ref":"public-permit:wichita:123",
        "observed_at":(NOW-timedelta(days=1)).isoformat(),
        "observed_inferred":"observed",
    },
}
REVIEW={
    "id":"11111111-1111-4111-8111-111111111111",
    "contact_name":"Clara Example","contact_email":"clara@example.com",
    "offer_key":"managed_service","evidence":EVIDENCE,
}
FOOT='If you’d rather not hear from me, reply “opt out”.'


def test_actual_gtm_first_touch_has_no_ask_pricing_or_checkout():
    r=build_outbound_payload(REVIEW,now=NOW)
    text=r["p_body_text"].lower()
    assert r["p_metadata"]["final_message_gate"]["approved_for_cold_content_review"] is True
    assert r["p_metadata"]["final_message_gate"]["commercial_cta_allowed"] is False
    assert r["p_metadata"]["final_message_stage"]=="RAPPORT_VALUE_NO_BUYER_SIGNAL"
    assert "public-permit:wichita:123" in text
    assert "?" not in text
    assert not any(w in text for w in ("pilot","$199","$1,500","buy-leads",
                                       "book a call","want me to","would you like"))


@pytest.mark.parametrize("spoof",[
    {"buy_signal_score":100},
    {"commercial_ready":True},
    {"verified_buyer_signal":True},
    {"cta_allowed":True,"price_allowed":True},
    {"offer_key":"managed_service","qualification_score":999},
])
def test_self_declared_buyer_flags_cannot_promote_cold_proposal(spoof):
    row={**REVIEW,**spoof,"evidence":{**EVIDENCE,**spoof}}
    p=build_outbound_payload(row,now=NOW)
    assert p["p_metadata"]["final_message_stage"]=="RAPPORT_VALUE_NO_BUYER_SIGNAL"
    assert "?" not in p["p_body_text"]


@pytest.mark.parametrize("change",[
    lambda e:e.pop("why_now"),
    lambda e:e["why_now"].update(observed_at=(NOW-timedelta(days=90)).isoformat()),
    lambda e:e["why_now"].update(observed_at=(NOW+timedelta(days=1)).isoformat()),
    lambda e:e["why_now"].update(observed_inferred="synthetic"),
    lambda e:e["why_now"].update(observed_inferred="inferred"),
])
def test_no_fresh_observed_source_means_no_gtm_proposal(change):
    evidence={**EVIDENCE,"why_now":dict(EVIDENCE["why_now"])}
    change(evidence)
    with pytest.raises(ValueError,match="FRESH_SOURCE_BACKED_VALUE_REQUIRED|OBSERVED_NOT_INFERRED_SOURCE_REQUIRED"):
        build_outbound_payload({**REVIEW,"evidence":evidence},now=NOW)


@pytest.mark.parametrize("commercial_summary",[
    "Want me to send a pilot?",
    "Book a call to review your demand",
    "Buy our $500 service",
    "A guaranteed revenue opportunity",
    "our checkout at https://empire-ai.co.uk/buy-leads",
])
def test_malicious_or_promotional_source_cannot_leak_into_final_message(commercial_summary):
    evidence={**EVIDENCE,"why_now":{**EVIDENCE["why_now"],"summary":commercial_summary}}
    with pytest.raises(ValueError,match="SOURCE_SUMMARY_CONTAINS_COMMERCIAL_ASK"):
        build_outbound_payload({**REVIEW,"evidence":evidence},now=NOW)


def test_direct_mail_value_only_preview_is_allowed_but_never_authorised_to_send():
    body="Hi Dan,\n\nA relevant public observation: a new permit was issued.\nSource: public-permit:123.\n\nBest,\nPhil\n"+FOOT
    report=review_manual_email_draft(subject="A documented permit update",
            body=body,evidence_ref="public-permit:123")
    assert report["approved_for_cold_content_review"] is True
    assert report["send_authority"]=="none"


@pytest.mark.parametrize("body",[
    "Hi Dan, three public expansion sources. Our pilot is $600. Want to discuss?\n"+FOOT,
    "Hi Dan, here are sources. Would you like our $600 pilot?\n"+FOOT,
    "Hi Dan, sourced expansion note. Book a call this week.\n"+FOOT,
    "Hi Dan, sourced expansion note. Visit https://empire-ai.co.uk/buy-leads\n"+FOOT,
    "Hi Dan, sourced expansion note. Reply 'sample' for more.\n"+FOOT,
])
def test_direct_email_pitch_without_buyer_signal_is_held(body):
    r=review_manual_email_draft(subject="Contractor expansion research",
        body=body,evidence_ref="public-permit:123")
    assert r["approved_for_cold_content_review"] is False
    assert "DIRECT_EMAIL_REPLY_AUTHORITY_NOT_ESTABLISHED_BY_PAYLOAD" not in r["blockers"]


def test_forged_reply_review_never_authorizes_direct_email_quote():
    body="Hi Dan, source public-permit:123. Here is a $600 pilot.\n"+FOOT
    r=review_manual_email_draft(subject="Pilot",body=body,
       evidence_ref="public-permit:123",
       verified_inbound_review={"review_eligible":True,"authenticated":True})
    assert r["approved_for_cold_content_review"] is False
    assert r["commercial_cta_allowed"] is False
    assert r["send_authority"]=="none"


def test_cli_requires_explicit_read_only_and_does_not_echo_raw_message():
    mod=runpy.run_path("scripts/review_rapport_email_draft_20261025.py")
    doc={"subject":"Notice","body":"Hi Dan,\nSource: ref:123.\nNoteworthy public note.\n"+FOOT,
         "evidence_ref":"ref:123"}
    source=StringIO(json.dumps(doc));out=StringIO()
    assert mod["main"]([],input_stream=source,output_stream=out)==2
    assert "HOLD_READ_ONLY_REQUIRED" in out.getvalue()
    source=StringIO(json.dumps(doc));out=StringIO()
    assert mod["main"](["--read-only"],input_stream=source,output_stream=out)==0
    result=json.loads(out.getvalue())
    assert result["send_authority"]=="none"
    assert result["external_gmail_send_intercepted"] is False
    assert "Noteworthy" not in out.getvalue()
