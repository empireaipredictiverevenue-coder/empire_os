"""Synthetic/offline contract tests for non-executing commercial review."""
from copy import deepcopy

import pytest

from empire_os.video_commercial_growth_framework import build_commercial_growth_review


def offer(
    identity="prospect-101",
    *,
    ready=True,
    demand="UNKNOWN",
    existing=False,
    state=None,
):
    state = state or ("OFFER_READY" if ready else "PRODUCT_READINESS_REQUIRED")
    return {
        "canonical_prospect_id": identity,
        "company": "Example Services",
        "domain": "example.invalid",
        "person_name": "Do Not Export",
        "email": "private@example.invalid",
        "state": state,
        "offer_package_ready": ready,
        "buyer_demand_verified": demand == "VERIFIED",
        "demand_state": demand,
        "contact_mode": "EXISTING_THREAD_REVIEW" if existing else "NEW_OUTREACH_REVIEW",
        "ready_product_codes": ["pricing_report"] if ready else [],
        "products": [{
            "product_code": "pricing_report",
            "amount_cents": 49900,
            "currency": "USD",
            "unit": "per_report",
        }],
        "send_blockers": ["existing_governance_gate"],
        "evidence_refs": ["canonical:evidence:1"],
    }


def fixture(*, offers=None, signals=None, funnel=None):
    return {
        "observations": {
            "observations": [] if signals is None else signals
        },
        "offer_book": {
            "schema_version": "empire.predictive-revenue.commercial-offer-book.v2",
            "targets": [offer()] if offers is None else offers,
        },
        "funnel": {
            "schema_version": "empire.founder_commercial_funnel.v1",
            "actual_revenue": False,
            "recognized_revenue_cents": 0,
            "realized_margin_cents": 0,
            "next_event": "qualify_and_review",
            **(funnel or {}),
        },
    }


def signal(*, prospect="prospect-101", signal_id="signal:1"):
    return {
        "canonical_prospect_id": prospect,
        "signal_id": signal_id,
        "niche": "roofing",
        "pain_summary": "Unbooked qualified enquiries",
        "buyer_demand_verified": True,  # Deliberately adversarial.
        "evidence_refs": ["research:source:1"],
    }


def review(**kwargs):
    return build_commercial_growth_review(**fixture(**kwargs))


def test_unverified_research_cannot_elevate_buyer_demand():
    result = review(signals=[signal()])
    row = result["review_queue"][0]
    assert row["offer_package_ready"] is True
    assert row["demand_state"] == "NOT_VERIFIED"
    assert row["next_research_or_review_action"] == "VALIDATE_BUYER_DEMAND"
    assert row["research_problem_hypotheses"][0]["status"] == "UNVERIFIED_RESEARCH_HYPOTHESIS"
    assert row["linked_research_signal_ids"] == ["signal:1"]
    assert row["expected_revenue_cents"] is None
    assert row["revenue_realized_cents"] is None


def test_buyer_demand_verified_by_offer_book_existing_thread():
    result = review(offers=[offer(demand="VERIFIED", existing=True)], signals=[signal()])
    row = result["review_queue"][0]
    assert row["demand_state"] == "BUYER_DEMAND_VERIFIED_BY_OFFER_BOOK"
    assert row["next_research_or_review_action"] == "REVIEW_EXISTING_THREAD_FOR_NEXT_QUESTION"
    assert row["priority_band"] == 0
    assert row["outreach_authorized"] is False
    assert "current_canonical_suppression_and_inbox_check" in row["send_blockers"]


def test_verified_demand_new_outreach_is_still_blocked():
    result = review(offers=[offer(demand="VERIFIED")])
    row = result["review_queue"][0]
    assert row["next_research_or_review_action"] == "REQUEST_FOUNDER_OUTBOUND_REVIEW"
    assert row["outreach_authorized"] is False
    assert result["outbound_authority"] == "NONE"
    assert result["payment_authority"] == "NONE"


