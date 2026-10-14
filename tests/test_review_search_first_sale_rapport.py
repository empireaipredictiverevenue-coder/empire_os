"""Three live research candidates must inherit existing strict rapport policy."""
from scripts.review_search_first_sale_rapport import PROSPECTS,review_candidate
from empire_os.outbound_department import plan_outbound_account


def test_three_candidates_are_rapport_only_or_research():
    assert [x["key"] for x in PROSPECTS]==[
        "green_coast","roofelite","aastro",
    ]
    results=[review_candidate(x) for x in PROSPECTS]
    assert [x["next_action"] for x in results]==[
        "DRAFT_RAPPORT_TOUCH","RESEARCH","RESEARCH",
    ]
    assert results[0]["copy_review"]["eligible"] is True
    for item in results:
        assert item["strict_verified_reply_required"] is True
        assert item["send_authorized"] is False
        assert item["execution_authority"]=="none"
        assert item["outbound_sent"] is False
        assert item["product_pitch_in_first_touch"] is False
        assert item["automatic_followup"] is False
        assert item["founder_send_approved"] is False
        assert item["canonical_suppression_cleared"] is False
        assert item["professional_mailbox_send_authorized"] is False
        assert "$" not in item["first_touch_body"]
        assert "empire-ai.co.uk/buy" not in item["first_touch_body"]
        assert "we offer" not in item["first_touch_body"].casefold()


def test_after_one_green_coast_touch_existing_policy_waits_without_reply():
    first=PROSPECTS[0]
    r=review_candidate(first,history=[{
        "event_type":"sent","sent":True,"touch_purpose":"rapport",
        "evidence_refs":[first["source_ref"]],
    }])
    assert r["next_action"]=="WAIT"
    assert r["copy_review"] is None
    assert r["send_authorized"] is False


def test_unverified_reply_is_not_rapport_even_when_called_positive():
    r=review_candidate(PROSPECTS[0],replies=[{
        "reply_id":"not-verified","classification":"positive",
    }])
    assert r["next_action"]=="WAIT"
    assert r["relationship_stage"]=="COLD_VERIFIED"


def test_typed_model_recommendation_never_grants_send():
    first=PROSPECTS[0]
    account={
        "company_name":first["company_name"],
        "company_name_verified":True,
        "decision_maker":first["person"],
        "contact_route":"person_bound",
        "person_bound":True,
        "contact_email":first["email"],
        "buyer_review_status":"pending",
        "product_code":"technical_search_audit",
        "verified_reply_required_for_followup":True,
    }
    recommendation=plan_outbound_account(
        account,
        evidence=[{
            "evidence_ref":first["source_ref"],
            "summary":first["observation"],
            "verified":True,
            "fresh":True,
            "account_bound":True,
        }],
        astra_recommendation="HANDOFF_TO_CLOSER",
    )
    assert recommendation["action_type"]=="DRAFT_RAPPORT_TOUCH"
    assert recommendation["astra_director"]["recommendation_accepted"] is False
    assert recommendation["execution_authority"]=="none"


def test_only_explicit_verified_request_unlocks_human_commercial_review():
    reply={
        "reply_id":"verified-original-thread",
        "classification":"question",
        "provider_authenticated":True,
        "same_thread_verified":True,
        "counterpart_identity_verified":True,
        "requested_product_code":"technical_search_audit",
        "explicit_product_request_verified":True,
    }
    r=review_candidate(PROSPECTS[0],replies=[reply])
    assert r["relationship_stage"]=="COMMERCIAL_READY"
    assert r["next_action"]=="HANDOFF_TO_CLOSER"
    assert r["send_authorized"] is False
    assert r["copy_review"] is None


def test_nonexplicit_interested_reply_gets_human_discovery_only():
    reply={
        "reply_id":"verified-original-thread",
        "classification":"positive",
        "provider_authenticated":True,
        "same_thread_verified":True,
        "counterpart_identity_verified":True,
    }
    r=review_candidate(PROSPECTS[0],replies=[reply])
    assert r["relationship_stage"]=="CONVERSATION"
    assert r["send_authorized"] is False
    assert r["next_action"]=="HANDOFF_TO_CLOSER"
