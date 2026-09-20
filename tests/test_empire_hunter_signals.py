import pytest

from empire_os.hunter.signals import (
    derive_temporal_signals,
    outcome_signal,
)


def test_leadership_and_contact_changes_create_evidence_backed_signals():
    signals = derive_temporal_signals(
        entity_id="entity-1",
        observed_at="2026-09-20T14:30:00Z",
        previous={
            "people": [{"name": "Old Owner", "title": "Owner"}],
            "emails": ["old@example.com"],
            "services": ["roof repair"],
            "domain": "example.com",
        },
        current={
            "people": [{"name": "New Owner", "title": "President"}],
            "emails": ["new@example.com"],
            "services": ["roof repair", "solar"],
            "domain": "example.com",
        },
        evidence_refs=["site:before", "site:after"],
    )

    types = {item.signal_type for item in signals}
    assert "leadership_change" in types
    assert "contact_surface_change" in types
    assert "service_expansion" in types
    assert all(item.evidence_refs for item in signals)
    assert all(item.execution_authority == "none" for item in signals)


def test_domain_change_is_high_confidence():
    signals = derive_temporal_signals(
        entity_id="entity-1",
        observed_at="2026-09-20T14:30:00Z",
        previous={"domain": "old.example.com"},
        current={"domain": "new.example.com"},
        evidence_refs=["dns:1", "site:2"],
    )

    signal = next(
        item for item in signals
        if item.signal_type == "domain_change"
    )
    assert signal.confidence == 0.95


def test_first_observation_does_not_fake_change_signal():
    signals = derive_temporal_signals(
        entity_id="entity-1",
        observed_at="2026-09-20T14:30:00Z",
        previous=None,
        current={
            "people": [{"name": "Owner", "title": "Owner"}],
            "emails": ["owner@example.com"],
            "services": ["roof repair"],
            "domain": "example.com",
        },
        evidence_refs=["site:1"],
    )

    assert signals == ()


def test_signal_requires_provenance():
    with pytest.raises(ValueError, match="evidence refs"):
        derive_temporal_signals(
            entity_id="entity-1",
            observed_at="2026-09-20T14:30:00Z",
            previous={"domain": "old.com"},
            current={"domain": "new.com"},
            evidence_refs=[],
        )


def test_verified_bounce_creates_degradation_signal_not_revenue():
    signal = outcome_signal(
        entity_id="entity-1",
        event_type="bounced",
        observed_at="2026-09-20T14:30:00Z",
        evidence_refs=["outbound-event:1"],
        email="person@example.com",
    )

    assert signal.signal_type == "contact_degraded"
    assert signal.strength == 0.9
    assert signal.payload["commercial_revenue"] is False
