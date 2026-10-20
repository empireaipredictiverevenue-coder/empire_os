from datetime import datetime, timedelta, timezone
from empire_os.meta_social_opportunity_research import SCHEMA, review_packet

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=timezone.utc)


def obs(platform="facebook_group", kind="aggregate_demand", us_zip="85001",
        source_url="https://www.facebook.com/groups/hvac-community/posts/123",
        subject_type="aggregated", niche="hvac", **extra):
    return {
        "platform": platform, "kind": kind, "us_zip": us_zip, "niche": niche,
        "source_url": source_url, "subject_type": subject_type,
        "rights_status": "verified_permitted", "access_method": "authorised_manual_review",
        "observed_at": NOW.isoformat(), **extra,
    }


def review(rows):
    return review_packet({"schema_version": SCHEMA, "observations": rows}, now=NOW)


def test_cross_platform_market_hypothesis_without_claiming_sales():
    data = review([
        obs(),
        obs(platform="instagram", kind="business_supply", subject_type="business",
            source_url="https://www.instagram.com/hvac_company/"),
    ])
    assert data["accepted_observations"] == 2
    assert len(data["market_hypotheses"]) == 1
    hypothesis = data["market_hypotheses"][0]
    assert hypothesis["niche"] == "hvac" and hypothesis["us_zip"] == "85001"
    assert not hypothesis["revenue_verified"] and not hypothesis["outbound_authorized"]
    assert hypothesis["verified_buyer_count"] == 0
    assert data["live_meta_queries"] == 0 and data["database_writes"] is False


def test_refuses_personal_identifiers_and_unverified_rights():
    personal = obs(person_name="Private Individual", phone="555-0100")
    rights = obs(rights_status="unknown", source_url="https://facebook.com/groups/a/posts/456")
    data = review([personal, rights])
    assert data["accepted_observations"] == 0
    assert data["held_counts"]["personal_or_raw_content_field"] == 1
    assert data["held_counts"]["source_rights_not_verified"] == 1


def test_no_cross_zip_or_personal_demand_matching():
    data = review([
        obs(),
        obs(kind="business_supply", subject_type="business", us_zip="85002",
            source_url="https://facebook.com/marketplace/item/987"),
        obs(kind="aggregate_demand", subject_type="person",
            source_url="https://facebook.com/groups/a/posts/654"),
    ])
    assert data["market_hypotheses"] == []
    assert data["held_counts"]["consumer_or_unverified_subject"] == 1


def test_no_stale_or_fake_or_duplicate_sources():
    older = (NOW - timedelta(days=22)).isoformat()
    data = review([
        obs(), obs(), obs(observed_at=older,
            source_url="https://facebook.com/groups/a/posts/old"),
        obs(source_url="https://facebook.com.attacker.example/groups/a/posts/123"),
        obs(source_url="http://facebook.com/groups/a/posts/789"),
    ])
    assert data["accepted_observations"] == 1
    assert data["held_counts"]["duplicate_observation"] == 1
    assert data["held_counts"]["stale_or_invalid_time"] == 1
    assert data["held_counts"]["untrusted_source_url"] == 2
