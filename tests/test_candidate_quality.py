import pytest

from empire_os.candidate_quality import (
    CandidateQualityError,
    assess_candidate,
    enforce_candidate_quality,
)
from empire_os.lead_sources import LeadCandidate


def test_accepts_identifiable_business_candidate():
    candidate = LeadCandidate(
        name="Real Roofing LLC",
        phone="512-555-0101",
        niche="roofing",
        metro="Austin",
        source="overpass_osm",
        url="https://www.openstreetmap.org/node/123",
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is True
    assert decision.entity_kind == "business"
    assert decision.source_role == "identity_or_direct"
    assert decision.reason_codes == ()
    assert decision.confidence > 0


def test_rejects_placeholder_business_name():
    candidate = LeadCandidate(
        name="NA",
        niche="general_contractor",
        metro="NYC",
        source="overpass_osm",
        url="https://example.test/record/1",
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert "placeholder_name" in decision.reason_codes


def test_rejects_signal_source_until_identity_is_resolved():
    candidate = LeadCandidate(
        name="Bank of Oklahoma, N.A.",
        niche="water_damage_restoration",
        metro="USA",
        source="courtlistener",
        url="https://www.courtlistener.com/example",
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert decision.entity_kind == "signal"
    assert "signal_requires_identity_resolution" in decision.reason_codes


def test_rejects_nyc_permit_as_direct_prospect():
    candidate = LeadCandidate(
        name="Example Property Owner LLC (Queens)",
        phone="212-555-0101",
        niche="roofing",
        metro="NYC",
        source="permits_nyc",
        url="https://example.test/permit/123",
        raw={"job__": "123"},
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert decision.source_role == "signal"
    assert "signal_requires_identity_resolution" in decision.reason_codes


def test_rejects_candidate_without_identity_evidence():
    candidate = LeadCandidate(
        name="Real Roofing LLC",
        niche="roofing",
        metro="Austin",
        source="manual_import",
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert "insufficient_identity_evidence" in decision.reason_codes


def test_enforcement_fails_closed():
    candidate = LeadCandidate(
        name="Unknown",
        niche="roofing",
        metro="Austin",
        source="manual_import",
        phone="512-555-0101",
    )

    with pytest.raises(CandidateQualityError):
        enforce_candidate_quality(candidate)


def test_rejects_reddit_json_as_signal():
    candidate = LeadCandidate(
        name="u/example (NYC)",
        niche="plumbing",
        metro="NYC",
        source="reddit_json",
        url="https://old.reddit.com/r/example/123",
        raw={"id": "123"},
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert decision.source_role == "signal"
    assert "signal_requires_identity_resolution" in decision.reason_codes


def test_rejects_chicago_permit_as_signal():
    candidate = LeadCandidate(
        name="Chicago chicago_permits #123",
        niche="general_contractor",
        metro="CHI",
        source="chicago_permits",
        url="https://data.cityofchicago.org",
        raw={"permit_": "123"},
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert decision.source_role == "signal"
    assert "signal_requires_identity_resolution" in decision.reason_codes


def test_rejects_unclassified_source_fail_closed():
    candidate = LeadCandidate(
        name="Real Roofing LLC",
        phone="512-555-0101",
        niche="roofing",
        metro="Austin",
        source="mystery_source",
        url="https://example.test/business/123",
    )

    decision = assess_candidate(candidate)

    assert decision.accepted is False
    assert decision.source_role == "unknown"
    assert "unclassified_source_role" in decision.reason_codes
