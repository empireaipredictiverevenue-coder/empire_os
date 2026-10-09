"""Strict read-only adapters for existing EmpireOS JSON discovery snapshots.

Never infer a license, contractor identity, insurer status, carrier purchase,
claim existence, individual contact details or outreach authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlparse
import re

BUYER_QUEUE_SCHEMA = "buyer-network-candidate-queue-v1"
DFW_COHORT_SCHEMA = "empire.revenue_strike.storm.v1"
DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,250}\.[a-z]{2,24}$", re.I)


def normalized_domain(value: object) -> str:
    if not isinstance(value, str):
        return ""
    raw = value.strip().lower()
    if raw.startswith(("http://", "https://")):
        try:
            parsed = urlparse(raw)
            if parsed.username or parsed.password or parsed.port:
                return ""
            raw = parsed.hostname or ""
        except ValueError:
            return ""
    raw = raw.removeprefix("www.").strip(".")
    if not DOMAIN_RE.fullmatch(raw) or ".." in raw or raw.endswith((".local", ".test", ".internal")):
        return ""
    return raw


def buyer_queue_candidates(source: Mapping) -> tuple[list[dict], dict]:
    if (not isinstance(source, Mapping)
        or source.get("schema_version") != BUYER_QUEUE_SCHEMA
        or source.get("authority") != "OBSERVE"
        or not isinstance(source.get("candidates"), list)):
        raise ValueError("untrusted_or_unsupported_buyer_queue_schema")
    raw = source["candidates"]
    if len(raw) > 500:
        raise ValueError("buyer_queue_over_limit")
    candidates = []
    skipped = 0
    for record in raw:
        if not isinstance(record, Mapping):
            skipped += 1
            continue
        domain = normalized_domain(record.get("domain"))
        if not domain:
            skipped += 1
            continue
        # Roles and geography are UNKNOWN. Category words are NOT licences.
        candidates.append({
            "entity_id": "provisional-buyer:" + domain,
            "kind": "buyer_research_candidate", "jurisdiction": "UNVERIFIED",
            "company_name": domain, "public_domain": domain,
            "services": [], "evidence": [],
            "research_source": "buyer_network",
            "source_status": record.get("status") if record.get("status") in ("WATCH", "VERIFY_REQUIREMENTS") else "UNVERIFIED",
            "discovery_verticals": [v for v in record.get("verticals", []) if isinstance(v, str) and v in ("roofing", "restoration", "hvac", "home_services", "solar")][:8]
                if isinstance(record.get("verticals", []), list) else [],
        })
    return candidates, {
        "schema": BUYER_QUEUE_SCHEMA,
        "source_rows": len(raw), "neutral_candidates": len(candidates),
        "skipped_unusable_rows": skipped,
        "no_role_classification": True,
    }


def dfw_storm_candidates(source: Mapping) -> tuple[list[dict], dict]:
    if (not isinstance(source, Mapping)
        or source.get("schema_version") != DFW_COHORT_SCHEMA
        or source.get("outbound_sent") is not False
        or source.get("market") != "Dallas-Fort Worth, TX"
        or not isinstance(source.get("prospects"), list)):
        raise ValueError("unsupported_dfw_cohort_schema")
    raw = source["prospects"]
    if len(raw) > 100:
        raise ValueError("dfw_cohort_over_limit")
    candidates = []
    skipped = 0
    for record in raw:
        if not isinstance(record, Mapping):
            skipped += 1
            continue
        domain = normalized_domain(record.get("website"))
        if not domain:
            skipped += 1
            continue
        # Even contractor cohorts require fresh, independently sourced evidence.
        name = record.get("business_name")
        if not isinstance(name, str) or not name.strip():
            skipped += 1
            continue
        candidates.append({
            "entity_id": "provisional-dfw:" + domain,
            "kind": "contractor", "jurisdiction": "TX",
            "company_name": name[:120], "public_domain": domain,
            "services": [], "evidence": [],
            "research_source": "dfw_storm_cohort",
            "source_status": "HISTORICAL_RESEARCH",
            "discovery_verticals": ["roofing"],
        })
    return candidates, {
        "schema": DFW_COHORT_SCHEMA,
        "source_rows": len(raw), "neutral_candidates": len(candidates),
        "skipped_unusable_rows": skipped,
        "all_evidence_requires_reverification": True,
    }


OFFICIAL_NETWORK_RESEARCH = (
    (
        "Sedgwick Repair Solutions",
        "sedgwick.com",
        "https://www.sedgwick.com/repair-solutions/managed-repair-network/",
        ("roofing", "restoration"),
    ),
    (
        "Contractor Connection",
        "contractorconnection.com",
        "https://www.contractorconnection.com/for-contractors/",
        ("roofing", "restoration"),
    ),
)


def official_network_research_candidates() -> list[dict]:
    """Manually checked official pages, 2026-10-09. No buyer demand assumed.

    Page presence is not proof that these programmes want to buy Empire services
    or have contractor capacity in a particular territory.
    """
    records = []
    for name, domain, url, services in OFFICIAL_NETWORK_RESEARCH:
        records.append({
            "entity_id": "network-research:" + domain,
            "kind": "managed_repair_network", "jurisdiction": "UNVERIFIED",
            "company_name": name, "public_domain": domain,
            "services": list(services),
            "research_source": "official_network_program",
            "source_status": "PROGRAM_PUBLISHED",
            "evidence": [
                {"kind": kind, "source_url": url, "source_type": "first_party",
                 "observed_at": "2026-10-09",
                 "verified_by": "official_public_page_review_2026-10-09",
                 "verified": True}
                for kind in ("identity", "service")
            ],
        })
    return records
