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
    assert copy.quality_tier == "proof_backed"
    assert "4.8★ across 116 reviews" in copy.body
    assert "generic lead pitch" in copy.body
    assert "small pilot" not in copy.body.lower()
    assert "opportunities in" not in copy.subject.lower()
    assert "send it" in copy.body.lower()
    assert POSTAL_ADDRESS in copy.body


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
    assert copy.quality_tier == "trigger_backed"
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
    assert copy.quality_tier == "proof_backed"
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


def test_followup_is_value_led_and_closes_after_step_two():
    row = {
        "root_subject": "Clay — one thing I noticed in Wichita",
        "candidate_evidence": {
            "business_name": "Kihle Roofing",
            "niche": "roofing",
            "metro": "Wichita",
        },
    }
    first = build_followup_copy(row, step=1, now=NOW)
    final = build_followup_copy(row, step=2, now=NOW)
    assert "one-page Wichita roofing brief" in first.body
    assert "reply “send it”" in first.body
    assert "Closing the loop" in final.body
    assert "No need for a call first" in final.body
