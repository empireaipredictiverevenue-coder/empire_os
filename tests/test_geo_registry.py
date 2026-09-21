from empire_os.geo_registry import (
    US_MARKETS,
    acquisition_markets,
    market_by_metro,
    market_coordinates,
)


def test_registry_covers_all_us_states_plus_dc():
    regions = {
        row.region_code
        for row in US_MARKETS
        if row.country_code == "US"
    }
    assert len(regions) == 51
    assert {"TX", "CA", "NY", "AK", "HI", "DC"} <= regions


def test_registry_expands_without_losing_existing_high_value_metros():
    coords = market_coordinates()
    for metro in (
        "Dallas, TX",
        "Houston, TX",
        "Austin, TX",
        "San Antonio, TX",
        "Tampa, FL",
        "San Diego, CA",
    ):
        assert metro in coords


def test_registry_has_initial_multi_country_coverage():
    countries = {row.country_code for row in acquisition_markets()}
    assert {
        "US", "GB", "CA", "AU", "IE", "NZ",
        "DE", "FR", "ES", "IT", "NL", "BE", "PT",
    } <= countries


def test_market_locale_is_explicit_for_multilingual_country():
    toronto = market_by_metro("Toronto, ON")
    assert toronto is not None
    payload = toronto.as_dict()
    assert payload["locale"]["country_code"] == "CA"
    assert payload["locale"]["outreach_language"] == "en-CA"
    assert payload["locale"]["timezone"] == "America/Toronto"
