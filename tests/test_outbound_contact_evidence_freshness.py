from datetime import datetime, timezone

from empire_os.outbound_contact_evidence_freshness import (
    evaluate_contact_evidence_freshness,
)


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_current_contact_evidence_is_valid():
    result = evaluate_contact_evidence_freshness(
        {
            "source_kind": "official_site_current",
            "verified_at": "2026-10-01T12:00:00+00:00",
        },
        now=NOW,
    )
    assert result["decision"] == "VALID"
    assert result["trust_multiplier"] == 1.0


def test_stale_contact_evidence_requires_reverification():
    result = evaluate_contact_evidence_freshness(
        {
            "source_kind": "official_site_current",
            "verified_at": "2026-09-01T12:00:00+00:00",
        },
        now=NOW,
    )
    assert result["decision"] == "REVERIFY"
    assert result["reason"] == "recipient_evidence_stale"


def test_hard_bounce_after_verification_is_hold():
    result = evaluate_contact_evidence_freshness(
        {
            "source_kind": "official_site_current",
            "verified_at": "2026-10-01T12:00:00+00:00",
            "last_hard_bounce_at": "2026-10-02T12:00:00+00:00",
        },
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert "hard_bounce_after_verification" in result["hard_holds"]
    assert result["trust_multiplier"] == 0.0


def test_opt_out_after_verification_is_hold():
    result = evaluate_contact_evidence_freshness(
        {
            "source_kind": "public_record",
            "verified_at": "2026-10-01T12:00:00+00:00",
            "last_opt_out_at": "2026-10-03T08:00:00+00:00",
        },
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert "opt_out_after_verification" in result["hard_holds"]


def test_missing_verification_timestamp_requires_reverification():
    result = evaluate_contact_evidence_freshness(
        {"source_kind": "official_site_current"},
        now=NOW,
    )
    assert result["decision"] == "REVERIFY"
    assert result["trust_multiplier"] == 0.0


def test_recent_success_can_improve_near_expiry_confidence_but_not_above_one():
    result = evaluate_contact_evidence_freshness(
        {
            "source_kind": "official_site_current",
            "verified_at": "2026-09-21T12:00:00+00:00",
            "last_successful_delivery_at": "2026-10-02T12:00:00+00:00",
        },
        now=NOW,
    )
    assert result["decision"] == "VALID"
    assert result["trust_multiplier"] <= 1.0
