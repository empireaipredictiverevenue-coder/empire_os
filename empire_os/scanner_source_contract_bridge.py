"""Read-only rights/identity adapter for legacy scanner-shaped business rows.

The legacy scanner.py includes US public registries, permit/property records
and generic web search. These are NOT automatically approved company leads.
This bridge uses existing canonical Source Intelligence contracts, no new
registrations, no live scanner invocations and no direct prospect ingestion.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from urllib.parse import urlsplit
import hashlib
import re

from empire_os.source_intelligence import SOURCES
from empire_os.waterfall_source_bridge import VERTICAL_TARGETS

SCHEMA = "empire.legacy_scanner_source_review.v1"
MAX_ROWS = 40
# Only already-registered source IDs/aliases. US DBPR, SunBiz, BBB and
# permit feeds remain HELD until licensing and source rights are reviewed.
APPROVED_SOURCE_ALIASES = {
    "recc_solar": "gb_recc_solar",
    "gb_recc_solar": "gb_recc_solar",
    "gb_companies_house": "gb_companies_house",
}


def _same_source_host(value: str, contract_url: str) -> bool:
    if not isinstance(value, str) or len(value) > 2048 or not value:
        return False
    try:
        proposed = urlsplit(value)
        known = urlsplit(contract_url)
        return (
            proposed.scheme == known.scheme == "https"
            and proposed.hostname == known.hostname
            and proposed.username is None and proposed.password is None
            and proposed.port is None
        )
    except ValueError:
        return False


def review_existing_scanner_rows(
    rows: Sequence[Mapping],
    *,
    niche: str, target_kind: str, territory: str,
    rights_receipt_ref: str = "",
    now: datetime | None = None,
) -> dict:
    """No source use approval or lead identity is inferred by this review."""
    if not isinstance(rows, (tuple, list)) or len(rows) > MAX_ROWS:
        raise ValueError("legacy scanner observations must be bounded")
    if not isinstance(niche, str) or not isinstance(territory, str):
        raise TypeError("invalid niche/territory")
    if not isinstance(target_kind, str):
        raise TypeError("invalid B2B target kind")
    _ = now or datetime.now(timezone.utc)
    results = []
    unique = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("non-mapping scanner row")
        raw_source = row.get("source")
        source_id = APPROVED_SOURCE_ALIASES.get(raw_source) if isinstance(raw_source, str) else None
        source = SOURCES.get(source_id) if source_id else None
        reasons = []
        if not source or source.production_status != "verified":
            reasons.append("source_contract_not_registered_or_verified")
        else:
            if "internal_acquisition" not in source.allowed_uses:
                reasons.append("source_use_not_authorized")
            if "identity" not in source.roles:
                reasons.append("signal_or_nonidentity_source")
            if source.niches != ("all",) and niche not in source.niches:
                reasons.append("source_niche_mismatch")
            if not territory.startswith(source.country_code + "-"):
                reasons.append("source_territory_mismatch")
            if not _same_source_host(row.get("url"), source.url):
                reasons.append("source_url_not_authoritatively_matched")
        if not rights_receipt_ref or len(rights_receipt_ref) < 8:
            reasons.append("source_rights_receipt_missing")
        elif any(ord(c) < 32 for c in rights_receipt_ref):
            reasons.append("source_rights_receipt_invalid")
        if niche not in VERTICAL_TARGETS or target_kind not in VERTICAL_TARGETS.get(niche, ()):
            reasons.append("individual_or_unapproved_target")
        if niche in {"legal", "mass_torts", "insurance", "dental"}:
            reasons.append("regulated_b2b_jurisdiction_review_required")
        business_name = row.get("name") or row.get("business_name")
        if not isinstance(business_name, str) or len(business_name.strip()) < 3:
            reasons.append("business_name_missing")
        if row.get("entity_kind") not in ("business", "company"):
            reasons.append("business_entity_classification_unproven")
        if row.get("contains_consumer_claimant_or_patient_data") is not False:
            reasons.append("consumer_or_sensitive_data_exclusion_unproven")

        key = hashlib.sha256(
            (str(raw_source) + "|" + str(row.get("url")) + "|" + str(business_name)
             + "|" + niche + "|" + territory).encode()
        ).hexdigest()[:20]
        if key in unique:
            reasons.append("duplicate_observation_same_scan")
        unique.add(key)
        results.append({
            "observation_key": key,
            "source_id": source_id,
            "review_state": "HOLD" if reasons else "OFFLINE_SOURCE_REVIEW",
            "reasons": sorted(set(reasons)),
            "canonical_business_verified": False,
            "lead_inventory_authorized": False,
            "outbound_authorized": False,
            "waterfall_enrich_authorized": False,
            "claimant_profiling_authorized": False,
        })

    return {
        "schema_version": SCHEMA,
        "mode": "OFFLINE_EXISTING_SCANNER_SOURCE_REVIEW",
        "rows_inspected": len(results),
        "source_review_counts": dict(sorted(Counter(
            x["review_state"] for x in results
        ).items())),
        "observations": results,
        "execution_authority": "none",
        "canonical_empiredb_writes": False,
        "outbound_authorized": False,
        "no_live_network_fetch": True,
        "note": "Receipt strings and classifications remain assertions to audit independently",
    }
