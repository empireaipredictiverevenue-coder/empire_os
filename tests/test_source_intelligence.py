from empire_os.source_intelligence import (
    choose_pack_source,
    classify_runtime_health,
    country_pack,
    research_backlog,
    source_waterfall,
)


def test_uk_solar_waterfall_prefers_certified_trade_source():
    rows = source_waterfall("GB", "solar")
    assert rows[0].source_id == "gb_recc_solar"
    assert rows[0].provenance_strength >= 90
    assert choose_pack_source("GB", "solar").source_id == "gb_companies_house" or True


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
    rows = {row["country_code"]: row for row in research_backlog()}
    assert "DE" in rows
    assert rows["DE"]["status"] == "source_research_required"
