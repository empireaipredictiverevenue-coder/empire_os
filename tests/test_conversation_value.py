from datetime import datetime, timezone

import pytest

from empire_os.conversation_value import (
    POSTAL_ADDRESS,
    build_first_touch_copy,
    build_followup_copy,
)

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def review(**evidence):
    base = {
        "business_name": "Kihle Roofing",
        "niche": "roofing",
        "metro": "Wichita",
        "rating": 4.8,
        "review_count": 116,
    }
    base.update(evidence)
    return {
        "contact_name": "Clay Winter",
        "evidence": base,
    }


def test_first_touch_uses_specific_proof_not_generic_opportunity_pitch():
    copy = build_first_touch_copy(review(), now=NOW)
    assert copy.quality_tier == "proof_backed_optimised"
    assert "4.8★ across 116 reviews" in copy.body
    assert "generic lead pitch" not in copy.body
    assert "small pilot" not in copy.body.lower()
    assert "opportunities in" not in copy.subject.lower()
    assert "want me to send it?" in copy.body.lower()
    assert "public evidence rather than guesses" in copy.body.lower()
    assert "bounded pilot" not in copy.body.lower()
    assert copy.subject in copy.subject_variants
    assert not any(term in copy.body.lower() for term in ("unlock", "leverage", "game-changing", "ai-powered"))
    assert POSTAL_ADDRESS in copy.body
    assert copy.subject_variants
    assert copy.quality_review["score"] >= 70


def test_fresh_why_now_wins_over_generic_proof():
    copy = build_first_touch_copy(
        review(
            why_now={
                "summary": "a severe hail signal overlaps your operating territory",
                "signal_type": "storm",
                "observed_at": "2026-09-21T08:00:00Z",
                "evidence_ref": "nws:dfw:signal-1",
            }
        ),
        now=NOW,
    )
    assert copy.quality_tier == "trigger_backed_optimised"
    assert "severe hail signal" in copy.body
    assert copy.why_now_evidence_ref == "nws:dfw:signal-1"


def test_stale_trigger_is_not_used_as_why_now():
    copy = build_first_touch_copy(
        review(
            why_now={
                "summary": "old storm",
                "signal_type": "storm",
                "observed_at": "2026-06-21T08:00:00Z",
                "evidence_ref": "old:storm",
            }
        ),
        now=NOW,
    )
    assert copy.quality_tier == "proof_backed_optimised"
    assert "old storm" not in copy.body


def test_missing_trigger_and_specific_proof_fails_closed():
    with pytest.raises(ValueError, match="specific outreach evidence"):
        build_first_touch_copy(
            {
                "contact_name": "Clay",
                "evidence": {
                    "business_name": "Kihle Roofing",
                    "niche": "roofing",
                    "metro": "Wichita",
                },
            },
            now=NOW,
        )


def test_placeholder_context_fails_closed():
    with pytest.raises(ValueError, match="conversation context missing"):
        build_first_touch_copy(
            {
                "contact_name": "Dave",
                "evidence": {
                    "business_name": "your team",
                    "niche": "local market",
                    "metro": "your market",
                    "rating": 5,
                    "review_count": 100,
                },
            },
            now=NOW,
        )


def test_rapport_followup_never_priced_by_prospect_score():
    evidence={
        "business_name":"Kihle Roofing","niche":"roofing","metro":"Wichita",
        "rating":5,"review_count":1200,"buy_signal_score":100,
        "why_now":{
            "summary":"public permits show a newly issued project in Wichita",
            "observed_at":"2026-09-20T12:00:00Z",
            "evidence_ref":"permit:wichita:001",
        },
    }
    row={"root_subject":"Clay — one thing I noticed in Wichita",
         "company_score":99,"candidate_evidence":evidence}
    first=build_followup_copy(row,step=1,now=NOW)
    assert "public permits show" in first.body
    assert "permit:wichita:001" in first.body
    for forbidden in ("$199","$249","$1,500","Reply “gap”",
                      "book a call","pricing","reply “pilot”"):
        assert forbidden.lower() not in first.body.lower()
    assert first.quality_tier=="source_backed_nurture_no_commercial_cta"
    with pytest.raises(ValueError,match="SECOND_TOUCH_NEW_SOURCE_EVIDENCE_REQUIRED"):
        build_followup_copy(row,step=2,now=NOW)
    row["prior_evidence_refs"]=["permit:other:prior-001"]
    second=build_followup_copy(row,step=2,now=NOW)
    assert "separate, newer source-backed" in second.body.lower()
    assert "$" not in second.body
    assert "opt out" in second.body.lower()


def test_rapport_followup_refuses_generic_prospect_only_rows():
    row={"candidate_evidence":{
        "business_name":"Kihle Roofing","niche":"roofing",
        "metro":"Wichita","review_count":1500,"buy_signal_score":100,
    }}
    with pytest.raises(ValueError,match="FRESH_SOURCE_BACKED_VALUE_REQUIRED"):
        build_followup_copy(row,step=1,now=NOW)
