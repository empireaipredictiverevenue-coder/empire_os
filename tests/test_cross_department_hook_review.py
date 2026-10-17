"""Cross-department hook reviews never become invisible execution authority."""
from __future__ import annotations

import json

import pytest

from empire_os.control_fabric import default_registry, route_event
from empire_os.cross_department_hook_review import (
    ReviewHook, content_hook_brief, content_hook_lenses, hook_catalogue,
    preview_event_hook, review_hook_coverage,
)
from empire_os.departments import default_departments


def test_full_department_coverage_reuses_existing_component_registry():
    review = review_hook_coverage()
    assert review["total"] == 34
    assert review["existing_route_count"] == 30
    assert review["unwired_count"] == 4
    assert {hook["department"] for hook in review["hooks"]} == {
        d.key for d in default_departments()
    }
    components = {r.name for r in default_registry()}
    assert all(hook["consumer"] in components for hook in review["hooks"])
    assert all(hook["hook_execution_authority"] == "none" for hook in review["hooks"])
    assert review["model_registered_or_activated_by_this_review"] is False
    assert review["new_scheduler"] is False
    assert review["new_database"] is False
    assert review["external_requests"] is False


def test_existing_control_fabric_routes_are_reused_not_overwritten():
    for spec in hook_catalogue():
        existing = route_event({"event_type": spec.event_type})
        observed = [r["component"] for r in existing]
        mapped = next(x for x in review_hook_coverage()["hooks"] if x["key"] == spec.key)
        assert mapped["existing_route_wired_in_control_fabric"] == (spec.consumer in observed)
        if spec.consumer in observed:
            assert mapped["current_control_fabric_authority"] in {
                "observe", "internal_write", "governed_external", "founder_gate"
            }


def test_unwired_proposed_hooks_remain_visible_but_inert():
    rows = review_hook_coverage()["hooks"]
    missing = {row["key"] for row in rows if row["status"] == "UNWIRED_NO_EXECUTION"}
    assert missing == {
        "confirmed_newsletter_opt_in",
        "website_article_live",
        "media_draft_content_hook",
        "verified_opt_out",
    }
    for row in rows:
        assert not row["automatic_publish"]
        assert not row["automatic_outbound"]
        assert not row["model_invocation"]
        assert not row["funds_moved"]


def test_prospect_and_email_reply_hook_exposes_no_personal_data():
    raw = {
        "event_type": "buyer_reply_received",
        "source": "mailbox",
        "email": "example@private.test",
        "subject_id": "private-customer-42",
        "payload": {"phone": "+441234567890", "content": "a sensitive message"},
    }
    result = preview_event_hook(raw, evidence_refs=("private-db:reply-42",))
    assert result["event_type"] == "buyer_reply_received"
    assert len(result["matches"]) == 1
    assert result["matches"][0]["status"] == "EVIDENCE_REVIEW_PENDING"
    assert result["matches"][0]["evidence_verified"] is False
    assert result["execution_authority"] == "none"
    assert result["messages_sent"] is False
    assert result["payment_executed"] is False
    serialized = json.dumps(result)
    for secret in ("example@private.test", "private-customer-42", "+441234567890", "a sensitive message", "private-db:reply-42"):
        assert secret not in serialized


@pytest.mark.parametrize(
    "event_type",
    ["payment_verified", "revenue_recognized", "outbound_intent_proposed",
     "newsletter_subscription_confirmed", "email_opt_out_verified"],
)
def test_money_and_outbound_events_never_execute_from_hook_review(event_type):
    result = preview_event_hook(
        {"event_type": event_type, "amount": 999_999_999},
        evidence_refs=["empiredb:event-observation-1"],
    )
    assert result["matches"]
    assert result["execution_authority"] == "none"
    assert not result["payment_executed"]
    assert not result["messages_sent"]
    for matched in result["matches"]:
        assert matched["execution_allowed"] is False
        assert matched["publication_authorized"] is False
        assert matched["outbound_authorized"] is False
        assert matched["payment_authorized"] is False


def test_missing_evidence_does_not_claim_verified_work():
    result = preview_event_hook({"event_type": "organic_gap_observed"})
    assert result["matches"][0]["status"] == "EVIDENCE_MISSING"
    assert result["matches"][0]["evidence_verified"] is False
    assert result["canonical_record_lookup_performed"] is False


def test_idempotent_event_fingerprint_never_includes_raw_identifiers():
    a = preview_event_hook(
        {"event_type": "funnel_change_observed", "sensitive": "hidden"},
        evidence_refs=["same-ref", "another-ref"],
    )
    b = preview_event_hook(
        {"event_type": "funnel_change_observed", "sensitive": "different"},
        evidence_refs=["another-ref", "same-ref"],
    )
    assert a["evidence_fingerprint"] == b["evidence_fingerprint"]
    c = preview_event_hook(
        {"event_type": "funnel_change_observed"}, evidence_refs=["other-ref"],
    )
    assert c["evidence_fingerprint"] != a["evidence_fingerprint"]
    assert "same-ref" not in json.dumps(a)


def test_content_hooks_cover_all_channels_without_fake_copy():
    assert len(content_hook_lenses()) == 10
    for channel in (
        "seo_article", "seo_title", "landing_page", "email_newsletter",
        "video_script", "social_post", "sales_deck", "partner_outreach",
    ):
        brief = content_hook_brief(
            channel=channel,
            audience="Commercial roofing purchasing managers",
            problem="Qualifying the survey and routing a genuine project",
        )
        assert brief["mode"] == "DRAFT_ONLY"
        assert brief["quality_and_editorial_review_required"] is True
        assert brief["copy_generated"] is False
        assert brief["publication_allowed"] is False
        assert brief["outbound_allowed"] is False
        assert brief["claimed_evidence_requires_review"] is True


def test_reject_unknown_events_invalid_content_and_unbounded_refs():
    with pytest.raises(ValueError):
        preview_event_hook({"event_type": "bad event"})
    with pytest.raises(ValueError):
        preview_event_hook(
            {"event_type": "organic_gap_observed"},
            evidence_refs=[f"ref:{n}" for n in range(11)],
        )
    with pytest.raises(ValueError):
        content_hook_brief(
            channel="unknown",
            audience="Businesses", problem="Lead leakage problem",
        )
    with pytest.raises(ValueError):
        ReviewHook(
            "invalid key", "marketing_growth", "editorial",
            "organic_gap_observed", "search_intelligence",
            "Wrong", 40,
        )
