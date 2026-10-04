from empire_os.intent_seed_bridge import build_intent_seed_records


def _signal(
    *,
    signal_id="sig-1",
    source="reddit_intent",
    status="unresolved",
    niche="roofing",
    score=82,
    band="high",
    evidence_urls=None,
):
    return {
        "signal_id": signal_id,
        "status": status,
        "last_seen_at": "2026-10-04T08:00:00+00:00",
        "source": source,
        "niche": niche,
        "url": "https://www.reddit.com/r/roofing/comments/example/",
        "lead_score": score,
        "raw": {
            "entity_kind": "signal",
            "outreach_authority": "none",
            "evidence_urls": list(
                evidence_urls
                or ["https://3pointcontracting.com/roof-replacement/"]
            ),
            "community_intent": {
                "source": "reddit",
                "url": (
                    "https://www.reddit.com/r/roofing/comments/example/"
                ),
                "title": "Need more qualified roofing appointments",
                "text": (
                    "We need 2-4 more qualified appointments per week. "
                    "Google Ads have not been consistently profitable."
                ),
                "observed_at": "2026-10-04T07:30:00+00:00",
                "niche": niche,
                "intent_score": score,
                "intent_band": band,
                "pain_points": [
                    "lead_generation",
                    "revenue_growth",
                ],
            },
        },
    }


def test_high_intent_roofing_signal_becomes_review_only_scout_seed():
    rows = build_intent_seed_records({"sig-1": _signal()})

    assert len(rows) == 1
    row = rows[0]
    assert row["business_name"] == ""
    assert row["website"] == (
        "https://3pointcontracting.com/roof-replacement/"
    )
    assert row["icp_profile_key"] == (
        "intent_driven_home_service_growth"
    )
    assert row["seed_intent_signal_id"] == "sig-1"
    assert row["seed_intent_score"] == 82
    assert row["seed_intent_band"] == "high"
    assert row["seed_intent_pain_points"] == [
        "lead_generation",
        "revenue_growth",
    ]
    assert row["outreach_authorized"] is False
    assert row["execution_authority"] == "none"


def test_social_platform_urls_are_not_promoted_as_business_seeds():
    signal = _signal(
        evidence_urls=[
            "https://www.reddit.com/r/roofing/comments/example/",
            "https://www.linkedin.com/posts/example",
        ],
    )
    assert build_intent_seed_records({"sig-1": signal}) == []


def test_low_intent_without_medium_or_high_band_is_held_back():
    signal = _signal(score=20, band="low")
    assert build_intent_seed_records({"sig-1": signal}) == []


def test_resolved_signal_is_not_reseeded():
    signal = _signal(status="resolved")
    assert build_intent_seed_records({"sig-1": signal}) == []


def test_domains_are_deduplicated_using_freshest_signal():
    newer = _signal(signal_id="newer")
    older = _signal(signal_id="older")
    older["last_seen_at"] = "2026-10-03T08:00:00+00:00"

    rows = build_intent_seed_records({
        "older": older,
        "newer": newer,
    })

    assert len(rows) == 1
    assert rows[0]["seed_intent_signal_id"] == "newer"
