from datetime import datetime, timezone

from empire_os.locale_intelligence import local_time_context, resolve_locale


def test_dallas_resolves_us_language_currency_and_central_time():
    locale = resolve_locale({"metro": "Dallas, TX"})
    assert locale.country_code == "US"
    assert locale.country_name == "United States"
    assert locale.language_code == "en-US"
    assert locale.outreach_language == "en-US"
    assert locale.timezone == "America/Chicago"
    assert locale.currency == "USD"
    assert locale.calling_code == "+1"
    assert locale.measurement_system == "us_customary"
    assert locale.resolved_from in {"region_code", "known_metro"}


def test_london_resolves_uk_locale_and_timezone():
    locale = resolve_locale({"metro": "London", "state": "England"})
    assert locale.country_code == "GB"
    assert locale.language_code == "en-GB"
    assert locale.outreach_language == "en-GB"
    assert locale.timezone == "Europe/London"
    assert locale.currency == "GBP"
    assert locale.date_format == "DD/MM/YYYY"


def test_canada_default_language_is_not_assumed_safe_for_outreach():
    locale = resolve_locale({"metro": "Toronto, ON"})
    assert locale.country_code == "CA"
    assert locale.language_code == "en-CA"
    assert locale.language_basis == "country_default"
    assert locale.outreach_language is None
    assert locale.timezone == "America/Toronto"
    assert locale.currency == "CAD"


def test_explicit_source_language_overrides_country_default():
    locale = resolve_locale({
        "metro": "Dallas, TX",
        "source_language": "es-US",
    })
    assert locale.country_code == "US"
    assert locale.language_code == "es-US"
    assert locale.language_basis == "explicit_or_detected"
    assert locale.outreach_language == "es-US"


def test_local_time_context_handles_dst():
    locale = resolve_locale({"metro": "London", "state": "England"})
    summer = local_time_context(
        locale,
        now=datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )
    winter = local_time_context(
        locale,
        now=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
    )
    assert summer["utc_offset"] == "+0100"
    assert summer["dst_active"] is True
    assert winter["utc_offset"] == "+0000"
    assert winter["dst_active"] is False


def test_unknown_geography_stays_unknown():
    locale = resolve_locale({"metro": "Springfield"})
    assert locale.country_code is None
    assert locale.language_code is None
    assert locale.outreach_language is None
    assert locale.timezone is None
    assert locale.currency is None
    assert locale.confidence == 0.0



def test_contact_window_uses_recipient_local_weekday_and_hours():
    from empire_os.locale_intelligence import contact_window_status

    locale = resolve_locale({"metro": "Dallas, TX"})
    eligible = contact_window_status(
        locale,
        now=datetime(2026, 9, 21, 16, 0, tzinfo=timezone.utc),
    )
    assert eligible["eligible"] is True
    assert eligible["timezone"] == "America/Chicago"
    assert eligible["local_hour"] == 11

    early = contact_window_status(
        locale,
        now=datetime(2026, 9, 21, 11, 0, tzinfo=timezone.utc),
    )
    assert early["eligible"] is False
    assert early["reason"] == "outside_recipient_local_contact_window"
    assert early["next_eligible_utc"].startswith("2026-09-21T13:00:00")


def test_contact_window_defers_weekends():
    from empire_os.locale_intelligence import contact_window_status

    locale = resolve_locale({"metro": "London", "state": "England"})
    result = contact_window_status(
        locale,
        now=datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc),
    )
    assert result["eligible"] is False
    assert result["reason"] == "recipient_local_weekend"
    assert result["next_eligible_utc"].startswith("2026-09-21T07:00:00")
