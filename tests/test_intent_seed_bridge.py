import json

from scripts.run_buyer_acquisition_scout import (
    _community_intent_seed_records,
)


def test_signal_inbox_intent_with_first_party_url_becomes_scout_seed(tmp_path):
    path = tmp_path / "runtime/acquisition/signal_inbox.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "sig-roof-1": {
            "signal_id": "sig-roof-1",
            "status": "unresolved",
            "source": "reddit_intent",
            "niche": "roofing",
            "lead_score": 86,
            "url": "https://reddit.com/r/Roofing/comments/example",
            "last_seen_at": "2026-10-04T08:00:00+00:00",
            "raw": {
                "entity_kind": "signal",
                "evidence_urls": [
                    "https://roofing-company.example/roof-replacement"
                ],
                "community_intent": {
                    "title": "Need more qualified appointments",
                    "text": (
                        "Google Ads has not been consistently profitable "
                        "and we need more leads."
                    ),
                    "observed_at": "2026-10-04T07:45:00+00:00",
                    "intent_score": 86,
                    "intent_band": "high",
                    "pain_points": [
                        "lead_generation",
                        "revenue_growth",
                    ],
                },
            },
        },
    }), encoding="utf-8")

    rows = _community_intent_seed_records(tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["website"] == (
        "https://roofing-company.example/roof-replacement"
    )
    assert row["icp_profile_key"] == (
        "intent_driven_home_service_growth"
    )
    assert row["seed_intent_signal_id"] == "sig-roof-1"
    assert row["intent_score"] == 86
    assert row["intent_band"] == "high"
    assert row["intent_observed_at"] == (
        "2026-10-04T07:45:00+00:00"
    )
    assert row["intent_evidence_url"] == (
        "https://reddit.com/r/Roofing/comments/example"
    )


def test_signal_without_first_party_url_remains_unpromoted(tmp_path):
    path = tmp_path / "runtime/acquisition/signal_inbox.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "sig-unknown": {
            "signal_id": "sig-unknown",
            "status": "unresolved",
            "source": "agent_research_intent",
            "niche": "roofing",
            "lead_score": 90,
            "url": "https://reddit.com/r/Roofing/comments/unknown",
            "raw": {
                "entity_kind": "signal",
                "community_intent": {
                    "title": "Need more leads",
                    "text": "Need more leads for our roofing company.",
                    "intent_score": 90,
                    "intent_band": "high",
                    "pain_points": ["lead_generation"],
                    "evidence_urls": [],
                },
            },
        },
    }), encoding="utf-8")

    assert _community_intent_seed_records(tmp_path) == []
