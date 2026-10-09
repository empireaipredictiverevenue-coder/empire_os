from datetime import datetime, timedelta, timezone
from empire_os.commercial_social_intent import build_social_intent_review


NOW = datetime(2026, 10, 9, 21, tzinfo=timezone.utc)


def signal(
    platform, source_url, *,
    score=66, evidence_urls=None, at=None,
):
    return {
        "source": platform + "_intent",
        "url": source_url,
        "status": "unresolved",
        "lead_score": score,
        "niche": "roofing",
        "raw": {
            "evidence_urls": evidence_urls or [],
            "community_intent": {
                "source": platform,
                "url": source_url,
                "intent_score": score,
                "observed_at": (at or NOW).isoformat(),
                "niche": "roofing",
                "evidence_urls": evidence_urls or [],
                "text": "need 10 more calls",
            }
        },
    }


def known():
    return [{
        "entity_key": "roofing-pro",
        "identity_domains": ["roofingpros.com"],
        "outbound_authorized": False,
        "stage": "RESEARCH_ONLY",
    }]


def sources():
    return {
        "community": {
            "observed_at": NOW.isoformat(),
            "source_status": {
                "reddit": {"ok": True, "accepted_observations": 2},
                "linkedin": {"ok": False, "accepted_observations": 0,
                             "engine": "none"},
            },
        },
        "linkedin": {
            "generated_at": NOW.isoformat(),
            "candidate_count": 9,
            "observed_signal_candidate_count": 3,
            "resolved_decision_maker_count": 0,
            "verified_contact_count": 0,
            "human_review_ready_count": 0,
        },
    }


def test_social_signal_without_company_is_not_an_outreach_contact():
    d = {
        "a": signal(
            "reddit",
            "https://www.reddit.com/r/roofing/comments/post123/need-leads",
            score=95,
        ),
        "b": signal(
            "linkedin",
            "https://www.linkedin.com/posts/marketeer_leadgeneration",
            score=72,
        ),
    }
    r = build_social_intent_review(d, known(), **sources(), now=NOW)
    assert r["sources"] == {"reddit_intent": 1, "linkedin_intent": 1}
    assert r["signals_with_potential_company_link_count"] == 0
    assert r["verified_poster_to_company_identity_count"] == 0
    assert r["verified_commercial_buying_intent_count"] == 0
    assert r["outbound_sent"] is False
    assert r["execution_authority"] == "NONE"
    assert len(r["identity_unverified_review_queue"]) == 2
    assert r["linkedin_and_reddit_runtime"]["linkedin_last_collector"]["ok"] is False
    assert r["linkedin_and_reddit_runtime"]["linkedin_department"]["verified_contact_count"] == 0


def test_even_explicit_website_is_only_a_potential_citation_match():
    d = {
        "a": signal(
            "reddit", "https://reddit.com/r/roofing/comments/xyz/post",
            evidence_urls=["https://www.roofingpros.com/estimate"],
        )
    }
    r = build_social_intent_review(d, known(), now=NOW)
    assert r["signals_with_potential_company_link_count"] == 1
    candidate = r["identity_unverified_review_queue"][0]
    assert candidate["potential_company_matches"] == [{
        "entity_key": "roofing-pro",
        "evidence_website": "https://www.roofingpros.com/estimate",
    }]
    assert candidate["poster_company_identity_verified"] is False
    assert candidate["buyer_purchase_intent_verified"] is False
    assert candidate["outbound_authorized"] is False
    assert candidate["next_action"] == "REVIEW_EXPLICIT_EXTERNAL_COMPANY_LINK"


def test_social_domains_do_not_match_from_the_post_url_itself():
    d = {
        "a": signal(
            "linkedin",
            "https://linkedin.com/posts/roofingpros_leads-abc",
            evidence_urls=["https://linkedin.com/company/roofingpros"],
        )
    }
    r = build_social_intent_review(d, known(), now=NOW)
    assert r["signals_with_potential_company_link_count"] == 0


def test_reject_stale_and_future_observations():
    d = {
        "old": signal("reddit", "https://reddit.com/r/a/old",
                      at=NOW-timedelta(days=22)),
        "future": signal("linkedin", "https://linkedin.com/posts/a_future",
                         at=NOW+timedelta(hours=3)),
        "recent": signal("reddit", "https://reddit.com/r/b/new"),
    }
    r = build_social_intent_review(d, known(), now=NOW)
    assert r["evidence_bearing_recent_signal_count"] == 1
    assert r["stale_or_unproven_observation_count"] == 2


def test_irrelevant_low_score_does_not_become_a_buying_signal():
    d={"x":signal("linkedin","https://linkedin.com/posts/advice-foo", score=12)}
    r=build_social_intent_review(d, known(), now=NOW)
    assert r["evidence_bearing_recent_signal_count"] == 0
    assert r["verified_commercial_buying_intent_count"] == 0


def test_deduped_bounded_reddit_and_linkedin_review():
    signals={}
    for i in range(28):
        channel="reddit" if i%2 else "linkedin"
        signals[str(i)]=signal(channel,f"https://{channel}.com/posts/{i}",score=50+i)
    r=build_social_intent_review(signals, known(), now=NOW)
    assert len(r["identity_unverified_review_queue"])==16
    assert r["review_queue_truncated"] is True
    assert {x["channel"] for x in r["identity_unverified_review_queue"]}=={"reddit","linkedin"}
    assert all(x["outbound_authorized"] is False for x in r["identity_unverified_review_queue"])
