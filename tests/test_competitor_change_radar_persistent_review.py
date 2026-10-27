"""Commercial change findings remain discoverable until explicit owner review."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from empire_os.competitor_change_radar import (
    acknowledge_review, build_radar,
)

AT = datetime(2026, 10, 27, tzinfo=timezone.utc)


def html(price: int, *, feature: bool = False) -> str:
    fragment = "<p>New feature now supports webhook automation and API access.</p>" if feature else ""
    return (
        "<html><main><h1>Public affiliate programme</h1>"
        f"<p>Plans start at £{price} per month for enterprise customers.</p>"
        "<p>Free trial and no credit card required.</p>"
        f"{fragment}</main></html>"
    )


def row(price: int, tick: int, *, feature: bool = False) -> dict:
    return {
        "entity_id": "operator-a", "company_name": "Operator A",
        "source_ref": "https://operator-a.com/pricing",
        "html": html(price, feature=feature),
        "industry": "b2b", "territory": "UK",
        "fetch_authority": "PUBLIC_ROBOTS_PERMITTED",
        "observed_at": (AT + timedelta(minutes=tick)).isoformat(),
    }


def _changed():
    original = build_radar([row(29, 0)])
    return build_radar([row(39, 2)], previous=original)


def test_change_survives_unchanged_reobservation_and_missing_fetch():
    changed = _changed()
    assert changed["new_review_candidate_count"] == 1
    assert changed["pending_review_count"] == 1
    review_id = changed["review_queue"][0]["review_id"]
    unchanged = build_radar([row(39, 4)], previous=changed)
    assert unchanged["unchanged_this_run"] == 1
    assert unchanged["pending_review_count"] == 1
    assert unchanged["new_review_candidate_count"] == 0
    assert unchanged["review_queue"][0]["review_id"] == review_id
    unavailable = build_radar([], previous=unchanged)
    assert unavailable["review_candidate_count"] == 1
    assert unavailable["review_queue"][0]["review_id"] == review_id


def test_followup_change_merges_into_same_open_review():
    changed = _changed()
    first_id = changed["review_queue"][0]["review_id"]
    later = build_radar([row(49, 5, feature=True)], previous=changed)
    assert later["pending_review_count"] == 1
    assert later["new_review_candidate_count"] == 0
    assert later["review_queue"][0]["review_id"] == first_id
    assert later["review_queue"][0]["research_priority"] == "PRICING_OR_OFFER_REVIEW"
    assert any("£49" in x["text"] for x in later["review_queue"][0]["changes"])


def test_only_explicit_human_resolution_closes_review():
    changed = _changed()
    item_id = changed["review_queue"][0]["review_id"]
    closed = acknowledge_review(
        changed, review_id=item_id, reviewer="founder",
        reason="Reviewed cited pricing; still only market research.",
        now=AT + timedelta(minutes=7),
    )
    assert closed["pending_review_count"] == 0
    assert closed["review_queue"] == []
    assert closed["resolved_reviews"][0]["decision"] == "REVIEW_CLOSED_NOT_BUYER_CONFIRMED"
    assert closed["outreach_enabled"] is False
    unchanged = build_radar([row(39, 8)], previous=closed)
    assert unchanged["pending_review_count"] == 0
    assert len(unchanged["resolved_reviews"]) == 1
    with pytest.raises(ValueError, match="already resolved"):
        acknowledge_review(
            closed, review_id=item_id, reviewer="founder",
            reason="Cannot resolve the same item twice", now=AT + timedelta(minutes=9),
        )


def test_invalid_decision_or_unauthorised_snapshot_rejected():
    changed = _changed()
    item_id = changed["review_queue"][0]["review_id"]
    with pytest.raises(ValueError, match="reviewer"):
        acknowledge_review(changed, review_id=item_id,
                           reviewer="../admin", reason="Verified source evidence.",
                           now=AT + timedelta(minutes=7))
    with pytest.raises(ValueError, match="explanation"):
        acknowledge_review(changed, review_id=item_id,
                           reviewer="founder", reason="ok",
                           now=AT + timedelta(minutes=7))
    changed["outreach_enabled"] = True
    with pytest.raises(ValueError, match="untrusted radar"):
        acknowledge_review(changed, review_id=item_id,
                           reviewer="founder", reason="Reviewed and acknowledged.",
                           now=AT + timedelta(minutes=7))
