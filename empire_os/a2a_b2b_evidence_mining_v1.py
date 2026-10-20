"""Real-data, local B2B research mining from canonical owner-issued snapshots.

This is an evidence extraction and deduplication layer, NOT a new web crawler,
verified lead generation, a sales contact collector, or proof of demand.
Only uses public-business domains; never exports source people's details.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from urllib.parse import urlsplit
import re

from empire_os.a2a_founder_targeting_cycle_v1 import SCHEMA as TARGET_SCHEMA
from empire_os.a2a_owner_research_protocol_v1 import OUTBOX_SCHEMA

SCHEMA = "empire.a2a.public_business_evidence_mining.v1"
PUBLIC_SCHEMA = "empire.buyer_public_research_seeds.v1"
SCOUT_SCHEMA = "empire.buyer_acquisition_scout.v1"
NYC_SCHEMA = "empire.permit_property_three_agency_evidence.v1"
_MAX_SOURCES = 200
_HOST = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
_IGNORED_DOMAINS = frozenset((
    "reddit.com", "redd.it", "facebook.com", "fbcdn.net", "instagram.com",
    "linkedin.com", "twitter.com", "x.com", "google.com",
    "googleusercontent.com", "youtube.com", "youtu.be", "tiktok.com",
    "pinterest.com", "pinimg.com", "imgur.com", "cloudfront.net",
))
_KNOWN_NON_DIRECT_OPERATOR_DIRECTORIES = frozenset((
    "all-contractors.com", "angi.com", "homeadvisor.com", "yelp.com",
    "thumbtack.com", "modernize.com",
))
_NICHE_ALIASES = {
    "roofing": {"roofing", "roofer", "roofers"},
    "hvac": {"hvac"},
    "general_contractor": {"general_contractor", "general contractor", "commercial construction"},
    "solar": {"solar"}, "plumbing": {"plumber", "plumbing"},
    "agency": {"agency", "marketing agency"}, "law": {"law firm", "legal"},
    "b2b": {"b2b"},
}


def _time(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return date.astimezone(timezone.utc) if date.tzinfo else None


def _domain(raw: Any) -> str | None:
    if not isinstance(raw, str) or not 3 <= len(raw) <= 400:
        return None
    try:
        parsed = urlsplit(raw if "://" in raw else "https://" + raw)
        safe = (parsed.scheme == "https" and parsed.username is None
                and parsed.password is None and parsed.port is None
                and parsed.hostname is not None)
    except ValueError:
        return None
    if not safe:
        return None
    host = parsed.hostname.casefold().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if (not _HOST.fullmatch(host)
            or any(host == blocked or host.endswith("." + blocked)
                   for blocked in _IGNORED_DOMAINS)):
        return None
    return host


def _preflight(snapshot: Mapping[str, Any], *, schema: str, now: datetime,
               timestamp: str, max_age: timedelta = timedelta(hours=72)) -> dict:
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("schema_version") != schema
            or snapshot.get("mode") != "OBSERVE"
            or str(snapshot.get("execution_authority")).lower() != "none"
            or snapshot.get("outbound_sent") is not False
            or snapshot.get("database_write_performed") is not False):
        raise ValueError("UNTRUSTED_OWNER_SOURCE_" + schema)
    stamp = _time(snapshot.get(timestamp))
    if stamp is None or stamp > now + timedelta(minutes=5):
        raise ValueError("INVALID_OWNER_SOURCE_TIMESTAMP")
    return {
        "snapshot_generated_at": stamp.isoformat(),
        "owner_snapshot_over_72h_old": now - stamp > max_age,
        "is_issuer_authenticated": False,
    }


def _source_rows(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = data.get("seeds")
    if not isinstance(rows, list) or len(rows) > _MAX_SOURCES:
        raise ValueError("INVALID_PUBLIC_RESEARCH_SEEDS")
    if data.get("seed_count") != len(rows):
        raise ValueError("PUBLIC_SOURCE_COUNT_MISMATCH")
    for row in rows:
        if (not isinstance(row, Mapping) or row.get("truth_class") != "OBSERVED_PUBLIC_RESEARCH"
                or row.get("identity_verified") is not False
                or row.get("buyer_capacity_verified") is not False
                or row.get("buyer_price_verified") is not False
                or row.get("commercial_terms_verified") is not False
                or row.get("outreach_authorized") is not False):
            raise ValueError("PUBLIC_RESEARCH_TRUTH_ESCALATION")
    return rows


def _scout_rows(data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = data.get("candidates")
    if not isinstance(rows, list) or len(rows) > _MAX_SOURCES or data.get("candidate_count") != len(rows):
        raise ValueError("INVALID_SCOUT_CANDIDATES")
    for row in rows:
        if (not isinstance(row, Mapping)
                or row.get("outreach_authorized") is not False
                or row.get("commercial_terms_verified") is not False
                or row.get("budget_verified") is not False
                or row.get("candidate_state") != "RESEARCH_EVIDENCE_ONLY"):
            raise ValueError("BUYER_SCOUT_TRUTH_ESCALATION")
    return rows


def _nyc_permit_context(report: Mapping[str, Any]) -> dict[str, Any]:
    if (not isinstance(report, Mapping)
            or report.get("schema") != NYC_SCHEMA
            or report.get("mode") != "OBSERVE"
            or str(report.get("execution_authority")).lower() != "none"
            or report.get("external_outreach_sent") is not False
            or report.get("customer_facing_distributable") is not False
            or report.get("rights_review_required_for_customer_distribution") is not True):
        raise ValueError("UNTRUSTED_PERMIT_DATA_REPORT")
    events = report.get("diagnostics")
    if (not isinstance(events, list) or len(events) > 250
            or type(report.get("permit_event_count")) is not int
            or report["permit_event_count"] != len(events)):
        raise ValueError("INVALID_NYC_PERMIT_EVENT_COUNT")
    joins = Counter()
    for row in events:
        if not isinstance(row, Mapping):
            raise ValueError("INVALID_PERMIT_RESEARCH_EVENT")
        if row.get("verified_business_buyer") is not False or row.get("commercial_contact_authorized") is not False:
            raise ValueError("PERMIT_EVENT_BUYER_CLAIM_UNVERIFIED")
        joins[str(row.get("building_tax_lot_evidence_state", "UNKNOWN"))] += 1
    return {
        "source_scope": "NYC_SOURCE_JOINED_PERMIT_RESEARCH_ONLY",
        "permit_event_records_mined": len(events),
        "distinct_commercial_buyers_proven_from_permits": 0,
        "individually_verified_projects_from_permits": 0,
        "event_join_assessment_counts_observed": dict(sorted(joins.items())),
        "data_product_field_rights_verified": False,
        "material_quantities_or_supplier_prices_proven": False,
        "customer_distribution_cleared": False,
    }


def mine_targeted_business_evidence(
    targeting: Mapping[str, Any],
    owner_pickup: Mapping[str, Any],
    public_seeds: Mapping[str, Any],
    buyer_scout: Mapping[str, Any],
    nyc_report: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("TIMEZONE_CLOCK_REQUIRED")
    now = now.astimezone(timezone.utc)
    if (not isinstance(targeting, Mapping)
            or targeting.get("schema_version") != TARGET_SCHEMA
            or targeting.get("execution_authority") != "NONE"
            or targeting.get("qualified_leads_found") != 0
            or targeting.get("external_messages_sent") != 0):
        raise ValueError("UNTRUSTED_FOUNDER_TARGETS")
    if (not isinstance(owner_pickup, Mapping)
            or owner_pickup.get("schema_version") != OUTBOX_SCHEMA
            or owner_pickup.get("execution_authority") != "NONE"
            or owner_pickup.get("owner_dispatches") != 0):
        raise ValueError("UNTRUSTED_OWNER_PICKUP")
    public_health = _preflight(public_seeds, schema=PUBLIC_SCHEMA, now=now,
                               timestamp="generated_at")
    scout_health = _preflight(buyer_scout, schema=SCOUT_SCHEMA, now=now,
                              timestamp="generated_at")
    seeds = _source_rows(public_seeds)
    scout = _scout_rows(buyer_scout)
    nyc = _nyc_permit_context(nyc_report)
    # Dedup on public business domains with source lineage from existing owners.
    corpus: dict[str, dict] = {}
    for row in seeds:
        domain = _domain(row.get("website")) or _domain(row.get("domain"))
        if not domain:
            continue
        verticals = row.get("target_verticals")
        markets = row.get("target_markets")
        if not isinstance(verticals, list) or not isinstance(markets, list):
            raise ValueError("INVALID_OWNER_SEED_TARGETING_FIELDS")
        verticals = [str(k).casefold() for k in verticals if isinstance(k, str) and len(k) <= 50]
        countries = [str(k).upper() for k in markets if isinstance(k, str) and len(k) <= 12]
        # Domain/source URL is a public business research identity only.
        # Never copy associated contacts, social authors or unverified messages.
        slot = corpus.setdefault(domain, {
            "public_business_domain": domain, "source_types": set(),
            "vertical_hypotheses": set(), "country_hypotheses": set(),
            "public_source_references": set(),
            "buyer_scout_relationship_caveats": set(),
        })
        slot["source_types"].add("BUYER_PUBLIC_RESEARCH_SEED")
        slot["vertical_hypotheses"].update(verticals)
        slot["country_hypotheses"].update(countries)
        refs = row.get("source_refs") or []
        if not isinstance(refs, list) or len(refs) > 20:
            raise ValueError("BAD_SEED_EVIDENCE_REFS")
        slot["public_source_references"].update(
            ref for ref in refs if isinstance(ref, str) and
            len(ref) <= 180 and re.fullmatch(r"public:[a-zA-Z0-9:._/-]{5,170}", ref))
    for row in scout:
        domain = _domain(row.get("website")) or _domain(row.get("domain"))
        if not domain:
            continue
        info = row.get("icp_intelligence")
        hits = (info.get("fit_evidence") or {}).get("industry_signal_hits") if isinstance(info, Mapping) else None
        tokens = (set(str(hit).casefold() for hit in hits if isinstance(hit, str) and len(hit) <= 50)
                  if isinstance(hits, list) else set())
        slot = corpus.setdefault(domain, {
            "public_business_domain": domain, "source_types": set(),
            "vertical_hypotheses": set(), "country_hypotheses": set(),
            "public_source_references": set(),
            "buyer_scout_relationship_caveats": set(),
        })
        slot["source_types"].add("CANONICAL_BUYER_SCOUT_RESEARCH_ONLY")
        slot["vertical_hypotheses"].update(tokens)
        slot["buyer_scout_relationship_caveats"].add(
            str(row.get("buyer_relationship") or "unknown"))
    inputs = targeting.get("profiles")
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 10:
        raise ValueError("INVALID_TARGET_PROFILE_COUNT")
    tickets = owner_pickup.get("pickup_by_owner")
    if not isinstance(tickets, Mapping):
        raise ValueError("MISSING_OWNER_PICKUPS")
    ticket_map = {}
    for owner, entries in tickets.items():
        if owner not in ("buyer_scout", "community_intent") or not isinstance(entries, list):
            raise ValueError("UNTRUSTED_PICKUP_OWNER")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("INVALID_PICKUP_ROW")
            req = entry.get("research_request")
            if not isinstance(req, Mapping):
                raise ValueError("INVALID_PICKUP_CONTENT")
            key = (req.get("target_id"),owner)
            if key in ticket_map:
                raise ValueError("DUPLICATE_OWNER_TICKET_FOR_TARGET")
            ticket_map[key] = entry.get("ticket_id")
    results = []
    for item in inputs:
        if not isinstance(item, Mapping):
            raise ValueError("INVALID_TARGET_ITEM")
        spec = item.get("specification")
        if (not isinstance(spec, Mapping) or spec.get("research_ready") is not True
                or spec.get("external_contact_authorized") is not False):
            raise ValueError("UNTRUSTED_MINING_TARGET")
        niche, metro, country = (spec.get(k) for k in ("niche", "metro", "country"))
        tid = spec.get("target_id")
        if niche not in _NICHE_ALIASES or not isinstance(metro, str) or country not in ("US", "UK"):
            raise ValueError("UNSUPPORTED_MINING_TARGET")
        if any((tid, owner) not in ticket_map for owner in ("buyer_scout", "community_intent")):
            raise ValueError("MISSING_TARGET_OWNER_HANDOFF")
        matched = []
        for domain, entry in sorted(corpus.items()):
            if not _NICHE_ALIASES[niche].intersection(entry["vertical_hypotheses"]):
                continue
            if ("BUYER_PUBLIC_RESEARCH_SEED" in entry["source_types"]
                    and country not in entry["country_hypotheses"]
                    and not (country == "US" and "USA" in entry["country_hypotheses"])):
                # May be a generic unspecified geography; avoid treating CA/AU as US.
                if entry["country_hypotheses"]:
                    continue
            sources = sorted(entry["source_types"])
            country_match = (country in entry["country_hypotheses"]
                             or country == "US" and "USA" in entry["country_hypotheses"])
            directory_caveat = domain in _KNOWN_NON_DIRECT_OPERATOR_DIRECTORIES
            reseller_caveat = ("intermediary_or_marketplace" in entry["buyer_scout_relationship_caveats"]
                               or "publisher_affiliate_partner" in entry["buyer_scout_relationship_caveats"]
                               or directory_caveat)
            matched.append({
                "research_record_id": sha256(domain.encode()).hexdigest()[:20],
                "public_business_domain_for_owner_review": domain,
                "source_families": sources,
                "source_ref_count_not_independent_confirmations": len(entry["public_source_references"]),
                "source_refs_public_not_authenticated_signatures": sorted(entry["public_source_references"])[:6],
                "sector_hypothesis_matched": True,
                "country_hypothesis_supported_by_seed": country_match,
                "requested_city_independently_verified": False,
                "buyer_company_identity_verified": False,
                "explicit_purchase_need_verified": False,
                "buying_budget_or_capacity_verified": False,
                "publisher_or_intermediary_caveat": reseller_caveat,
                "business_directory_not_direct_local_operator": directory_caveat,
                "customer_record_created": False,
                "contact_authorized": False,
                "next_owner": "buyer_scout",
                "review_priority": (
                    "EXCLUDE_INTERMEDIARY_PENDING_OWNER_REVIEW" if reseller_caveat else
                    "COUNTRY_SECTOR_RESEARCH_ONLY" if country_match else
                    "SECTOR_ONLY_GEO_UNKNOWN"
                ),
            })
        results.append({
            "target_id": tid, "niche": niche, "requested_metro": metro,
            "requested_country": country,
            "owner_ticket_refs": {
                owner: ticket_map[(tid, owner)] for owner in ("buyer_scout", "community_intent")
            },
            "public_business_research_record_count": len(matched),
            "records": matched[:30],
            "records_truncated": len(matched) > 30,
            "exact_city_verified_buyers": 0,
            "sales_qualified_leads": 0,
            "source_mining_coverage": "EXISTING_OWNER_SNAPSHOTS_ONLY_NOT_NEW_WEB_SEARCH",
            "buyer_scout_qualification_owner": "buyer_scout",
        })
    source_digests = {
        name: sha256(json.dumps(record, sort_keys=True, separators=(",", ":"),
                                allow_nan=False).encode()).hexdigest()
        for name, record in (
            ("buyer_public_research_seeds", public_seeds),
            ("buyer_scout_research_window", buyer_scout),
            ("nyc_derived_permit_report", nyc_report),
        )
    }
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "generated_at": now.isoformat(),
        "source_snapshot_digests_not_issuer_signatures": source_digests,
        "buyer_scout_snapshot_is_rotating_research_window_not_cumulative_customer_count": True,
        "reported_record_count_is_not_market_demand": True,
        "public_owner_source_health": public_health,
        "scout_owner_source_health": scout_health,
        "public_seed_input_rows_scanned": len(seeds),
        "buyer_scout_input_rows_scanned": len(scout),
        "distinct_public_business_domains_observed": len(corpus),
        "source_research_only_no_new_provider_queries": True,
        "public_provider_fresh_search_status": str(public_seeds.get("fresh_search_result_status")),
        "search_provider_health_independently_verified": public_seeds.get("search_provider_health_independently_verified") is True,
        "nyc_permit_market_context": nyc,
        "target_mining_results": results,
        "total_target_research_records_before_cross_target_dedupe": sum(x["public_business_research_record_count"] for x in results),
        "verified_new_local_buyer_count": 0,
        "verified_real_lead_count": 0,
        "outbound_messages": 0, "customer_data_exported": False,
        "crm_write_performed": False, "new_crawl_performed": False,
        "payment_transactions": 0, "next_owner": "buyer_scout_and_source_collectors",
    }


def make_mining_source_hold(targeting: Mapping[str, Any], *, reason: str,
                            now: datetime | None = None) -> dict[str, Any]:
    if reason not in ("CANONICAL_MINING_INPUT_UNAVAILABLE", "CANONICAL_MINING_INPUT_UNTRUSTED"):
        raise ValueError("INVALID_MINING_HOLD_REASON")
    if not isinstance(targeting, Mapping) or targeting.get("schema_version") != TARGET_SCHEMA:
        raise ValueError("UNTRUSTED_TARGETING_ON_HOLD")
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        raise ValueError("UNTRUSTED_HOLD_CLOCK")
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "generated_at": when.astimezone(timezone.utc).isoformat(),
        "status": reason,
        "public_seed_input_rows_scanned": None,
        "buyer_scout_input_rows_scanned": None,
        "distinct_public_business_domains_observed": None,
        "target_mining_results": [],
        "total_target_research_records_before_cross_target_dedupe": None,
        "verified_new_local_buyer_count": 0,
        "verified_real_lead_count": 0,
        "source_mining_performed": False,
        "source_absence_is_not_zero_market_demand": True,
        "crm_write_performed": False, "new_crawl_performed": False,
        "outbound_messages": 0, "customer_data_exported": False,
        "next_owner": "buyer_scout_and_source_collectors",
    }
