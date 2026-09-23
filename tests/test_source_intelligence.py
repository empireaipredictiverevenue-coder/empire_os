from empire_os.source_intelligence import (
    choose_pack_source,
    classify_runtime_health,
    commercial_source_score,
    source_plan,
    country_pack,
    research_backlog,
    source_waterfall,
)


def test_uk_solar_waterfall_prefers_certified_trade_source():
    rows = source_waterfall("GB", "solar")
    assert rows[0].source_id == "gb_recc_solar"
    assert rows[0].provenance_strength >= 90
    assert choose_pack_source("GB", "solar").source_id == "gb_recc_solar"


def test_quarantine_removes_bad_source_from_pack_choice():
    choice = choose_pack_source(
        "GB",
        "solar",
        runtime_states={"gb_recc_solar": "QUARANTINED"},
    )
    assert choice is not None
    assert choice.source_id == "gb_companies_house"


def test_health_classification_fails_closed():
    assert classify_runtime_health(runs=3, accepted=0, errors=3) == "QUARANTINED"
    assert classify_runtime_health(runs=2, accepted=0, errors=1) == "DEGRADED"
    assert classify_runtime_health(runs=2, accepted=4, errors=0) == "HEALTHY"


def test_all_unlocked_country_packs_exist():
    for code in ("GB","CA","AU","IE","NZ","DE","FR","ES","IT","NL","BE","PT"):
        assert country_pack(code).country_code == code


def test_research_backlog_preserves_unknowns():
    rows = list(research_backlog())
    assert any(
        row["country_code"] == "DE"
        and row["status"] == "source_research_required"
        for row in rows
    )
    assert any(
        row["country_code"] == "CA"
        and row["niche"] == "solar"
        and row["status"] == "niche_source_research_required"
        for row in rows
    )


def test_global_solar_packs_use_verified_specialist_sources():
    assert choose_pack_source("AU", "solar").source_id == "au_saa_solar"
    assert choose_pack_source("IE", "solar").source_id == "ie_seai_solar"
    assert choose_pack_source("DE", "solar").source_id == "de_mastr"
    assert choose_pack_source("FR", "solar").source_id == "fr_france_renov_rge"


def test_source_plan_never_grants_execution_authority():
    plan = source_plan("GB", "solar")
    assert plan["selected_source"] == "gb_recc_solar"
    assert plan["execution_authority"] == "none"
    assert plan["actual_revenue"] is False


def test_commercial_source_score_values_outcomes_over_raw_volume():
    raw_volume = commercial_source_score(prospects=100, runs=10)
    revenue_source = commercial_source_score(
        prospects=5,
        qualified=3,
        conversations=2,
        verified_revenue_cents=50000,
        runs=2,
    )
    assert revenue_source > raw_volume