def test_product_readiness_is_not_bypassed_by_demand():
    result = review(offers=[offer(ready=False, demand="VERIFIED")])
    row = result["review_queue"][0]
    assert row["offer_package_ready"] is False
    assert row["ready_product_codes"] == []
    assert row["verified_offer_price_bases"] == []
    assert row["next_research_or_review_action"] == "VERIFY_PRODUCT_TERMS_AND_FULFILLMENT"


def test_weak_contact_evidence_blocks_offer():
    result = review(offers=[offer(ready=False, state="CONTACT_EVIDENCE_REQUIRED")])
    assert result["review_queue"][0]["next_research_or_review_action"] == "QUALIFY_CONTACT_EVIDENCE"


def test_dedup_signal_and_preserve_canonical_id_only():
    result = review(signals=[signal(), signal()])
    assert result["source_counts"]["duplicate_research_observations_skipped"] == 1
    assert result["source_counts"]["linked_research_observations"] == 1
    assert result["review_queue"][0]["linked_research_signal_ids"] == ["signal:1"]


def test_missing_canonical_identity_does_not_fuzzy_join():
    anonymous = signal()
    anonymous.pop("canonical_prospect_id")
    result = review(signals=[anonymous, signal(prospect="wrong-prospect", signal_id="signal:2")])
    assert result["review_queue"][0]["linked_research_signal_ids"] == []
    reasons = {s["review_reason"] for s in result["unlinked_signal_review"]}
    assert reasons == {"canonical_prospect_id_required", "no_canonical_offer_book_target"}


def test_empty_signal_evidence_stays_unlinked_not_assumed_real():
    row = signal()
    row["evidence_refs"] = []
    result = review(signals=[row])
    assert result["source_counts"]["unlinked_research_observations"] == 1
    assert result["source_counts"]["linked_research_observations"] == 0


def test_duplicate_canonical_prospect_in_offerbook_fails_closed():
    with pytest.raises(ValueError, match="duplicate canonical_prospect_id"):
        review(offers=[offer(), offer()])


def test_offerbook_without_identity_needs_resolution_no_authority():
    result = review(offers=[offer(identity=None, demand="VERIFIED", existing=True)])
    row = result["review_queue"][0]
    assert row["next_research_or_review_action"] == "RESOLVE_CANONICAL_PROSPECT_ID"
    assert row["offer_package_ready"] is False
    assert row["verified_offer_price_bases"] == []


def test_only_catalogue_price_not_revenue_projection_or_payment():
    result = review()
    row = result["review_queue"][0]
    assert row["verified_offer_price_bases"][0]["amount_cents"] == 49900
    assert row["expected_revenue_cents"] is None
    assert row["payment_authorized"] is False
    assert result["aggregate_revenue_context"]["reported_recognized_revenue_cents"] is None
    assert "private@example.invalid" not in str(result)
    assert "Do Not Export" not in str(result)


def test_aggregate_revenue_not_misattributed_to_candidates():
    result = review(funnel={
        "actual_revenue": True,
        "recognized_revenue_cents": 120000,
        "realized_margin_cents": 50000,
        "current_stage": "recognized_revenue",
    })
    context = result["aggregate_revenue_context"]
    assert context["reported_recognized_revenue_cents"] == 120000
    assert context["reported_realized_margin_cents"] == 50000
    assert context["attributed_to_reviewed_opportunities_cents"] is None
    assert context["verification_status"] == "SOURCE_INPUT_NOT_INDEPENDENTLY_REVERIFIED"
    assert result["review_queue"][0]["revenue_realized_cents"] is None


def test_false_actual_revenue_flag_suppresses_financial_claims():
    result = review(funnel={"recognized_revenue_cents": 999999999, "realized_margin_cents": 100})
    context = result["aggregate_revenue_context"]
    assert context["reported_recognized_revenue_cents"] is None
    assert context["reported_realized_margin_cents"] is None


