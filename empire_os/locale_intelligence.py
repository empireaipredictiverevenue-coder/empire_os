"""Canonical geography, locale, language and timezone intelligence.

The resolver is conservative:
- explicit evidence wins;
- metro/region inference is used only for known mappings;
- multilingual-country defaults are labeled as defaults, not detection;
- unknown geography/language/timezone stays unknown.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class CountryProfile:
    code: str
    name: str
    default_language: str
    currency: str
    calling_code: str
    measurement_system: str
    date_format: str
    number_locale: str
    default_timezone: str | None = None
    multilingual: bool = False


COUNTRIES: dict[str, CountryProfile] = {
    "US": CountryProfile("US", "United States", "en-US", "USD", "+1", "us_customary", "MM/DD/YYYY", "en-US"),
    "GB": CountryProfile("GB", "United Kingdom", "en-GB", "GBP", "+44", "mixed", "DD/MM/YYYY", "en-GB", "Europe/London"),
    "CA": CountryProfile("CA", "Canada", "en-CA", "CAD", "+1", "metric", "YYYY-MM-DD", "en-CA", multilingual=True),
    "AU": CountryProfile("AU", "Australia", "en-AU", "AUD", "+61", "metric", "DD/MM/YYYY", "en-AU"),
    "IE": CountryProfile("IE", "Ireland", "en-IE", "EUR", "+353", "metric", "DD/MM/YYYY", "en-IE", "Europe/Dublin", multilingual=True),
    "NZ": CountryProfile("NZ", "New Zealand", "en-NZ", "NZD", "+64", "metric", "DD/MM/YYYY", "en-NZ", "Pacific/Auckland", multilingual=True),
    "DE": CountryProfile("DE", "Germany", "de-DE", "EUR", "+49", "metric", "DD.MM.YYYY", "de-DE", "Europe/Berlin"),
    "FR": CountryProfile("FR", "France", "fr-FR", "EUR", "+33", "metric", "DD/MM/YYYY", "fr-FR", "Europe/Paris"),
    "ES": CountryProfile("ES", "Spain", "es-ES", "EUR", "+34", "metric", "DD/MM/YYYY", "es-ES", "Europe/Madrid", multilingual=True),
    "IT": CountryProfile("IT", "Italy", "it-IT", "EUR", "+39", "metric", "DD/MM/YYYY", "it-IT", "Europe/Rome"),
    "NL": CountryProfile("NL", "Netherlands", "nl-NL", "EUR", "+31", "metric", "DD-MM-YYYY", "nl-NL", "Europe/Amsterdam"),
    "BE": CountryProfile("BE", "Belgium", "nl-BE", "EUR", "+32", "metric", "DD/MM/YYYY", "nl-BE", "Europe/Brussels", multilingual=True),
    "PT": CountryProfile("PT", "Portugal", "pt-PT", "EUR", "+351", "metric", "DD/MM/YYYY", "pt-PT", "Europe/Lisbon"),
}

def _load_iso_country_names() -> dict[str, str]:
    path = "/usr/share/zoneinfo/iso3166.tab"
    result: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                code, name = line.rstrip("\n").split("\t", 1)
                if len(code) == 2 and name:
                    result[code.upper()] = name.strip()
    except OSError:
        pass
    return result


def _load_country_timezones() -> dict[str, tuple[str, ...]]:
    path = "/usr/share/zoneinfo/zone.tab"
    rows: dict[str, list[str]] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if not line or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                code, zone = parts[0].upper(), parts[2].strip()
                if len(code) != 2 or not zone:
                    continue
                rows.setdefault(code, []).append(zone)
    except OSError:
        return {}
    return {
        code: tuple(dict.fromkeys(zones))
        for code, zones in rows.items()
    }


SYSTEM_COUNTRY_NAMES = _load_iso_country_names()
SYSTEM_COUNTRY_TIMEZONES = _load_country_timezones()
SYSTEM_COUNTRY_ALIASES = {
    name.casefold(): code
    for code, name in SYSTEM_COUNTRY_NAMES.items()
}


COUNTRY_ALIASES = {
    "usa": "US", "us": "US", "u.s.": "US", "united states": "US", "united states of america": "US",
    "uk": "GB", "u.k.": "GB", "great britain": "GB", "united kingdom": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "northern ireland": "GB",
    "canada": "CA", "australia": "AU", "ireland": "IE", "new zealand": "NZ",
    "germany": "DE", "france": "FR", "spain": "ES", "italy": "IT",
    "netherlands": "NL", "belgium": "BE", "portugal": "PT",
}

US_STATE_CODES = {
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia","ks","ky","la","me","md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj","nm","ny","nc","nd","oh","ok","or","pa","ri","sc","sd","tn","tx","ut","vt","va","wa","wv","wi","wy","dc"
}
CA_PROVINCE_CODES = {"ab","bc","mb","nb","nl","ns","nt","nu","on","pe","qc","sk","yt"}
AU_STATE_CODES = {"act","nsw","nt","qld","sa","tas","vic","wa"}

CITY_TIMEZONES = {
    # United States
    ("US", "new york"): "America/New_York",
    ("US", "nyc"): "America/New_York",
    ("US", "boston"): "America/New_York",
    ("US", "philadelphia"): "America/New_York",
    ("US", "washington"): "America/New_York",
    ("US", "miami"): "America/New_York",
    ("US", "atlanta"): "America/New_York",
    ("US", "charlotte"): "America/New_York",
    ("US", "chicago"): "America/Chicago",
    ("US", "dallas"): "America/Chicago",
    ("US", "dallas-fort worth"): "America/Chicago",
    ("US", "houston"): "America/Chicago",
    ("US", "austin"): "America/Chicago",
    ("US", "san antonio"): "America/Chicago",
    ("US", "nashville"): "America/Chicago",
    ("US", "milwaukee"): "America/Chicago",
    ("US", "wichita"): "America/Chicago",
    ("US", "denver"): "America/Denver",
    ("US", "salt lake city"): "America/Denver",
    ("US", "phoenix"): "America/Phoenix",
    ("US", "los angeles"): "America/Los_Angeles",
    ("US", "san francisco"): "America/Los_Angeles",
    ("US", "seattle"): "America/Los_Angeles",
    ("US", "portland"): "America/Los_Angeles",
    # Canada
    ("CA", "toronto"): "America/Toronto",
    ("CA", "ottawa"): "America/Toronto",
    ("CA", "montreal"): "America/Toronto",
    ("CA", "vancouver"): "America/Vancouver",
    ("CA", "calgary"): "America/Edmonton",
    ("CA", "edmonton"): "America/Edmonton",
    ("CA", "winnipeg"): "America/Winnipeg",
    ("CA", "halifax"): "America/Halifax",
    # Australia
    ("AU", "sydney"): "Australia/Sydney",
    ("AU", "melbourne"): "Australia/Melbourne",
    ("AU", "brisbane"): "Australia/Brisbane",
    ("AU", "adelaide"): "Australia/Adelaide",
    ("AU", "perth"): "Australia/Perth",
    ("AU", "hobart"): "Australia/Hobart",
    ("AU", "darwin"): "Australia/Darwin",
    # UK/Ireland/NZ
    ("GB", "london"): "Europe/London",
    ("GB", "manchester"): "Europe/London",
    ("GB", "birmingham"): "Europe/London",
    ("GB", "glasgow"): "Europe/London",
    ("GB", "edinburgh"): "Europe/London",
    ("GB", "cardiff"): "Europe/London",
    ("GB", "belfast"): "Europe/London",
    ("IE", "dublin"): "Europe/Dublin",
    ("NZ", "auckland"): "Pacific/Auckland",
    ("NZ", "wellington"): "Pacific/Auckland",
    ("NZ", "christchurch"): "Pacific/Auckland",
}

US_SINGLE_ZONE_STATE_TZ = {
    "ct":"America/New_York","de":"America/New_York","dc":"America/New_York","ga":"America/New_York",
    "ma":"America/New_York","md":"America/New_York","me":"America/New_York","nh":"America/New_York",
    "nj":"America/New_York","ny":"America/New_York","oh":"America/New_York","pa":"America/New_York",
    "ri":"America/New_York","sc":"America/New_York","vt":"America/New_York","va":"America/New_York","wv":"America/New_York",
    "il":"America/Chicago","ia":"America/Chicago","la":"America/Chicago","mn":"America/Chicago",
    "mo":"America/Chicago","ms":"America/Chicago","ok":"America/Chicago","wi":"America/Chicago",
    "co":"America/Denver","mt":"America/Denver","nm":"America/Denver","ut":"America/Denver","wy":"America/Denver",
    "az":"America/Phoenix","ca":"America/Los_Angeles","nv":"America/Los_Angeles","wa":"America/Los_Angeles",
    "hi":"Pacific/Honolulu","ak":"America/Anchorage",
}


@dataclass(frozen=True)
class LocaleIdentity:
    country_code: str | None
    country_name: str | None
    region: str | None
    city_or_metro: str | None
    language_code: str | None
    language_basis: str
    outreach_language: str | None
    timezone: str | None
    timezone_basis: str
    timezone_candidates: tuple[str, ...]
    currency: str | None
    calling_code: str | None
    measurement_system: str | None
    date_format: str | None
    number_locale: str | None
    confidence: float
    resolved_from: str
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    return _clean(value).casefold()


def _raw_dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _explicit_country(data: Mapping[str, Any], raw: Mapping[str, Any]) -> tuple[str | None, str]:
    for key in ("country_code", "countryCode", "iso_country", "country"):
        value = data.get(key)
        if value in (None, ""):
            value = raw.get(key)
        text = _clean(value)
        if not text:
            continue
        upper = text.upper()
        if upper in COUNTRIES or upper in SYSTEM_COUNTRY_NAMES:
            return upper, "explicit_country"
        alias = (
            COUNTRY_ALIASES.get(text.casefold())
            or SYSTEM_COUNTRY_ALIASES.get(text.casefold())
        )
        if alias:
            return alias, "explicit_country"
    return None, ""


def _region_token(state: str, metro: str) -> str:
    state_n = _norm(state)
    if state_n:
        return state_n
    match = re.search(r",\s*([A-Za-z]{2,3})\s*(?:,|$)", metro)
    return match.group(1).casefold() if match else ""


def _infer_country(state: str, metro: str, raw: Mapping[str, Any]) -> tuple[str | None, str]:
    haystack = " ".join([state, metro, _clean(raw.get("country")), _clean(raw.get("country_name"))]).casefold()
    for alias, code in COUNTRY_ALIASES.items():
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", haystack):
            return code, "geo_text"
    clean_haystack = _norm(haystack)
    if clean_haystack in SYSTEM_COUNTRY_ALIASES:
        return SYSTEM_COUNTRY_ALIASES[clean_haystack], "geo_text"

    token = _region_token(state, metro)
    if token in US_STATE_CODES:
        return "US", "region_code"
    if token in CA_PROVINCE_CODES:
        return "CA", "region_code"
    if token in AU_STATE_CODES:
        return "AU", "region_code"

    metro_n = _norm(metro)
    for code, city in CITY_TIMEZONES:
        if metro_n == city or metro_n.startswith(city + ",") or metro_n.startswith(city + " "):
            return code, "known_metro"
    return None, ""


def _city_from_metro(metro: str) -> str:
    value = _clean(metro)
    if not value:
        return ""
    return value.split(",", 1)[0].strip()


def _timezone_for(code: str | None, state: str, metro: str, explicit: Any = None) -> tuple[str | None, str]:
    explicit_tz = _clean(explicit)
    if explicit_tz:
        try:
            ZoneInfo(explicit_tz)
            return explicit_tz, "explicit_timezone"
        except ZoneInfoNotFoundError:
            pass
    if not code:
        return None, "unknown"

    city = _norm(_city_from_metro(metro))
    tz = CITY_TIMEZONES.get((code, city))
    if tz:
        return tz, "metro"

    if code == "US":
        region = _region_token(state, metro)
        tz = US_SINGLE_ZONE_STATE_TZ.get(region)
        if tz:
            return tz, "region"

    profile = COUNTRIES.get(code)
    if profile and profile.default_timezone:
        return profile.default_timezone, "country_default"

    candidates = SYSTEM_COUNTRY_TIMEZONES.get(code, ())
    if len(candidates) == 1:
        return candidates[0], "country_single_zone"
    return None, "unknown"


def resolve_locale(data: Mapping[str, Any] | Any) -> LocaleIdentity:
    if not isinstance(data, Mapping):
        data = {
            key: getattr(data, key, None)
            for key in (
                "metro", "state", "country_code", "country", "language_code",
                "source_language", "timezone", "raw",
            )
        }

    raw = _raw_dict(data.get("raw"))
    metro = _clean(data.get("metro"))
    state = _clean(data.get("state"))

    code, basis = _explicit_country(data, raw)
    if not code:
        code, basis = _infer_country(state, metro, raw)

    profile = COUNTRIES.get(code or "")
    explicit_language = _clean(
        data.get("source_language")
        or data.get("language_code")
        or raw.get("language")
        or raw.get("language_code")
    )
    if explicit_language:
        language = explicit_language
        language_basis = "explicit_or_detected"
        outreach_language = explicit_language
    elif profile:
        language = profile.default_language
        language_basis = "country_default"
        # Multilingual countries need source/person language evidence before outreach.
        outreach_language = None if profile.multilingual else language
    else:
        language = None
        language_basis = "unknown"
        outreach_language = None

    tz, tz_basis = _timezone_for(
        code,
        state,
        metro,
        data.get("timezone") or raw.get("timezone"),
    )

    confidence = 0.0
    if basis == "explicit_country":
        confidence = 1.0
    elif basis == "region_code":
        confidence = 0.95
    elif basis == "known_metro":
        confidence = 0.9
    elif basis == "geo_text":
        confidence = 0.85

    return LocaleIdentity(
        country_code=code,
        country_name=(
            profile.name
            if profile
            else SYSTEM_COUNTRY_NAMES.get(code or "")
        ),
        region=state or None,
        city_or_metro=metro or None,
        language_code=language,
        language_basis=language_basis,
        outreach_language=outreach_language,
        timezone=tz,
        timezone_basis=tz_basis,
        timezone_candidates=SYSTEM_COUNTRY_TIMEZONES.get(code or "", ()),
        currency=profile.currency if profile else None,
        calling_code=profile.calling_code if profile else None,
        measurement_system=profile.measurement_system if profile else None,
        date_format=profile.date_format if profile else None,
        number_locale=profile.number_locale if profile else None,
        confidence=confidence,
        resolved_from=basis or "unknown",
    )


def local_time_context(locale: LocaleIdentity, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")
    if not locale.timezone:
        return {
            "timezone": None,
            "local_iso": None,
            "utc_offset": None,
            "dst_active": None,
        }
    try:
        zone = ZoneInfo(locale.timezone)
    except ZoneInfoNotFoundError:
        return {
            "timezone": locale.timezone,
            "local_iso": None,
            "utc_offset": None,
            "dst_active": None,
        }
    local = current.astimezone(zone)
    dst = local.dst()
    return {
        "timezone": locale.timezone,
        "local_iso": local.isoformat(),
        "utc_offset": local.strftime("%z"),
        "dst_active": bool(dst and dst.total_seconds() != 0),
    }



def contact_window_status(
    locale: LocaleIdentity,
    *,
    now: datetime | None = None,
    start_hour: int = 8,
    end_hour: int = 18,
) -> dict[str, Any]:
    """Return local business-hour eligibility for governed outreach."""
    if not 0 <= start_hour < end_hour <= 24:
        raise ValueError("invalid local contact window")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include timezone")
    if not locale.timezone:
        return {
            "eligible": False,
            "reason": "recipient_timezone_unresolved",
            "timezone": None,
            "local_iso": None,
            "next_eligible_utc": None,
        }
    try:
        zone = ZoneInfo(locale.timezone)
    except ZoneInfoNotFoundError:
        return {
            "eligible": False,
            "reason": "recipient_timezone_invalid",
            "timezone": locale.timezone,
            "local_iso": None,
            "next_eligible_utc": None,
        }

    local = current.astimezone(zone)
    weekday_ok = local.weekday() < 5
    hour_ok = start_hour <= local.hour < end_hour
    eligible = weekday_ok and hour_ok

    next_eligible = None
    if not eligible:
        for day_offset in range(0, 8):
            day = local.date() + timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue
            candidate = datetime.combine(
                day,
                dt_time(hour=start_hour),
                tzinfo=zone,
            )
            if candidate > local:
                next_eligible = candidate.astimezone(timezone.utc)
                break

    reason = (
        "inside_local_contact_window"
        if eligible
        else (
            "recipient_local_weekend"
            if not weekday_ok
            else "outside_recipient_local_contact_window"
        )
    )
    return {
        "eligible": eligible,
        "reason": reason,
        "timezone": locale.timezone,
        "local_iso": local.isoformat(),
        "local_weekday": local.weekday(),
        "local_hour": local.hour,
        "window_start_hour": start_hour,
        "window_end_hour": end_hour,
        "next_eligible_utc": (
            next_eligible.isoformat()
            if next_eligible is not None
            else None
        ),
    }
