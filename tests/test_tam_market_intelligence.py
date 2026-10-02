import pytest

from empire_os.tam_market_intelligence import (
    MarketEntityObservation,
    TamCountEvidence,
    build_tam_market_intelligence,
)


def observed(
    entity_id,
    *,
    industry="roofing",
    country="US",
    source="registry:1",
    tenant="tenant-1",
):
    return MarketEntityObservation(
        tenant_id=tenant,
        entity_id=entity_id,
        company_name=f"Company {entity_id}",
        industry=industry,
        country_code=country,
        source_ref=source,
        observed_at="2026-10-02T12:00:00+00:00",
    )


def tam(count, *, industry="roofing", country="US", tenant="tenant-1"):
    return TamCountEvidence(
        tenant_id=tenant,
        industry=industry,
        country_code=country,
        entity_count=count,
        source_ref="official_registry:tam:1",
        observed_at="2026-10-02T10:00:00+00:00",
    )


def test_observed_roster_is_not_promoted_to_tam():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[observed("e1"), observed("e2")],
        active_industries=["roofing"],
        active_countries=["US"],
    )
    scope = result["market_scopes"][0]
    assert scope["observed_entity_count"] == 2
    assert scope["tam_entity_count"] is None
    assert scope["tam_state"] == "UNKNOWN"
    assert scope["coverage_ratio"] is None
    assert result["tam_inferred_from_observed_roster"] is False


def test_explicit_verified_tam_is_kept_separate_from_coverage():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[observed("e1"), observed("e2")],
        active_industries=["roofing"],
        active_countries=["US"],
        tam_evidence=[tam(10)],
    )
    scope = result["market_scopes"][0]
    assert scope["observed_entity_count"] == 2
    assert scope["tam_entity_count"] == 10
    assert scope["tam_state"] == "VERIFIED"
    assert scope["coverage_ratio"] == 0.2


def test_new_industry_and_country_emit_research_only_classes():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[
            observed(
                "e1",
                industry="solar",
                country="GB",
                source="companies_house:1",
            )
        ],
        active_industries=["roofing"],
        active_countries=["US"],
    )
    classes = {
        row["opportunity_class"]: row
        for row in result["opportunity_classes"]
    }
    assert set(classes) == {
        "new_industry",
        "new_country",
        "new_industry_country",
    }
    for row in classes.values():
        assert row["decision"] == "research"
        assert row["buyer_intent_proven"] is False
        assert row["demand_proven"] is False
        assert row["commercial_terms_verified"] is False
        assert row["revenue_verified"] is False
        assert row["execution_authority"] == "none"


def test_existing_industry_country_creates_no_expansion_opportunity():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[observed("e1")],
        active_industries=["roofing"],
        active_countries=["US"],
    )
    assert result["opportunity_classes"] == []


def test_duplicate_entity_observations_dedupe_and_retain_provenance():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[
            observed("e1", source="registry:1"),
            observed("e1", source="search:1"),
        ],
    )
    scope = result["market_scopes"][0]
    assert scope["observed_entity_count"] == 1
    assert scope["entities"][0]["evidence_refs"] == [
        "registry:1",
        "search:1",
    ]


def test_tam_below_observed_coverage_is_rejected():
    with pytest.raises(
        ValueError,
        match="verified TAM count cannot be below observed",
    ):
        build_tam_market_intelligence(
            tenant_id="tenant-1",
            observations=[observed("e1"), observed("e2")],
            tam_evidence=[tam(1)],
        )


def test_mixed_tenant_input_fails_closed():
    with pytest.raises(ValueError, match="mixed tenant"):
        build_tam_market_intelligence(
            tenant_id="tenant-1",
            observations=[observed("e1", tenant="tenant-2")],
        )


def test_top_level_authority_and_commercial_flags_stay_false():
    result = build_tam_market_intelligence(
        tenant_id="tenant-1",
        observations=[observed("e1", industry="solar", country="GB")],
    )
    assert result["mode"] == "OBSERVE"
    assert result["buyer_intent_inferred"] is False
    assert result["demand_inferred"] is False
    assert result["pricing_inferred"] is False
    assert result["revenue_inferred"] is False
    assert result["prospect_created"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"