def test_schema_contracts_enforced():
    kwargs = fixture()
    kwargs["offer_book"]["schema_version"] = "unknown"
    with pytest.raises(ValueError, match="canonical commercial offer book"):
        build_commercial_growth_review(**kwargs)
    kwargs = fixture()
    kwargs["funnel"]["schema_version"] = "unknown"
    with pytest.raises(ValueError, match="canonical commercial funnel"):
        build_commercial_growth_review(**kwargs)


def test_bounded_inputs():
    kwargs = fixture()
    kwargs["observations"]["observations"] = [signal(signal_id=f"signal:{i}") for i in range(501)]
    with pytest.raises(ValueError, match="no more than 500"):
        build_commercial_growth_review(**kwargs)
    kwargs = fixture()
    kwargs["offer_book"]["targets"] = [offer(identity=f"p-{i}") for i in range(501)]
    with pytest.raises(ValueError, match="<=500"):
        build_commercial_growth_review(**kwargs)


def test_deterministic_rank_and_side_effect_contract():
    rows = [
        offer("b", demand="UNKNOWN"),
        offer("a", demand="VERIFIED", existing=True),
        offer("c", ready=False),
    ]
    result = review(offers=rows)
    assert [x["canonical_prospect_id"] for x in result["review_queue"]] == ["a", "b", "c"]
    assert result["database_writes"] is False
    assert result["external_actions"] is False
    assert result["agent_owner_changes"] is False
    assert result["model_training"] is False
    assert result["autonomous_pricing"] is False


def test_actor_packet_is_safe_unlinked_research_not_fake_buyer():
    actor = {
        "community:abc": {
            "signal_id": "community:abc",
            "source": "community_intent",
            "status": "unresolved",
            "niche": "roofing",
            "url": "https://source.example.invalid/post",
            "raw": {
                "evidence_urls": ["https://source.example.invalid/post"],
                "community_intent": {
                    "author": "Not a verified buyer",
                    "pain_points": ["storm cleanup"],
                },
            },
        }
    }
    kwargs = fixture()
    kwargs["observations"] = actor
    result = build_commercial_growth_review(**kwargs)
    assert result["source_counts"]["unlinked_research_observations"] == 1
    assert result["source_counts"]["linked_research_observations"] == 0
    assert result["unlinked_signal_review"][0]["review_reason"] == "canonical_prospect_id_required"
    assert "Not a verified buyer" not in str(result)


def test_source_freshness_detects_stale_and_fresh_snapshots():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    kwargs = fixture()
    kwargs["offer_book"]["generated_at"] = "2026-09-30T00:00:00Z"
    kwargs["funnel"]["generated_at"] = "2026-10-18T18:00:00Z"
    result = build_commercial_growth_review(**kwargs, now=now)
    freshness = result["source_freshness"]
    assert freshness["offer_book"]["status"] == "STALE"
    assert freshness["funnel"]["status"] == "FRESH"
    assert freshness["requires_refresh_before_commercial_use"] is True
    kwargs["offer_book"]["generated_at"] = "2026-10-18T10:00:00Z"
    result = build_commercial_growth_review(**kwargs, now=now)
    assert result["source_freshness"]["requires_refresh_before_commercial_use"] is False


def test_unknown_invalid_and_future_freshness_do_not_pass():
    from datetime import datetime, timezone
    now = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
    kwargs = fixture()
    kwargs["offer_book"]["generated_at"] = "not a date"
    kwargs["funnel"]["generated_at"] = "2026-10-21T00:00:00Z"
    result = build_commercial_growth_review(**kwargs, now=now)
    assert result["source_freshness"]["offer_book"]["status"] == "INVALID"
    assert result["source_freshness"]["funnel"]["status"] == "FUTURE"
    assert result["source_freshness"]["requires_refresh_before_commercial_use"] is True
    with pytest.raises(ValueError, match="timezone"):
        build_commercial_growth_review(**kwargs, now=datetime(2026, 10, 19, 12))
