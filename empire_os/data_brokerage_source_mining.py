"""Real Data Brokerage source acquisition and mining on the existing EmpireOS cycle.

Source discovery uses the existing public Search Fabric fallback, and first-party
official government API samples. Only non-identifying aggregates are persisted.
No new database, scraper service, timer, checkout, lead importer or distribution.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import json
import os
import re
import tempfile
import ipaddress

from empire_os.source_intelligence import SOURCES
from empire_os.permit_property_source_join import PLUTO_ID, FOOTPRINT_ID
from empire_os.search_fabric.public_fallback import search_public_web
from empire_os.data_brokerage_acquisition_sequence import DISCOVERY_LANES, acquisition_sequence
from empire_os.data_brokerage_product_mining import build_source_specific_products, validate_source_specific_product_report
from empire_os.data_brokerage_us_construction import (
    fetch_official_sources as fetch_us_construction_sources,
    fetch_latest_published_official_sources as fetch_latest_us_construction_sources,
    summarise_for_existing_source_cycle,
)
from empire_os.data_brokerage_us_construction_product import (
    build_product_from_existing_official_sample,
    validate_private_market_product,
)

SCHEMA = "empire.data_brokerage.source_mining.v1"
STATE = Path("runtime/data_brokerage/source_mining_latest.json")
INBOX = Path("runtime/acquisition/signal_inbox.json")
MIN_INTERVAL = timedelta(hours=12)
MAX_INBOX_BYTES = 8_000_000
MAX_API_BYTES = 85_000
US_DATA_HOST = "data.cityofnewyork.us"
NYC_PERMITS = "https://data.cityofnewyork.us/resource/ipu4-2q9a.json"
# Only these fields may be collected from a third-party API for the aggregate.
PERMIT_FIELDS = ("borough", "permit_type", "issuance_date")
PERMIT_LIMIT = 75
# Product-first multi-country rotation; the original Search Fabric
# still owns the search provider and source registry.
DISCOVERY_QUERIES = tuple(lane[2] for lane in DISCOVERY_LANES)
# A narrow domain allowlist: search results are *untrusted candidates*, not data.
OFFICIAL_HOST_SUFFIXES = (".gov", ".gov.uk", ".gov.au", ".gc.ca", ".govt.nz")
OFFICIAL_EXACT_HOSTS = {
    "data.cityofnewyork.us", "opendata.cityofnewyork.us",
    "www.planning.data.gov.uk", "www.data.gov.uk",
    "opendata.cro.ie", "www.census.gov", "api.census.gov",
}
# Source URL, origin, licence and status live in the ONE canonical
# Source Intelligence registry. This is a derived reading, not a second list.
RESEARCH_SOURCE_IDS = (
    "us_nyc_dob_permit_issuance",
    "us_nyc_dob_now_approved_permits",
    "us_census_building_permits",
)
RESEARCH_SOURCES = tuple({
    "key": key, "country": SOURCES[key].country_code,
    "sector": "construction", "data_url": SOURCES[key].url,
    "commercial_data_rights": "UNREVIEWED",
    "registry_state": SOURCES[key].production_status,
} for key in RESEARCH_SOURCE_IDS if key in SOURCES)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 50:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.utcoffset() is not None else None
    except (ValueError, OverflowError, TypeError):
        return None


def _digest(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _official_url(url: Any) -> str | None:
    if not isinstance(url, str) or not 10 <= len(url) <= 350:
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if (parsed.scheme != "https" or parsed.username or parsed.password
        or parsed.port not in (None, 443) or not host or host.startswith("www.local")
        or "@" in parsed.netloc or host.endswith((".localhost", ".local"))
        or parsed.fragment or not parsed.path.startswith("/")):
        return None
    if host not in OFFICIAL_EXACT_HOSTS and not any(
        host == suffix.lstrip(".") or host.endswith(suffix)
        for suffix in OFFICIAL_HOST_SUFFIXES
    ):
        return None
    if parsed.path in ("/", ""):
        return None
    return parsed._replace(fragment="", query="").geturl()


def _research_candidate_url(value: Any) -> str | None:
    """Accept only public HTTPS web-catalogue CANDIDATES, never auto-fetch."""
    if not isinstance(value, str) or not 12 <= len(value) <= 500:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or port not in (None, 443) or not host
                or not re.fullmatch(r"[a-z0-9.-]{4,253}", host)
                or len(host.split(".")) < 2
                or host.endswith((".example", ".test", ".invalid", ".localhost",
                                   ".local", ".onion", ".internal"))
                or host in {"example.com", "example.org", "example.net",
                            "invalid-example.com", "localhost"}
                or host.startswith(("localhost.", "127.", "0."))
                or not re.fullmatch(r"[a-z]{2,24}", host.rsplit(".", 1)[-1])):
            return None
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            pass
        clean = parsed._replace(query="", fragment="").geturl()
        if len(clean) > 360:
            return None
        return clean
    except (ValueError, TypeError):
        return None


def discover_sources(
    *, query_index: int, search: Callable[..., Any] = search_public_web,
) -> dict[str, Any]:
    """Rotate existing Search Fabric discovery; never treat a SERP as licence."""
    if type(query_index) is not int or not 0 <= query_index < len(DISCOVERY_QUERIES):
        raise ValueError("INVALID_DISCOVERY_ROTATION")
    query = DISCOVERY_QUERIES[query_index]
    try:
        rows = search(query, num=5, timeout=4.0)
    except (ValueError, OSError, TypeError, TimeoutError):
        rows = []
    existing_urls = {
        _research_candidate_url(source.url)
        for source in SOURCES.values()
    }
    seen = {url for url in existing_urls if url}
    seen.update(u for source in RESEARCH_SOURCES
                if (u := _research_candidate_url(source["data_url"])))
    # Original bounded mining adapters and property joins already own these
    # source datasets even when their catalogue-registration branch is pending.
    seen.update({
        NYC_PERMITS, DOBNOW_PERMITS,
        f"https://data.cityofnewyork.us/resource/{PLUTO_ID}.json",
        f"https://data.cityofnewyork.us/resource/{FOOTPRINT_ID}.json",
    })
    known_dataset_ids = {
        PLUTO_ID, FOOTPRINT_ID, "w9ak-ipjd", "ipu4-2q9a", "rbx6-tga4",
    }
    known_dataset_ids.update(
        x.rsplit("/", 1)[-1].replace(".json", "")
        for x in seen if "/resource/" in x
    )
    candidates = []
    for raw in (rows[:20] if isinstance(rows, list) else []):
        if not isinstance(raw, Mapping):
            continue
        url = _research_candidate_url(raw.get("link") or raw.get("url"))
        if url is None or url in seen:
            continue
        ident = url.rsplit("/", 1)[-1].replace(".json", "")
        if ident in known_dataset_ids:
            continue
        # A vendor, university, open-source archive or public registry can be
        # a worthwhile source. URL discovery NEVER grants permission to scrape.
        quality_text = " ".join(str(raw.get(k) or "")[:220] for k in
                                ("title", "snippet", "name", "description")).casefold()
        if not quality_text and not any(x in url.casefold() for x in
                                        ("data", "dataset", "api", "planning", "registry")):
            continue
        trusted_host = _official_url(url) is not None
        seen.add(url)
        candidates.append({
            "url": url, "source_host": urlsplit(url).hostname,
            "status": "DISCOVERED_UNVERIFIED",
            "origin_kind": ("GOVERNMENT_OR_OFFICIAL_DOMAIN_CANDIDATE"
                            if trusted_host else "NON_GOVERNMENT_RESEARCH_CANDIDATE"),
            "api_schema_checked": False, "licence_checked": False,
            "site_terms_checked": False, "first_party_source_verified": False,
            "customer_distribution_allowed": False,
        })
        if len(candidates) >= 6:
            break
    return {
        "query_index": query_index, "query": query,
        "existing_source_registry_count": len(SOURCES),
        "new_search_candidates": candidates,
        "candidate_count": len(candidates),
        "search_provider_available": bool(getattr(rows, "provider_available", False)),
        "candidate_reuse_rights_verified": False,
    }


def _fetch_nyc_sample(url: str) -> list[Mapping[str, Any]]:
    if url != NYC_PERMITS + "?" + urlencode({
        "$select": ",".join(PERMIT_FIELDS), "$limit": str(PERMIT_LIMIT),
    }):
        raise ValueError("UNAPPROVED_BROKERAGE_SOURCE_REQUEST")
    req = Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Brokerage-Source-Mining/1.0 (empire-ai.co.uk)",
    })
    with build_opener(_NoRedirect).open(req, timeout=8) as response:
        if (response.geturl() != url or response.status != 200
            or not response.headers.get("Content-Type", "").startswith("application/json")):
            raise ValueError("UNTRUSTED_OFFICIAL_API_RESPONSE")
        raw = response.read(MAX_API_BYTES + 1)
        if len(raw) > MAX_API_BYTES:
            raise ValueError("OFFICIAL_API_RESPONSE_TOO_LARGE")
    result = json.loads(raw)
    if not isinstance(result, list) or len(result) > PERMIT_LIMIT:
        raise ValueError("OFFICIAL_PERMIT_SAMPLE_INVALID")
    return result


def mine_nyc_permit_sample(
    rows: list[Mapping[str, Any]], *, now: datetime,
) -> dict[str, Any]:
    """Bounded real mining: date/borough/type histograms, never applicant PII.

    A first-page sample is NEVER a population count, live alert or verified
    customer-facing dataset. Event dates and observation date stay separate.
    """
    if type(rows) is not list or len(rows) > PERMIT_LIMIT:
        raise ValueError("UNTRUSTED_PERMIT_SAMPLE")
    cities = {"MANHATTAN", "BRONX", "BROOKLYN", "QUEENS", "STATEN ISLAND"}
    boroughs: Counter[str] = Counter()
    types: Counter[str] = Counter()
    original_years: Counter[str] = Counter()
    valid = 0
    recent_30 = 0
    for row in rows:
        if not isinstance(row, Mapping) or set(row) - set(PERMIT_FIELDS):
            raise ValueError("UNAPPROVED_PUBLIC_SOURCE_FIELDS")
        borough = str(row.get("borough") or "").strip().upper()
        permit = str(row.get("permit_type") or "").strip().upper()
        issued = _parse_time(row.get("issuance_date"))
        # Source dates are often YYYY-MM-DD (without timezone); parse as date
        # only when source provides a proper YYYY-MM-DD calendar value.
        if issued is None and isinstance(row.get("issuance_date"), str):
            raw = row["issuance_date"]
            if (re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw)
                or re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.0{1,3})?", raw)):
                try:
                    issued = datetime.fromisoformat(raw[:10]).replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
            elif re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
                # NYC DOB permits return US-format original issue dates.
                try:
                    issued = datetime.strptime(raw, "%m/%d/%Y").replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        if borough not in cities or not re.fullmatch(r"[A-Z0-9 -]{1,25}", permit) or issued is None:
            continue
        if issued > now + timedelta(days=1) or issued.year < 1980:
            continue
        valid += 1
        boroughs[borough] += 1
        types[permit] += 1
        original_years[str(issued.year)] += 1
        if timedelta(days=0) <= now - issued <= timedelta(days=30):
            recent_30 += 1
    return {
        "source": "us_nyc_dob_permit_issuance",
        "status": "OFFICIAL_BOUNDED_SAMPLE_MINED" if valid else "NO_VALID_SOURCE_EVENTS_IN_SAMPLE",
        "source_record_count": len(rows), "validated_event_dates": valid,
        "original_filing_or_issuance_last_30_days_in_sample": recent_30,
        "sample_borough_counts": dict(sorted(boroughs.items())),
        "sample_permit_type_counts": dict(sorted(types.items())),
        "original_issue_year_counts": dict(sorted(original_years.items())),
        "sample_is_population": False, "latest_source_event_across_market_verified": False,
        "permit_to_company_binding_verified": False,
        "buyer_demand_inferred": False, "resale_rights_cleared": False,
        "source_fields_used": list(PERMIT_FIELDS),
        "histogram_sha256": _digest([dict(sorted(boroughs.items())),
                                      dict(sorted(types.items())),
                                      dict(sorted(original_years.items()))]),
    }


def mine_existing_inbox(root: Path, *, now: datetime) -> dict[str, Any]:
    """Mine canonical inbox source coverage without touching contact/raw fields."""
    path = root / INBOX
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_INBOX_BYTES:
        return {"status": "INBOX_UNAVAILABLE", "signal_count": None, "source_counts": {}}
    try:
        inbox = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(inbox, dict) or len(inbox) > 50000:
            raise ValueError("UNTRUSTED_CANONICAL_INBOX")
        counts: Counter[str] = Counter()
        observed_7d = 0
        for row in inbox.values():
            if not isinstance(row, Mapping):
                continue
            source = row.get("source")
            if not isinstance(source, str) or not re.fullmatch(r"[a-z0-9_]{1,48}", source):
                continue
            counts[source] += 1
            timestamp = _parse_time(row.get("created_at"))
            if timestamp is not None and timedelta(0) <= now - timestamp <= timedelta(days=7):
                observed_7d += 1
        return {
            "status": "CANONICAL_INBOX_AGGREGATED",
            "signal_count": sum(counts.values()), "source_counts": dict(sorted(counts.items())),
            "first_seen_last_7d_in_current_inbox": observed_7d,
            "any_newly_found_signal_is_buyer": False,
            "raw_contact_or_personal_records_read": False,
            "source_deduplication_basis": "existing_canonical_inbox_identity",
        }
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "INBOX_UNAVAILABLE", "signal_count": None, "source_counts": {}}


def build_brokerage_source_mining(
    root: Path, *, now: datetime | None = None,
    search: Callable[..., Any] = search_public_web,
    fetch: Callable[[str], list[Mapping[str, Any]]] = _fetch_nyc_sample,
    catalog_fetch: Callable[[str], Mapping[str, Any]] | None = None,
    recent_fetch: Callable[[str], list[Mapping[str, Any]]] | None = None,
    construction_fetch: Callable[..., tuple[str, Mapping[str, Any]]] | None = None,
    construction_product_sink: Callable[[Mapping[str, Any]], None] | None = None,
    query_index: int = 0,
) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if clock.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_CYCLE_REQUIRED")
    clock = clock.astimezone(timezone.utc)
    discovery = discover_sources(query_index=query_index, search=search)
    market, product, _ = DISCOVERY_LANES[query_index]
    government = {
        "status": "NOT_SELECTED_THIS_CYCLE",
        "query_index": query_index % len(CATALOG_QUERIES),
        "candidate_count": 0, "new_candidates": [],
    }
    if market == "US" and product == "property_development":
        government = discover_government_datasets(
            query_index=query_index % len(CATALOG_QUERIES),
            fetch=catalog_fetch or _fetch_socrata_catalog,
        )
    url = NYC_PERMITS + "?" + urlencode({
        "$select": ",".join(PERMIT_FIELDS), "$limit": str(PERMIT_LIMIT),
    })
    mined = {
        "source": "us_nyc_dob_permit_issuance",
        "status": "NOT_SELECTED_THIS_CYCLE",
        "source_record_count": None,
        "buyer_demand_inferred": False, "resale_rights_cleared": False,
    }
    if market == "US" and product == "property_development":
        try:
            event_rows = fetch(url)
            mined = mine_nyc_permit_sample(event_rows, now=clock)
        except (OSError, ValueError, TimeoutError, HTTPError, URLError, TypeError, KeyError):
            mined = {
                "source": "us_nyc_dob_permit_issuance",
                "status": "OFFICIAL_SOURCE_READ_FAILED",
                "source_record_count": None,
                "buyer_demand_inferred": False, "resale_rights_cleared": False,
            }
    recent = {
        "source": "us_nyc_dob_now_approved_permits",
        "status": "NOT_SELECTED_THIS_CYCLE",
        "sample_count": None,
        "valid_recent_issue_dates_in_sample": None,
        "buyer_demand_inferred": False, "resale_rights_cleared": False,
    }
    if market == "US" and product == "property_development":
        try:
            recent_rows = (recent_fetch or _fetch_recent_dobnow)(_dobnow_url(clock))
            recent = mine_recent_dobnow(recent_rows, now=clock)
        except (OSError, ValueError, TypeError, KeyError, TimeoutError, HTTPError, URLError):
            recent = {
                "source": "us_nyc_dob_now_approved_permits",
                "status": "RECENT_OFFICIAL_SOURCE_READ_FAILED",
                "sample_count": None,
                "valid_recent_issue_dates_in_sample": None,
                "buyer_demand_inferred": False, "resale_rights_cleared": False,
            }
    # Existing 12-hour mining owner: one bounded two-source US market view.
    # No extra scheduler, buyer inference or raw organisation rows persisted.
    us_construction = {
        "status": "NOT_SELECTED_THIS_CYCLE", "source_records_persisted": False,
        "buyer_enquiries_verified": 0, "outreach_sent": False,
        "execution_authority": "none",
    }
    # Unlike rotating discovery queries, official construction market evidence
    # refreshes on each already-budgeted 12h owner cycle, regardless of lane.
    if root.resolve() == Path("/srv/empire_os") or construction_fetch is not None:
        try:
            candidate_month = (clock - timedelta(days=30)).strftime("%Y%m")
            if construction_fetch is None:
                reference_month, census_text, award_data = (
                    fetch_latest_us_construction_sources(now=clock)
                )
            else:
                # Tests may inject one deterministic historical source snapshot.
                reference_month = (clock - timedelta(days=49)).strftime("%Y%m")
                census_text, award_data = construction_fetch(
                    now=clock, month=reference_month,
                )
            us_construction = summarise_for_existing_source_cycle(
                now=clock, month=reference_month,
                census_text=census_text, awards_response=award_data,
            )
            us_construction["newer_state_month_checked"] = candidate_month
            us_construction["publication_fallback_used"] = (
                reference_month != candidate_month
            )
            # The original brokerage cycle owns the product materialisation.
            # This callback only collects an internal, privacy-minimised
            # candidate; the driver persists it under the existing lock.
            if construction_product_sink is not None and construction_fetch is None:
                try:
                    draft = build_product_from_existing_official_sample(
                        now=clock, latest=reference_month,
                        latest_census_text=census_text,
                        awards_response=award_data,
                        include_nyc_projects=True,
                        include_property_crosscheck=True,
                    )
                    if not validate_private_market_product(draft, now=clock):
                        raise ValueError("US_MARKET_PRODUCT_EVIDENCE_UNVERIFIED")
                    construction_product_sink(draft)
                    us_construction["market_project_events_crosschecked"] = (
                        draft["verified_local_project_evidence"][
                            "distinct_crosschecked_jobs"
                        ]
                    )
                    us_construction["market_project_source_status"] = (
                        draft["verified_local_project_evidence"]["status"]
                    )
                    us_construction["market_property_reference_matches"] = (
                        draft["independent_property_reference_review"][
                            "three_agency_reference_matches"
                        ]
                    )
                    us_construction["market_property_reference_status"] = (
                        draft["independent_property_reference_review"]["status"]
                    )
                    us_construction["market_product_candidate"] = (
                        "PRIVATE_PREVIEW_VALIDATED_PENDING_OWNER_COMMIT"
                    )
                except (OSError, ValueError, KeyError, TypeError, TimeoutError, UnicodeError):
                    us_construction["market_product_candidate"] = (
                        "SOURCE_PRODUCT_EVIDENCE_HOLD"
                    )
        except (OSError, ValueError, TypeError, KeyError, TimeoutError, UnicodeError):
            us_construction = {
                "status": "OFFICIAL_US_CONSTRUCTION_SOURCE_READ_FAILED",
                "source_records_persisted": False,
                "buyer_enquiries_verified": 0, "outreach_sent": False,
                "execution_authority": "none",
            }
    else:
        us_construction["status"] = "NONCANONICAL_SOURCE_READ_NOT_RUN"
    existing = mine_existing_inbox(root, now=clock)
    # Source-specific product mining is the canonical brokerage owner's
    # bounded read. Isolated tests cannot accidentally call public APIs.
    product_intelligence = {
        "status": "NONCANONICAL_RUNTIME_NOT_RUN",
        "original_product_count": 0,
        "source_bound_products": [],
        "no_customer_delivery": True,
    }
    if root.resolve() == Path("/srv/empire_os"):
        product_intelligence = build_source_specific_products(root, now=clock)
    strategy = acquisition_sequence(root, index=query_index, now=clock,
                                    mining={"recent_official_permit_mining": recent})
    return {
        "schema_version": SCHEMA, "mode": "BOUNDED_SOURCE_DISCOVERY_AND_MINING",
        "status": "SOURCE_MINING_CYCLE_EXECUTED",
        "observed_at": clock.isoformat(), "next_eligible_at": (clock + MIN_INTERVAL).isoformat(),
        "discovery": discovery, "official_dataset_discovery": government,
        "product_targeting_sequence": strategy,
        "source_specific_product_intelligence": product_intelligence,
        "official_api_mining": mined,
        "recent_official_permit_mining": recent,
        "us_construction_official_research": us_construction,
        "existing_acquisition_mining": existing,
        "mining_new_research_source_count": len(RESEARCH_SOURCES),
        "research_source_registration_pending": [key for key in RESEARCH_SOURCE_IDS if key not in SOURCES],
        "research_sources": [dict(s) for s in RESEARCH_SOURCES],
        "existing_source_registry_count": len(SOURCES),
        "non_identifying_data_only": True, "canonical_inbox_modified": False,
        "raw_source_rows_persisted": False, "customer_distribution_enabled": False,
        "commercialisation_rights_verified": False, "qualified_buyers_inferred": False,
        "money_or_models_used": False, "outbound_sent": False,
        "production_db_writes": False, "execution_authority": "none",
    }


def load_verified_cycle(root: Path) -> dict[str, Any] | None:
    path = root / STATE
    try:
        if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size > 95000:
            return None
        report = json.loads(path.read_text(encoding="utf-8"))
        claim = report.pop("local_integrity_sha256")
        if (report.get("schema_version") != SCHEMA or _digest(report) != claim
            or report.get("raw_source_rows_persisted") is not False
            or report.get("customer_distribution_enabled") is not False
            or report.get("outbound_sent") is not False
            or report.get("production_db_writes") is not False
            or ("source_specific_product_intelligence" in report
                and not validate_source_specific_product_report(report["source_specific_product_intelligence"]))):
            return None
        return {**report, "local_integrity_sha256": claim}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def persist_source_cycle(root: Path, report: Mapping[str, Any]) -> Path:
    if (report.get("schema_version") != SCHEMA
        or report.get("customer_distribution_enabled") is not False
        or report.get("raw_source_rows_persisted") is not False
        or report.get("production_db_writes") is not False
        or report.get("outbound_sent") is not False
        or ("source_specific_product_intelligence" in report
            and not validate_source_specific_product_report(report["source_specific_product_intelligence"]))):
        raise ValueError("SOURCE_CYCLE_AUTHORITY_NOT_VERIFIED")
    location = root / STATE
    if location.parent.is_symlink() or location.is_symlink():
        raise ValueError("BROKERAGE_PRIVATE_SOURCE_SYMLINK_REFUSED")
    location.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(location.parent, 0o700)
    document = dict(report)
    document["local_integrity_sha256"] = _digest(report)
    fd, temp = tempfile.mkstemp(prefix=".source_mining.", dir=location.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(document, out, sort_keys=True, indent=2, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, location)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return location


def due_source_cycle(root: Path, *, now: datetime | None = None) -> bool:
    clock = now or datetime.now(timezone.utc)
    previous = load_verified_cycle(root)
    due = _parse_time(previous.get("next_eligible_at")) if previous else None
    return due is None or clock >= due


# Independently searchable government dataset catalogue. This is not the
# Web Search Fabric provider; it is an official published dataset index.
SOCRATA_HOST = "api.us.socrata.com"
CATALOG_QUERIES = (
    "building permits", "commercial property", "solar installations", "land use",
)
_CATALOG_ID = re.compile(r"[a-z0-9]{4}-[a-z0-9]{4}\Z")
_CATALOG_WORDS = frozenset((
    "building", "permit", "property", "land", "construction", "solar",
    "housing", "parcel", "zoning", "pluto", "fire", "inspection",
))


def _fetch_socrata_catalog(url: str) -> Mapping[str, Any]:
    required_prefix = "https://api.us.socrata.com/api/catalog/v1?"
    if not url.startswith(required_prefix):
        raise ValueError("UNAPPROVED_CATALOG_ENDPOINT")
    parsed = urlsplit(url)
    if parsed.hostname != SOCRATA_HOST or parsed.scheme != "https":
        raise ValueError("UNTRUSTED_CATALOG_HOST")
    req = Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Brokerage-Catalogue-Mining/1.0 (empire-ai.co.uk)",
    })
    with build_opener(_NoRedirect).open(req, timeout=6) as resp:
        if (resp.status != 200 or resp.geturl() != url
                or not resp.headers.get("Content-Type", "").startswith("application/json")):
            raise ValueError("CATALOG_HTTP_UNVERIFIED")
        raw = resp.read(150_001)
        if len(raw) > 150000:
            raise ValueError("CATALOG_TOO_LARGE")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("CATALOG_INVALID")
    return data


def discover_government_datasets(
    *, query_index: int,
    fetch: Callable[[str], Mapping[str, Any]] = _fetch_socrata_catalog,
) -> dict[str, Any]:
    """Query existing NYC published dataset index for NEW candidate IDs.

    Search matches do not guarantee relevance. Never harvest row data or
    infer a commercial licence from this public catalogue.
    """
    if type(query_index) is not int or not 0 <= query_index < len(CATALOG_QUERIES):
        raise ValueError("INVALID_GOVERNMENT_CATALOG_QUERY")
    url = "https://" + SOCRATA_HOST + "/api/catalog/v1?" + urlencode({
        "domains": "data.cityofnewyork.us",
        "search_context": "data.cityofnewyork.us",
        "q": CATALOG_QUERIES[query_index],
        "limit": "5",
    })
    try:
        data = fetch(url)
        rows = data.get("results")
        if not isinstance(rows, list) or len(rows) > 5:
            raise ValueError("CATALOG_RESULT_BOUND_EXCEEDED")
        total = data.get("resultSetSize")
        if type(total) is not int or total < len(rows):
            raise ValueError("CATALOG_TOTAL_INVALID")
    except (OSError, ValueError, TypeError, KeyError, HTTPError, URLError, TimeoutError):
        return {
            "status": "OFFICIAL_CATALOG_LOOKUP_FAILED",
            "query_index": query_index, "metadata_rows": None,
            "new_candidates": [], "candidate_count": 0,
        }
    registry_ids = set()
    for item in SOURCES.values():
        path = urlsplit(item.url).path
        matched = re.search(r"/(?:resource|api/views)/([a-z0-9]{4}-[a-z0-9]{4})(?:\.json)?", path)
        if matched:
            registry_ids.add(matched.group(1))
    # Preserve first-party source-ownership: these existing cross-agency
    # NYC datasets are already mined by the Permit/Property source owner.
    registry_ids.update({
        PLUTO_ID, FOOTPRINT_ID, "w9ak-ipjd",
        "ipu4-2q9a", "rbx6-tga4",
    })
    candidates = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        resource = row.get("resource")
        if not isinstance(resource, Mapping):
            continue
        ident = resource.get("id")
        name = resource.get("name")
        if (not isinstance(ident, str) or not _CATALOG_ID.fullmatch(ident)
                or ident in registry_ids or not isinstance(name, str)
                or not 3 <= len(name) <= 120 or "@" in name
                or "retired" in name.casefold()
                or not _CATALOG_WORDS.intersection(
                    set(re.findall(r"[a-z]+", name.casefold()))
                )):
            continue
        registry_ids.add(ident)
        candidates.append({
            "candidate_id": ident, "dataset_name": name[:120],
            "api_url": f"https://data.cityofnewyork.us/resource/{ident}.json",
            "status": "OFFICIAL_CATALOG_METADATA_ONLY",
            "schema_verified": False, "event_freshness_verified": False,
            "licence_or_resale_rights_verified": False,
            "buyer_identity_verified": False,
        })
    return {
        "status": "OFFICIAL_CATALOG_METADATA_RECEIVED",
        "query_index": query_index,
        "search_term": CATALOG_QUERIES[query_index],
        "metadata_rows": len(rows), "published_matching_total": total,
        "new_candidates": candidates, "candidate_count": len(candidates),
        "customer_use_authorized": False,
    }


# Second, complementary source: official DOB NOW permits with typed
# calendar_date. Unlike legacy DOB Permit Issuance text dates, a bounded
# recent-date filter can be applied by the official public API.
DOBNOW_PERMITS = "https://data.cityofnewyork.us/resource/rbx6-tga4.json"
DOBNOW_FIELDS = ("borough", "issued_date", "permit_status")
DOBNOW_LIMIT = 40


def _dobnow_url(now: datetime) -> str:
    if now.utcoffset() is None:
        raise ValueError("UTC_AWARE_CLOCK_REQUIRED")
    earliest = (now.astimezone(timezone.utc).date() - timedelta(days=30)).isoformat()
    return DOBNOW_PERMITS + "?" + urlencode({
        "$select": ",".join(DOBNOW_FIELDS),
        "$where": "issued_date >= '" + earliest + "T00:00:00'",
        "$limit": str(DOBNOW_LIMIT),
    })


def _fetch_recent_dobnow(url: str) -> list[Mapping[str, Any]]:
    if (not url.startswith(DOBNOW_PERMITS + "?")
        or urlsplit(url).hostname != US_DATA_HOST):
        raise ValueError("UNAPPROVED_RECENT_PERMIT_URL")
    req = Request(url, method="GET", headers={
        "Accept": "application/json",
        "User-Agent": "EmpireAI-Brokerage-Recent-Permit-Observer/1.0 (empire-ai.co.uk)",
    })
    with build_opener(_NoRedirect).open(req, timeout=8) as response:
        if (response.status != 200 or response.geturl() != url
                or not response.headers.get("Content-Type", "").startswith("application/json")):
            raise ValueError("DOBNOW_OFFICIAL_SOURCE_UNTRUSTED")
        raw = response.read(MAX_API_BYTES + 1)
        if len(raw) > MAX_API_BYTES:
            raise ValueError("DOBNOW_OFFICIAL_SAMPLE_TOO_LARGE")
    data = json.loads(raw)
    if not isinstance(data, list) or len(data) > DOBNOW_LIMIT:
        raise ValueError("DOBNOW_SAMPLE_SHAPE_UNTRUSTED")
    return data


def mine_recent_dobnow(
    rows: list[Mapping[str, Any]], *, now: datetime,
) -> dict[str, Any]:
    """Mine original issue calendar dates, never collection dates or buyer claims."""
    if type(rows) is not list or len(rows) > DOBNOW_LIMIT or now.utcoffset() is None:
        raise ValueError("DOBNOW_MINING_INPUT_INVALID")
    earliest = now.astimezone(timezone.utc).date() - timedelta(days=30)
    latest = now.astimezone(timezone.utc).date()
    boroughs = Counter()
    statuses = Counter()
    by_day = Counter()
    invalid = 0
    for row in rows:
        if not isinstance(row, Mapping) or set(row) - set(DOBNOW_FIELDS):
            raise ValueError("DOBNOW_UNAPPROVED_FIELDS")
        b = str(row.get("borough") or "").strip().upper()
        status = str(row.get("permit_status") or "").strip().upper()
        date_str = row.get("issued_date")
        if (b not in {"MANHATTAN", "BRONX", "BROOKLYN", "QUEENS", "STATEN ISLAND"}
            or not isinstance(date_str, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T00:00:00(?:\.0{1,3})?", date_str)
            or not re.fullmatch(r"[A-Z0-9 _-]{1,55}", status)):
            invalid += 1
            continue
        try:
            observed_date = datetime.fromisoformat(date_str[:10]).date()
        except ValueError:
            invalid += 1
            continue
        if not earliest <= observed_date <= latest:
            invalid += 1
            continue
        boroughs[b] += 1
        statuses[status] += 1
        by_day[observed_date.isoformat()] += 1
    return {
        "source": "us_nyc_dob_now_approved_permits",
        "status": ("CURRENT_DATED_ISSUANCE_SAMPLE_MINED" if sum(by_day.values())
                   else "RECENT_ISSUANCE_SAMPLE_EMPTY_OR_INVALID"),
        "sample_count": len(rows),
        "valid_recent_issue_dates_in_sample": sum(by_day.values()),
        "invalid_or_out_of_window_sample_rows": invalid,
        "original_issue_dates_in_sample": dict(sorted(by_day.items())),
        "borough_counts_in_sample": dict(sorted(boroughs.items())),
        "permit_status_counts_in_sample": dict(sorted(statuses.items())),
        "date_window_start": earliest.isoformat(),
        "date_window_end": latest.isoformat(),
        "source_page_is_complete": False,
        "total_recent_permits_citywide": None,
        "event_date_independently_confirmed": False,
        "verified_active_construction_starts": None,
        "verified_business_buyers": None,
        "raw_source_records_persisted": False,
        "resale_rights_cleared": False,
        "histogram_sha256": _digest([
            dict(sorted(by_day.items())),
            dict(sorted(boroughs.items())),
            dict(sorted(statuses.items())),
        ]),
    }
