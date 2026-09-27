from uuid import uuid4

from empire_os.qualification_v2 import (
    build_v2_qualification_payload,
)


def test_payload_preserves_unknown_dimensions_as_none():
    prospect_id = str(uuid4())
    payload = build_v2_qualification_payload(
        {
            "id": prospect_id,
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "buy_signal_score": 0,
            "enrichment_score": 0,
        },
        scored_at="2026-09-19T11:00:00+00:00",
    )

    assert payload["prospect_id"] == prospect_id
    assert payload["scoring_version"] == "v2"
    assert payload["tier"] == "insufficient_evidence"
    assert payload["status"] == "insufficient_evidence"
    assert payload["score"] == 100.0
    assert payload["engagement_potential_score"] is None
    assert payload["enrichment_quality_score"] is None
    assert payload["evidence_confidence"] == 0.15
    assert payload["observed_dimensions"] == ["market_fit"]
    assert "engagement_potential" in payload["unknown_dimensions"]


def test_payload_records_explicitly_observed_zero():
    payload = build_v2_qualification_payload(
        {
            "id": str(uuid4()),
            "business_name": "Acme Roofing",
            "niche": "roofing",
            "buy_signal_score": 0,
        },
        buy_signal_observed=True,
        scored_at="2026-09-19T11:00:00+00:00",
    )

    assert payload["engagement_potential_score"] == 0.0
    assert "engagement_potential" in payload["observed_dimensions"]


def test_payload_keeps_entity_linkage_when_known():
    entity_id = str(uuid4())
    payload = build_v2_qualification_payload(
        {
            "id": str(uuid4()),
            "business_name": "Acme Roofing",
            "niche": "roofing",
        },
        entity_id=entity_id,
        scored_at="2026-09-19T11:00:00+00:00",
    )

    assert payload["entity_id"] == entity_id
