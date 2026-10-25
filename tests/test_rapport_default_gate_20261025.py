"""Regression: no-reply nurture cannot default back to an offer."""
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.conversation_value import build_followup_copy

NOW=datetime(2026,10,25,19,0,tzinfo=timezone.utc)


def row(*,score=0,step=1):
    return {
        "company_score":score,
        "buyer_signal_score":score,
        "root_subject":"Civic Expansion Source",
        "candidate_evidence":{
            "business_name":"Example Roofing",
            "niche":"roofing",
            "metro":"Chicago",
            "buy_signal_score":score,
            "review_count":1200,
            "why_now":{
                "summary":"A permit-stage project was publicly reported",
                "evidence_ref":"official-permit:chi:123",
                "observed_at":(NOW-timedelta(days=1)).isoformat(),
            },
        },
        "prior_evidence_refs":["official-permit:chi:old"],
        "followup_step":step,
    }


@pytest.mark.parametrize("score",[0,50,80,90,99,100,10000])
def test_scores_never_inject_price_offer_or_cta(score):
    for step in (1,2):
        rendered=build_followup_copy(row(score=score,step=step),step=step,now=NOW)
        assert "official-permit:chi:123" in rendered.body
        assert rendered.why_now_evidence_ref=="official-permit:chi:123"
        assert rendered.quality_tier=="source_backed_nurture_no_commercial_cta"
        for forbidden in ("$","£","€","pilot","buy-leads","reply “gap”",
                          "reply “map”","reply “pilot”","book a call","schedule",
                          "let's talk","pricing","checkout"):
            assert forbidden not in rendered.body.lower()


def test_generic_prospect_and_ratings_do_not_generate_nurture():
    r=row()
    del r["candidate_evidence"]["why_now"]
    for step in (1,2):
        with pytest.raises(ValueError,match="FRESH_SOURCE_BACKED_VALUE_REQUIRED"):
            build_followup_copy(r,step=step,now=NOW)


def test_second_touch_with_reused_or_unknown_evidence_is_held():
    r=row(step=2)
    r["prior_evidence_refs"]=["official-permit:chi:123"]
    with pytest.raises(ValueError,match="SECOND_TOUCH_NEW_SOURCE"):
        build_followup_copy(r,step=2,now=NOW)
    r.pop("prior_evidence_refs")
    with pytest.raises(ValueError,match="SECOND_TOUCH_NEW_SOURCE"):
        build_followup_copy(r,step=2,now=NOW)


def test_future_or_stale_trigger_must_not_produce_outreach():
    r=row()
    for time in (NOW+timedelta(days=1),NOW-timedelta(days=60)):
        r["candidate_evidence"]["why_now"]["observed_at"]=time.isoformat()
        with pytest.raises(ValueError,match="FRESH_SOURCE_BACKED_VALUE_REQUIRED"):
            build_followup_copy(r,step=1,now=NOW)


def test_no_unverified_value_even_if_product_candidate_is_marked_approved():
    r=row(score=100)
    r["approved"]=True
    r["product_code"]="managed_service"
    r["cta_allowed"]=True
    r["price_allowed"]=True
    r["candidate_evidence"]["why_now"]["summary"]="A public permit was issued"
    copy=build_followup_copy(r,step=1,now=NOW)
    assert "A public permit was issued" in copy.body
    assert "managed" not in copy.body.lower()
    assert "$" not in copy.body
    assert "would you like" not in copy.body.lower()
