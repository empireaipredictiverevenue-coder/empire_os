"""Validate an explicitly approved first-party research snapshot for A2A.

Self-described website location is NOT a verified local purchaser or lead.
Cached reads are advisory. Only owner-verified canonical buyer evidence may
promote records into CRM; this adapter never writes to it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import re

from empire_os.a2a_first_party_site_recovery_v1 import SCHEMA as SOURCE_SCHEMA
from empire_os.a2a_first_party_site_recovery_v1 import CONFIG_SCHEMA, _parse_site

SCHEMA = "empire.a2a.first_party_source_recovery_review.v1"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def review_first_party_research(
    manifest: Mapping[str, Any],
    snapshot: Mapping[str, Any] | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("AWARE_SOURCE_REVIEW_CLOCK_REQUIRED")
    clock = clock.astimezone(timezone.utc)
    if (not isinstance(manifest, Mapping)
            or manifest.get("schema_version") != CONFIG_SCHEMA
            or manifest.get("mode") != "OBSERVE"
            or manifest.get("send_messages") is not False
            or manifest.get("assume_buyer_intent") is not False):
        raise ValueError("UNTRUSTED_SOURCE_MANIFEST")
    expected = manifest.get("sites")
    if not isinstance(expected,list) or not 1 <= len(expected) <= 9:
        raise ValueError("INVALID_APPROVED_SITE_COUNT")
    expected_map = {}
    for row in expected:
        if not isinstance(row, Mapping):
            raise ValueError("INVALID_APPROVED_SITE")
        _, canonical = _parse_site(row.get("url"))
        expected_map[canonical] = (row.get("market"), row.get("niche"))
    if len(expected_map) != len(expected):
        raise ValueError("DUPLICATE_APPROVED_SITE")
    empty = {
        "tampa, fl": {"sector": "roofing", "first_party_sites_attempted": 0,
                      "successful_site_reads": 0, "self_described_sector_and_region_matches": 0},
        "little rock, ar": {"sector": "hvac", "first_party_sites_attempted": 0,
                            "successful_site_reads": 0, "self_described_sector_and_region_matches": 0},
        "nyc": {"sector": "general_contractor", "first_party_sites_attempted": 0,
                "successful_site_reads": 0, "self_described_sector_and_region_matches": 0},
    }
    reviewed = []
    state = "SOURCE_CACHE_MISSING_NEEDS_OPERATOR_COLLECTION"
    captured = None
    if snapshot is not None:
        if (not isinstance(snapshot, Mapping)
                or snapshot.get("schema_version") != SOURCE_SCHEMA
                or snapshot.get("mode") != "OBSERVE"
                or snapshot.get("execution_authority") != "NONE"
                or snapshot.get("buyers_verified") != 0
                or snapshot.get("contacts_sent") != 0
                or snapshot.get("crm_write_performed") is not False
                or snapshot.get("new_prospects_created") != 0
                or snapshot.get("no_personal_contact_harvesting") is not True):
            raise ValueError("SOURCE_READBACK_TRUTH_ESCALATION")
        raw_time = snapshot.get("collected_at_utc")
        if not isinstance(raw_time, str):
            raise ValueError("SOURCE_CAPTURE_TIMESTAMP_REQUIRED")
        try:
            observed = datetime.fromisoformat(raw_time.replace("Z","+00:00"))
        except ValueError:
            raise ValueError("INVALID_SOURCE_CAPTURE_TIMESTAMP") from None
        if observed.tzinfo is None or observed > clock + timedelta(minutes=5):
            raise ValueError("FUTURE_OR_NAIVE_SOURCE_CAPTURE")
        captured = observed.astimezone(timezone.utc).isoformat()
        state = ("CACHED_FIRST_PARTY_PUBLIC_RESEARCH_WITHIN_7_DAYS"
                 if clock-observed <= timedelta(days=7)
                 else "STALE_FIRST_PARTY_PUBLIC_RESEARCH_OVER_7_DAYS")
        rows = snapshot.get("records")
        if not isinstance(rows,list) or len(rows) > 9 or len(rows) != snapshot.get("websites_attempted"):
            raise ValueError("INVALID_SOURCE_FETCH_COUNT")
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("INVALID_SOURCE_READBACK_RECORD")
            site = row.get("company_site")
            if not isinstance(site, str) or site not in expected_map or site in seen:
                raise ValueError("UNAPPROVED_OR_DUPLICATE_FIRST_PARTY_SITE")
            seen.add(site)
            market, niche = expected_map[site]
            if row.get("market_requested") != market or row.get("sector_requested") != niche:
                raise ValueError("SOURCE_SECTOR_MARKET_CLAIM_MISMATCH")
            if (row.get("actual_buyer_intent") is not False
                    or row.get("buyer_budget_verified") is not False
                    or row.get("contact_authorised") is not False
                    or row.get("independently_verified_company_identity") is not False
                    or row.get("person_contact_details_recorded") is not False
                    or row.get("independently_verified_service_territory") is not False):
                raise ValueError("UNAUTHORIZED_FIRST_PARTY_CLAIM")
            good = row.get("site_fetch_status") == "HTTP_200"
            if (good and (row.get("robots_policy") not in (
                    "ROBOTS_ALLOWED","ROBOTS_NOT_PRESENT_NO_RESTRICTION_FILE")
                    or not isinstance(row.get("source_body_sha256"), str)
                    or not _DIGEST.fullmatch(row["source_body_sha256"]))):
                raise ValueError("SITE_FETCH_LACKS_SOURCE_EVIDENCE")
            match = (good and row.get("self_described_sector_matched") is True
                     and row.get("self_described_city_or_region_matched") is True)
            empty[market]["first_party_sites_attempted"] += 1
            empty[market]["successful_site_reads"] += int(good)
            empty[market]["self_described_sector_and_region_matches"] += int(match)
            reviewed.append({
                "source_url": site, "market": market, "sector": niche,
                "read_status": row.get("site_fetch_status"),
                "self_description_matches_trade_and_region": bool(match),
                "source_sha256_if_http_200": row.get("source_body_sha256") if good else None,
                "buyer_or_lead_verified": False,
                "contact_allowed": False,
            })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "source_state": state, "captured_at_utc": captured,
        "approved_site_count": len(expected_map),
        "sites_read": len(reviewed),
        "market_coverage": empty,
        "source_records": reviewed,
        "source_issuer_signature_verified": False,
        "first_party_self_description_not_owner_verified_company_identity": True,
        "local_territory_independently_verified": False,
        "commercial_buying_intent_verified": False,
        "buyer_budget_verified": False,
        "new_verified_sales_leads": 0,
        "new_campaign_launch_authority": False,
        "outbound_sent": 0, "customer_data_exported": False,
        "next_owner": "existing_buyer_scout_for_business_and_buyer_validation",
    }
