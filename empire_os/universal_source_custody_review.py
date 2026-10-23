"""Universal real-world source intake *review* for existing EmpireOS Data Cloud.

Pure, offline, no credentials/network/Redis/PostgreSQL/writes. Preserves the
original Economic Signal Fabric -> canonical identity -> Predictive Cloud and
the existing Economic Memory and PRIME simulator. No duplicate memory tables.

Input is an UNTRUSTED provider or operator observation, not official proof.
Even well-formed provider references can never prove data rights, ownership,
buyer intent, finance outcomes, consent or production ingestion authority.

Only opaque record IDs and source-host references are processed. Raw social
content, contact details, article bodies, addresses and arbitrary JSON are
deliberately excluded to reduce data leakage across niches/tenants.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

SCHEMA = "empire.universal_source_custody_review.v1"
MAX_RECORDS = 100
MAX_HISTORICAL_DAYS = 90

# Inclusion = potentially useful, NOT a live provider connection or legal
# licence. Source names are stable keys for original owner-owned adapters.
# Provider evidence URLs point to the source system, not a user-supplied
# arbitrary webpage whose claims/rights have not been checked.
SOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "gdelt_doc": {
        "niche": "NEWS", "kinds": {"NEWS_MENTION"},
        "hosts": {"api.gdeltproject.org"},
        "access": "PUBLIC_API_REVIEW",
    },
    "rss_editorial": {
        "niche": "NEWS", "kinds": {"NEWS_MENTION"},
        "hosts": set(), "access": "PUBLISHER_RIGHTS_REVIEW",
    },
    "sec_edgar": {
        "niche": "LEGAL", "kinds": {"SEC_FILING"},
        "hosts": {"data.sec.gov", "www.sec.gov"},
        "access": "OFFICIAL_API_POLICY_REVIEW",
    },
    "federal_register": {
        "niche": "LEGAL", "kinds": {"RULEMAKING", "REGULATION"},
        "hosts": {"www.federalregister.gov", "federalregister.gov"},
        "access": "PUBLIC_API_REVIEW",
    },
    "courtlistener": {
        "niche": "LEGAL", "kinds": {"COURT_DOCKET"},
        "hosts": {"www.courtlistener.com", "courtlistener.com"},
        "access": "API_TERMS_AND_CASE_DATA_REVIEW",
    },
    "pacer": {
        "niche": "LEGAL", "kinds": {"COURT_DOCKET"},
        "hosts": {"pacer.uscourts.gov"},
        "access": "PAID_OR_RESTRICTED_ACCESS",
    },
    "meta_ad_library": {
        "niche": "MARKETING", "kinds": {"AD_CREATIVE_OBSERVATION"},
        "hosts": {"www.facebook.com"},
        "access": "PLATFORM_PERMISSION_REVIEW",
    },
    "google_ads_transparency": {
        "niche": "MARKETING", "kinds": {"AD_CREATIVE_OBSERVATION"},
        "hosts": {"adstransparency.google.com"},
        "access": "PLATFORM_PERMISSION_REVIEW",
    },
    "google_trends": {
        "niche": "MARKETING", "kinds": {"SEARCH_INTEREST_INDEX"},
        "hosts": {"trends.google.com"},
        "access": "API_ACCESS_AND_QUOTA_REVIEW",
    },
    "reddit": {
        "niche": "MARKETING", "kinds": {"SOCIAL_MENTION"},
        "hosts": {"www.reddit.com", "oauth.reddit.com"},
        "access": "PLATFORM_PRIVACY_AND_TERMS_REVIEW",
    },
    "github_releases": {
        "niche": "AI", "kinds": {"MODEL_OR_CODE_RELEASE"},
        "hosts": {"github.com", "api.github.com"},
        "access": "PUBLIC_API_REVIEW",
    },
    "huggingface": {
        "niche": "AI", "kinds": {"MODEL_OR_CODE_RELEASE"},
        "hosts": {"huggingface.co"},
        "access": "MODEL_LICENCE_REVIEW",
    },
    "noaa_nws": {
        "niche": "ENVIRONMENT", "kinds": {"WEATHER_ALERT"},
        "hosts": {"api.weather.gov", "www.weather.gov", "www.nhc.noaa.gov"},
        "access": "OFFICIAL_API_POLICY_REVIEW",
    },
    "usgs": {
        "niche": "ENVIRONMENT", "kinds": {"EARTHQUAKE_OBSERVATION"},
        "hosts": {"earthquake.usgs.gov", "www.usgs.gov"},
        "access": "OFFICIAL_API_POLICY_REVIEW",
    },
    "licensed_property": {
        "niche": "PROPERTY", "kinds": {"PROPERTY_MARKET_OBSERVATION"},
        "hosts": set(), "access": "LICENCE_REQUIRED_NOT_ENABLED",
    },
    "licensed_markets": {
        "niche": "MARKETS", "kinds": {"MARKET_QUOTE"},
        "hosts": set(), "access": "LICENCE_REQUIRED_NOT_ENABLED",
    },
}

# No CRM contact data or market-derived payment amounts permitted as raw input.
RECORD_FIELDS = frozenset({
    "provider", "provider_record_id", "provider_url",
    "event_kind", "published_at", "observed_at",
    "data_classification", "rights_claim",
})
CLASSIFICATIONS = frozenset({"public_nonpersonal", "unknown", "personal_data"})
RIGHTS_CLAIMS = frozenset({
    "unreviewed", "public_reference", "permission_claimed", "licence_claimed",
})


def _timestamp(value: Any, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"{label}: invalid timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label}: timezone required")
    return value.astimezone(timezone.utc)


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise ValueError(f"{label}: bounded identifier required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,127}", value):
        raise ValueError(f"{label}: opaque identifier only")
    return value


def _provider_host(value: Any, allowed: set[str]) -> str:
    if type(value) is not str or not 1 <= len(value) <= 2048:
        raise ValueError("provider_url: bounded HTTPS URL required")
    try:
        url = urlsplit(value)
        hostname = (url.hostname or "").lower().rstrip(".")
        port = url.port
    except ValueError:
        raise ValueError("provider_url: invalid URL") from None
    if url.scheme != "https" or not hostname or url.username or url.password or (
        port not in (None, 443)
    ):
        raise ValueError("provider_url: official HTTPS reference required")
    if not allowed:
        raise ValueError("provider_url: no authorised source host configured")
    if hostname not in allowed:
        raise ValueError("provider_url: not a registered provider host")
    if not url.path.startswith("/") and url.path:
        raise ValueError("provider_url: invalid path")
    return hostname


def sec_submissions_url(cik: str) -> str:
    """Construct an offline URL for SEC's *numeric CIK*, never a ticker.

    No ticker lookup occurs; company-to-CIK mapping must originate in a
    separately verified official SEC company-tickers mapping.
    """
    if type(cik) is not str or not re.fullmatch(r"[0-9]{1,10}", cik):
        raise ValueError("SEC CIK must contain 1-10 ASCII digits; ticker unsupported")
    if int(cik) == 0:
        raise ValueError("SEC CIK cannot be zero")
    return f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"


def gdelt_doc_query_url(query: str, *, timespan_hours: int = 24) -> str:
    """Generate a bounded GDELT query URL without sending a network request."""
    if type(query) is not str or not 1 <= len(query.strip()) <= 160:
        raise ValueError("bounded GDELT query required")
    if any(ord(char) < 32 for char in query):
        raise ValueError("control characters rejected")
    if type(timespan_hours) is not int or not 1 <= timespan_hours <= 24:
        raise ValueError("GDELT review window must be 1-24h")
    return "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode({
        "query": query.strip(), "mode": "artlist", "format": "json",
        "timespan": f"{timespan_hours}h", "maxrecords": 100,
    })


def _review_record(
    raw: Mapping[str, Any], *, as_of: datetime,
) -> tuple[dict[str, Any], str]:
    if not isinstance(raw, Mapping) or set(raw) != RECORD_FIELDS:
        raise ValueError("exact minimal observation fields required")
    provider = raw["provider"]
    if type(provider) is not str or provider not in SOURCE_CATALOG:
        raise ValueError("unknown source; original provider integration required")
    policy = SOURCE_CATALOG[provider]
    record_id = _identifier(raw["provider_record_id"], "provider_record_id")
    event_kind = raw["event_kind"]
    if type(event_kind) is not str or event_kind not in policy["kinds"]:
        raise ValueError("event_kind not supported by this provider")
    host = _provider_host(raw["provider_url"], policy["hosts"])
    published = _timestamp(raw["published_at"], "published_at")
    observed = _timestamp(raw["observed_at"], "observed_at")
    if published > observed or observed > as_of:
        raise ValueError("future or chronologically impossible event")
    if raw["data_classification"] not in CLASSIFICATIONS:
        raise ValueError("data_classification: unknown value")
    if raw["rights_claim"] not in RIGHTS_CLAIMS:
        raise ValueError("rights_claim: unknown value")
    if provider == "sec_edgar" and host == "data.sec.gov":
        # Input must reference a numeric CIK at this endpoint; 'AAPL'
        # padded with zfill is not a CIK.
        expected_url = sec_submissions_url(record_id)
        if raw["provider_url"] != expected_url:
            raise ValueError("SEC submissions CIK/URL mismatch")
    blockers = [
        "DATA_RIGHTS_NOT_INDEPENDENTLY_VERIFIED",
        "SOURCE_CUSTODY_NOT_INDEPENDENTLY_VERIFIED",
        "NO_CANONICAL_ENTITY_OR_TENANT_BINDING",
        "NOT_A_VERIFIED_BUYING_SIGNAL",
        "NOT_A_VERIFIED_REVENUE_EVENT",
    ]
    if as_of - published > timedelta(days=MAX_HISTORICAL_DAYS):
        blockers.append("HISTORICAL_EVIDENCE_REQUIRES_FRESHNESS_REVIEW")
    if raw["data_classification"] != "public_nonpersonal":
        blockers.append("PERSONAL_DATA_CLASSIFICATION_REQUIRES_REVIEW")
    if policy["access"] in {
        "LICENCE_REQUIRED_NOT_ENABLED", "PAID_OR_RESTRICTED_ACCESS",
    }:
        blockers.append("PROVIDER_ACCESS_NOT_AUTHORISED")
    identity = sha256(
        ("v1|" + provider + "|" + event_kind + "|" + record_id).encode("utf-8")
    ).hexdigest()
    # Do not emit headline, text, URL query, sensitive provider IDs, PII,
    # acquired documents, user records, tenant IDs or licence claims.
    return {
        "evidence_fingerprint": identity,
        "provider": provider,
        "category": policy["niche"],
        "event_kind": event_kind,
        "source_host": host,
        "published_at": published.isoformat(),
        "observed_at": observed.isoformat(),
        "access_status": policy["access"],
        "stage": "SOURCE_REFERENCE_REVIEW_ONLY",
        "blockers": sorted(blockers),
        "independent_source_verified": False,
        "licensed_for_downstream_use": False,
        "canonical_entity_resolved": False,
        "buyer_intent_verified": False,
        "revenue_verified": False,
        "commercial_authority": "none",
    }, identity


def review_universal_observations(
    observations: Sequence[Mapping[str, Any]], *, as_of: datetime,
) -> dict[str, Any]:
    """Produce redacted review metadata only, with zero mutation authority."""
    now = _timestamp(as_of, "as_of")
    if type(observations) not in (list, tuple) or len(observations) > MAX_RECORDS:
        raise ValueError("bounded list or tuple required")
    reviewed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    categories: Counter[str] = Counter()
    for position, observation in enumerate(observations):
        try:
            candidate, fingerprint = _review_record(observation, as_of=now)
            if fingerprint in seen:
                raise ValueError("duplicate source observation")
            seen.add(fingerprint)
            reviewed.append(candidate)
            categories[candidate["category"]] += 1
        except (ValueError, TypeError) as exc:
            # Error text is ours, not interpolated provider/body content.
            errors.append({"position": position, "reason": str(exc)})
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "as_of": now.isoformat(),
        "source_count_structurally_reviewed": len(reviewed),
        "source_count_rejected": len(errors),
        "category_counts": dict(sorted(categories.items())),
        "reviewed_sources": reviewed,
        "rejections": errors,
        "next_owner": "existing Economic Signal Fabric and source intelligence owners",
        "next_stage": "CANONICAL_SOURCE_RIGHTS_AND_ENTITY_BINDING_REVIEW",
        "raw_provider_events_persisted": False,
        "redis_stream_written": False,
        "empiredb_tables_created": False,
        "empiredb_write": False,
        "vector_embeddings_created": False,
        "source_connections_activated": False,
        "new_revenue_pipeline_created": False,
        "crm_prospects_created": False,
        "buyers_verified": False,
        "recognized_revenue_cents": None,
        "payment_processing_enabled": False,
        "gpu_spend_cents": 0,
        "execution_authority": "none",
    }
