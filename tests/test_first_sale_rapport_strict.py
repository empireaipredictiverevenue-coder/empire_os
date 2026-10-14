"""First-sale rapport: use the existing Outbound Department, not a new sender."""
import pytest

from empire_os.outbound_department import (
    plan_outbound_account, review_outbound_draft,
)

ACCOUNT={
    "company_name":"Green Coast Roofing & Solar",
    "company_name_verified":True,
    "decision_maker":"Brian Sujevich",
    "contact_email":"brian@gogreencoast.com",
    "contact_route":"person_bound",
    "person_bound":True,
    "buyer_review_status":"pending",
    "product_code":"technical_search_audit",
    "verified_reply_required_for_followup":True,
}
EVIDENCE={
    "evidence_ref":"source:green-coast-20261004-launch",
    "summary":"Green Coast Roofing & Solar published a redesigned website announcement.",
    "verified":True,
    "fresh":True,
    "account_bound":True,
}
FIRST_SUBJECT="Green Coast website refresh"
FIRST_BODY=(
    "Hi Brian,\n\nI saw Green Coast Roofing & Solar announced its redesigned "
    "website this month. Bringing the roofing and solar work into one clear "
    "experience for customers looks like a substantial project. Thought it "
    "was worth acknowledging the launch.\n\nBest,\nPhil\nEmpire AI"
)


def planning(*, history=(), replies=(), account=None, evidence=None, suppressions=()):
    return plan_outbound_account(
        ACCOUNT if account is None else account,
        history=history, replies=replies,
        evidence=[EVIDENCE] if evidence is None else evidence,
        suppressions=suppressions,
    )


def sent(n=1):
    return [
        {"event_type":"delivered","delivered":True,
         "touch_purpose":"value","evidence_refs":["old-"+str(i)]}
        for i in range(n)
    ]


def reply(*, classification="positive", **override):
    record={
        "reply_id":"canonical-message-1",
        "classification":classification,
        "provider_authenticated":True,
        "same_thread_verified":True,
        "counterpart_identity_verified":True,
        "explicit_product_request_verified":False,
    }
    record.update(override)
    return record


def test_cold_verified_account_gets_rapport_only_not_pitch():
    p=planning()
    assert p["action_type"]=="DRAFT_RAPPORT_TOUCH"
    assert p["price_allowed"] is False
    assert p["cta_allowed"] is False
    assert p["execution_authority"]=="none"
    result=review_outbound_draft(
        account=ACCOUNT,plan=p,subject=FIRST_SUBJECT,body=FIRST_BODY,
        used_evidence_refs=[EVIDENCE["evidence_ref"]],
    )
    assert result["eligible"] is True, result["blockers"]
    assert result["send_enabled"] is False


@pytest.mark.parametrize("phrase",[
    "We offer a Technical Search Audit.",
    "We offer an audit of your pages.",
    "Here is our checkout link https://empire-ai.co.uk/buy",
    "Our service helps contractors.",
    "Competitor Search Gap",
    "Search Opportunity Map",
])
def test_unsolicited_product_pitch_without_price_still_blocked(phrase):
    p=planning()
    draft=FIRST_BODY+"\n"+phrase
    check=review_outbound_draft(
        account=ACCOUNT,plan=p,subject=FIRST_SUBJECT,body=draft,
        used_evidence_refs=[EVIDENCE["evidence_ref"]],
    )
    assert "PREMATURE_OFFER" in check["blockers"]


@pytest.mark.parametrize("followups",[1,2,4,8])
def test_any_unanswered_outreach_freezes_no_scheduled_sequence(followups):
    p=planning(history=sent(followups))
    assert p["action_type"]=="WAIT"
    assert p["cta_allowed"] is False
    assert p["price_allowed"] is False
    assert p["automated_nurture_allowed"] is False


@pytest.mark.parametrize("defect",[
    {"provider_authenticated":False},
    {"same_thread_verified":False},
    {"counterpart_identity_verified":False},
    {"reply_id":None},
])
def test_unverified_positive_label_never_unlocks_rapport_or_price(defect):
    p=planning(history=sent(),replies=[reply(**defect)])
    assert p["action_type"]=="WAIT"
    assert "unverified_reply" in p["reason"]
    assert p["price_allowed"] is False


def test_real_authenticated_reply_requires_discovery_not_an_instant_pitch():
    p=planning(history=sent(),replies=[reply(classification="positive")])
    assert p["action_type"]=="HANDOFF_TO_CLOSER"
    assert p["relationship_stage"]=="CONVERSATION"
    assert p["price_allowed"] is False
    assert p["execution_authority"]=="none"


def test_explicit_verified_product_request_unlocks_review_not_send():
    verified=reply(
        classification="pricing_question",
        explicit_product_request_verified=True,
        requested_product_code="technical_search_audit",
    )
    p=planning(history=sent(),replies=[verified])
    assert p["relationship_stage"]=="COMMERCIAL_READY"
    assert p["price_allowed"] is True
    assert p["action_type"]=="HANDOFF_TO_CLOSER"
    assert p["execution_authority"]=="none"
    assert p["deliverability_check_required"] is False


def test_another_product_requested_does_not_authorize_this_offer():
    verified=reply(
        explicit_product_request_verified=True,
        requested_product_code="predictive_revenue_diagnostic",
    )
    p=planning(history=sent(),replies=[verified])
    assert p["action_type"]=="HANDOFF_TO_CLOSER"
    assert p["price_allowed"] is False


def test_stale_commercial_ready_flag_without_real_reply_must_wait():
    p=planning(account={**ACCOUNT,"commercial_ready":True})
    assert p["action_type"]=="WAIT"
    assert p["price_allowed"] is False


def test_suppression_is_stronger_than_all_rapport_evidence():
    p=planning(
        history=sent(),replies=[
            reply(explicit_product_request_verified=True,
                  requested_product_code="technical_search_audit")],
        suppressions=[{"status":"suppressed"}],
    )
    assert p["action_type"]=="SUPPRESS"
    assert p["price_allowed"] is False


def test_unsubscribe_held_without_needing_rapport_proof():
    p=planning(replies=[{"classification":"unsubscribe"}])
    assert p["action_type"]=="SUPPRESS"


def test_research_only_without_contact_or_review_stays_research():
    p=planning(account={
        **ACCOUNT,"contact_email":None,
        "contact_route":None,"person_bound":False,
        "buyer_review_status":"research",
    })
    assert p["action_type"]=="RESEARCH"
    assert p["price_allowed"] is False


def test_first_touch_cannot_quietly_include_checkout_or_price():
    p=planning()
    review=review_outbound_draft(
        account=ACCOUNT, plan=p, subject=FIRST_SUBJECT,
        body=FIRST_BODY+"\n\nWe offer a $299 audit. Book a demo?",
        used_evidence_refs=[EVIDENCE["evidence_ref"]],
    )
    assert set(("PREMATURE_PRICE","PREMATURE_OFFER","PREMATURE_CTA")).issubset(review["blockers"])
