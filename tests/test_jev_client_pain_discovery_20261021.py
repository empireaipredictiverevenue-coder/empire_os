from datetime import datetime, timedelta, timezone

import pytest

from empire_os.jev_client_pain_discovery import discover_client_pains


NOW = datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc)


def row(url="https://www.reddit.com/r/roofing/comments/proof",
        title="I own a roofing business",
        text="We need more leads this week. Looking for an agency.",
        source="reddit", age_days=1, **extra):
    return {
        "source": source, "url": url, "title": title, "text": text,
        "niche": "roofing",
        "observed_at": (NOW - timedelta(days=age_days)).isoformat(),
        **extra,
    }


def test_specific_direct_request_is_review_only_not_verified_lead():
    output = discover_client_pains([row()], now=NOW)
    assert output["observations_with_pain_or_topic"] == 1
    r = output["items"][0]
    assert r["review_lane"] == "REVIEW_IDENTITY"
    assert r["pain_hypotheses"] == ["inconsistent_lead_flow"]
    assert "predictive_revenue_demand_engine" in r["matched_offers_to_validate"]
    assert r["unverified_identity"] is True
    assert r["unverified_commercial_need"] is True
    assert r["outreach_authorized"] is False
    assert output["prospects_verified"] == 0
    assert output["outbound_sent"] == 0
    assert output["execution_authority"] == "none"
    assert "private_evidence_url" not in r


def test_private_owner_queue_has_source_link_but_no_raw_text_or_contact():
    r = discover_client_pains([row()], now=NOW, include_private_source_links=True)["items"][0]
    assert r["private_evidence_url"].endswith("/r/roofing/comments/proof")
    assert "title" not in r
    assert "text" not in r
    assert "author" not in r


@pytest.mark.parametrize("description", [
    "We're hiring a sales specialist. We need more leads this week.",
    "Our clients need more leads. Book a demo with our agency to help.",
    "Here's how to fix your problem: stop losing leads with our platform.",
])
def test_hiring_and_marketing_copy_cannot_become_client(description):
    result = discover_client_pains([row(text=description)], now=NOW)
    assert result["review_lane_counts"].get("REVIEW_IDENTITY", 0) == 0


def test_stale_source_and_fake_identity_flag_cannot_upgrade():
    result = discover_client_pains([
        row(age_days=120, first_party_verified=True,
            canonical_identity_verified=True, repeated_signal_count=100),
    ], now=NOW)
    assert result["items"][0]["review_lane"] == "MONITOR_UNVERIFIED"
    assert result["items"][0]["unverified_identity"] is True


def test_dedup_url_fragment_and_collapse_same_source():
    result = discover_client_pains([
        row(url="https://reddit.com/r/roofing/comments/proof#x"),
        row(url="https://www.reddit.com/r/roofing/comments/proof#y"),
    ], now=NOW)
    assert result["observations_with_pain_or_topic"] == 1
    assert result["quality_counters"]["duplicate_source"] == 1


def test_reject_cross_platform_forgery_without_promoting():
    result = discover_client_pains([
        row(url="https://linkedin.com/posts/other", source="reddit"),
    ], now=NOW)
    assert result["items"] == []
    assert result["quality_counters"]["invalid_or_untrusted_source"] == 1


def test_public_rfp_is_valid_source_but_never_first_party_verified():
    candidate = row(
        source="public_rfp",
        url="https://procurement.example.org/tender/127",
        text="We need help automating manual data entry. Looking for an automation specialist.",
    )
    result = discover_client_pains([candidate], now=NOW)
    assert result["items"][0]["unverified_identity"] is True
    assert "manual_operations_overload" in result["items"][0]["pain_hypotheses"]


def test_generic_keywords_are_topic_only_not_concrete_pain():
    result = discover_client_pains([
        row(text="SEO, CRM and leads are subjects in our weekly newsletter."),
    ], now=NOW)
    assert result["pain_counts"] == {}
    assert result["items"] == []
    assert result["quality_counters"]["no_problem_evidence"] == 1


def test_500_signal_limit_and_future_signal_gate():
    with pytest.raises(ValueError, match="bounded"):
        discover_client_pains([row()] * 501, now=NOW)
    r = discover_client_pains([row(age_days=-2)], now=NOW)
    assert r["items"][0]["review_lane"] == "MONITOR_UNVERIFIED"
    assert r["items"][0]["freshness"] == "future_rejected"


def test_same_individual_signal_can_have_two_problems_without_double_counting():
    r = discover_client_pains([row(
        text="We need more leads this week. Our manual follow-up is too slow. Looking for an agency."
    )], now=NOW)
    assert r["observations_with_pain_or_topic"] == 1
    assert len(r["items"][0]["pain_hypotheses"]) >= 2


def test_canonical_adapter_keeps_social_only_and_strips_untrusted_proof():
    from empire_os.jev_client_pain_discovery import observations_from_existing_canonical_inbox
    s = row(first_party_verified=True, canonical_identity_verified=True)
    result = observations_from_existing_canonical_inbox({
        "social": {"source": "reddit_intent", "status": "unresolved",
                   "execution_authority": "none", "entity_id": None,
                   "prospect_id": None, "raw": {"community_intent": s}},
        "permit": {"source": "permits_nyc", "status": "unresolved",
                   "execution_authority": "none", "raw": {"community_intent": s}},
        "buyer": {"source": "reddit_intent", "status": "resolved",
                  "execution_authority": "none", "raw": {"community_intent": s}},
    })
    assert len(result) == 1
    assert result[0]["source"] == "reddit"
    assert "first_party_verified" not in result[0]
    assert "canonical_identity_verified" not in result[0]
    assert discover_client_pains(result, now=NOW)["prospects_verified"] == 0



def test_explicit_no_soliciting_does_not_enter_identity_queue():
    x = discover_client_pains([row(
        text="We need more clients. Looking for an agency. No soliciting please.",
    )], now=NOW)
    assert x["items"][0]["review_lane"] == "NO_SOLICITATION"
    assert x["items"][0]["no_solicitation"] is True
    assert x["items"][0]["evidence_priority"] == 0


def test_recent_realistic_operational_demand_language_is_specific():
    r = discover_client_pains([row(
        text="Our enquiries can still be unpredictable; we need one more consistent source of leads."
    )], now=NOW)
    assert "inconsistent_lead_flow" in r["items"][0]["pain_hypotheses"]



def test_self_reported_but_not_buying_is_only_pain_hypothesis_review():
    result = discover_client_pains([row(
        title="I own a marketing agency",
        text="No new clients for 11 months. People are not booking sales calls.",
    )], now=NOW)
    assert result["items"][0]["review_lane"] == "REVIEW_PAIN_HYPOTHESIS"
    assert result["items"][0]["unverified_commercial_need"] is True
    assert result["items"][0]["outreach_authorized"] is False



def test_generic_topic_cannot_be_identity_review_without_specific_pain():
    r = discover_client_pains([row(
        title="I own a business", text="We need help with our CRM."
    )], now=NOW)
    assert r["review_lane_counts"].get("REVIEW_IDENTITY", 0) == 0


def test_saas_first_users_and_churn_map_to_usable_research_hypotheses():
    r = discover_client_pains([row(
        source="reddit", url="https://www.reddit.com/r/SaaS/comments/test",
        title="Struggling to get my first users",
        text="I own a SaaS startup. No meaningful signups and users quietly disappear after a week.",
        niche="saas",
    )], now=NOW)
    pains = r["items"][0]["pain_hypotheses"]
    assert "no_initial_saas_users" in pains
    assert "saas_retention_loss" in pains
    assert r["items"][0]["outreach_authorized"] is False
