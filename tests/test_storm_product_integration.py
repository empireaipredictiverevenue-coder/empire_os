from datetime import datetime, timedelta, timezone

import pytest

from empire_os.storm_product_integration import (
    AffectedSubject,
    BuyerProductMatch,
    Evidence,
    StormEvent,
    SubjectKind,
    TruthClass,
    assess_storm_product,
)


def ev(ref, now):
    return Evidence("tenant-a", ref, "weather", now - timedelta(hours=1), now + timedelta(hours=2))


def test_storm_assessment_is_observe_only_and_founder_gated():
    now = datetime.now(timezone.utc)
    event = StormEvent("tenant-a", "storm-1", "hail", "severe", now - timedelta(hours=3), now - timedelta(hours=1), TruthClass.OBSERVED, (ev("event", now),))
    subject = AffectedSubject("tenant-a", "storm-1", "property-1", SubjectKind.PROPERTY, "roofing", "tx-dfw", 0.9, 0.8, (ev("subject", now),))
    match = BuyerProductMatch("tenant-a", "buyer-1", "storm_leads", "roofing", "tx-dfw", (ev("buyer", now),))

    result = assess_storm_product(event, subject, match, now=now)

    assert result.execution_authority == "OBSERVE"
    assert result.commercial_ready is False
    assert result.economics is None
    assert "founder_commercial_authority_required" in result.blockers
    assert any(value.endswith("_evidence_required") for value in result.blockers)


def test_storm_assessment_rejects_cross_tenant_subject():
    now = datetime.now(timezone.utc)
    event = StormEvent("tenant-a", "storm-1", "hail", "severe", now - timedelta(hours=2), now - timedelta(hours=1), TruthClass.OBSERVED, (ev("event", now),))
    foreign = Evidence("tenant-b", "subject", "weather", now - timedelta(hours=1), now + timedelta(hours=1))
    subject = AffectedSubject("tenant-b", "storm-1", "property-1", SubjectKind.PROPERTY, "roofing", "tx-dfw", 0.8, 0.8, (foreign,))
    match = BuyerProductMatch("tenant-a", "buyer-1", "storm_leads", "roofing", "tx-dfw", (ev("buyer", now),))

    with pytest.raises(ValueError, match="tenant mismatch"):
        assess_storm_product(event, subject, match, now=now)
