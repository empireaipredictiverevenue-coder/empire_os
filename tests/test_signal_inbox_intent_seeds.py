import json

from empire_os.signal_inbox import intent_seed_records


def test_intent_signal_projects_to_review_only_home_service_seed(tmp_path):
    inbox = tmp_path / "signal_inbox.json"
    inbox.write_text(json.dumps({
        "sig-roof-1": {
            "signal_id": "sig-roof-1",
            "status": "unresolved",
            "last_seen_at": "2026-10-04T08:30:00+00:00",
            "source": "reddit_intent",
            "niche": "roofing",
            "lead_score": 86,
            "url": "https://www.reddit.com/r/Roofing/comments/example/",
            "raw": {
                "entity_kind": "signal",
                "outreach_authority": "none",
                "evidence_urls": [
                    "https://intent-roof.example/roof-replacement"
                ],
                "community_intent": {
                    "title": "Need more qualified appointments",
                    "text": (
                        "We need 2-4 more qualified appointments a week. "
                        "Google Ads has not been consistently profitable."
                    ),
                    "intent_band": "high",
                    "pain_points": [
                        "lead_generation",
                        "revenue_growth",
                    ],
                    "evidence_urls": [
                        "https://intent-roof.example/roof-replacement"
                    ],
                },
            },
        }
    }), encoding="utf-8")

    rows = intent_seed_records(inbox=inbox)

    assert len(rows) == 1
    row = rows[0]
    assert row["business_name"] == ""
    assert row["website"] == (
        "https://intent-roof.example/roof-replacement"
    )
    assert row["icp_profile_key"] == "home_service_growth_intent"
    assert row["seed_intent_signal_id"] == "sig-roof-1"
    assert row["seed_intent_score"] == 86
    assert row["seed_intent_band"] == "high"
    assert row["seed_intent_pain_points"] == [
        "lead_generation",
        "revenue_growth",
    ]
    assert row["outreach_authorized"] is False


def test_low_intent_or_missing_first_party_url_is_not_promoted(tmp_path):
    inbox = tmp_path / "signal_inbox.json"
    inbox.write_text(json.dumps({
        "low": {
            "signal_id": "low",
            "status": "unresolved",
            "last_seen_at": "2026-10-04T08:30:00+00:00",
            "source": "reddit_intent",
            "niche": "roofing",
            "lead_score": 20,
            "url": "https://reddit.com/r/Roofing/comments/low/",
            "raw": {
                "community_intent": {
                    "evidence_urls": [
                        "https://low.example/"
                    ],
                },
            },
        },
        "no-company-url": {
            "signal_id": "no-company-url",
            "status": "unresolved",
            "last_seen_at": "2026-10-04T08:31:00+00:00",
            "source": "reddit_intent",
            "niche": "roofing",
            "lead_score": 90,
            "url": "https://reddit.com/r/Roofing/comments/no-url/",
            "raw": {
                "community_intent": {
                    "evidence_urls": [],
                },
            },
        },
    }), encoding="utf-8")

    assert intent_seed_records(inbox=inbox) == []


def test_intent_seed_dedupes_same_first_party_domain(tmp_path):
    inbox = tmp_path / "signal_inbox.json"
    base = {
        "status": "unresolved",
        "source": "reddit_intent",
        "niche": "roofing",
        "lead_score": 75,
        "url": "https://reddit.com/r/Roofing/comments/example/",
        "raw": {
            "community_intent": {
                "intent_band": "high",
                "pain_points": ["lead_generation"],
            },
        },
    }
    newer = dict(base)
    newer["signal_id"] = "newer"
    newer["last_seen_at"] = "2026-10-04T09:00:00+00:00"
    newer["raw"] = {
        **base["raw"],
        "evidence_urls": ["https://same.example/path-a"],
    }
    older = dict(base)
    older["signal_id"] = "older"
    older["last_seen_at"] = "2026-10-04T08:00:00+00:00"
    older["raw"] = {
        **base["raw"],
        "evidence_urls": ["https://same.example/path-b"],
    }
    inbox.write_text(
        json.dumps({"older": older, "newer": newer}),
        encoding="utf-8",
    )

    rows = intent_seed_records(inbox=inbox)

    assert len(rows) == 1
    assert rows[0]["seed_intent_signal_id"] == "newer"
