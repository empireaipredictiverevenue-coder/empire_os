import pytest

from empire_os.legal_mass_tort_intelligence import (
    LegalMarketSignal,
    build_legal_market_brief,
    legacy_mass_tort_agent_status,
)


def signal(signal_type, source, ref, **kwargs):
    return LegalMarketSignal(
        vertical="roundup",
        signal_type=signal_type,
        source=source,
        source_ref=ref,
        observed_at="2026-09-21T10:00:00Z",
        **kwargs,
    )


def test_b2b_market_evidence_can_create_opportunity_brief():
    brief = build_legal_market_brief(
        "roundup",
        [
            signal(
                "court_activity",
                "courtlistener",
                "court:1",
                signal_count=12,
            ),
            signal(
                "firm_capacity",
                "state_bar",
                "bar:firm-a",
                firm_name="Firm A",
            ),
            signal(
                "search_demand",
                "search_fabric",
                "search:roundup",
                signal_count=18,
            ),
        ],
    )
    assert brief.opportunity_state == "market_opportunity_observed"
    assert brief.firm_count == 1
    assert brief.court_activity_count == 12
    assert brief.individual_consumer_targeting is False


def test_individual_sensitive_consumer_targeting_is_rejected():
    row = signal(
        "search_demand",
        "search_fabric",
        "search:1",
        individual_consumer_targeting=True,
    )
    with pytest.raises(ValueError, match="individual consumer targeting prohibited"):
        row.validate()


def test_legacy_agent_is_explicitly_non_authoritative():
    status = legacy_mass_tort_agent_status()
    assert status["authoritative"] is False
    assert "individual_sensitive_consumer_targeting" in status["retired_reasons"]
