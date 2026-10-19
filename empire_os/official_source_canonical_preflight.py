"""Official B2B source ledgers -> existing canonical crawler *READ-ONLY* preflight.

Use the established CrawlerProspectRepository.lookup_existing() and
prepare_candidate(), not a new database or reviewer. No writer is referenced.

RECC has internal acquisition rights; NPPES/NYC are separate research-only
contracts. None of the three may be silently counted as new EmpireDB inventory.
Contact-source/registry evidence is NEVER buying-intent evidence.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from empire_os.candidate_quality import assess_candidate
from empire_os.prospect_ingest import prepare_candidate, prospect_identity_keys
from empire_os.source_intelligence import SOURCES

SCHEMA = "empire.official_source_canonical_preflight.v1"
LIMITS = {"gb_recc_solar": 40, "us_cms_nppes_dental_npi2": 48,
          "us_nyc_dcwp_home_improvement_companies": 20}
LEDGER_FIELDS = {"gb_recc_solar": ("observations", "empire.recc_solar_supply_sweep.v1"),
                 "us_cms_nppes_dental_npi2": ("organizations", "empire.cms_nppes_dental_org_sweep.v1"),
                 "us_nyc_dcwp_home_improvement_companies": ("businesses", "empire.us_nyc_home_improvement_company_pilot.v1")}


def _valid_recc_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        p = urlsplit(value)
        return (p.scheme == "https" and p.hostname == "www.recc.org.uk"
                and p.port is None and p.username is None and p.password is None
                and p.path.startswith("/scheme/members/") and
                len(p.path) > len("/scheme/members/") and
                not p.query and not p.fragment)
    except ValueError:
        return False


def _fresh(value: object, now: datetime) -> bool:
    try:
        observed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            return False
        diff = (now - observed).total_seconds()
        return -300 <= diff <= 7 * 86400
    except (TypeError, ValueError, OverflowError):
        return False


def preflight_official_source_ledgers(
    ledgers: Mapping[str, Mapping],
    *,
    reader=None,
    max_canonical_lookups: int = 4,
    now: datetime | None = None,
) -> dict:
    """Returns only counters and no company names, IDs, emails or raw records.

    reader must expose lookup_existing(prepared) using canonical EmpireDB.
    An operator-supplied reader's reply is a read result, not a verified
    company identity/capacity or authorised insert. Never invoke ingest_atomic.
    """
    if not isinstance(ledgers, Mapping) or set(ledgers) != set(LIMITS):
        raise ValueError("exact_three_source_ledgers_required")
    if type(max_canonical_lookups) is not int or not 0 <= max_canonical_lookups <= 8:
        raise ValueError("canonical_lookup_budget_must_be_bounded")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone_aware_time_required")
    reasons = Counter()
    by_source = []
    prepared = []
    for sid in LIMITS:
        raw = ledgers[sid]
        field, version = LEDGER_FIELDS[sid]
        if not isinstance(raw, Mapping) or raw.get("schema_version") != version:
            raise ValueError("source_ledger_schema_mismatch")
        rows = raw.get(field)
        if not isinstance(rows, list) or len(rows) > LIMITS[sid]:
            raise ValueError("unbounded_source_ledger")
        contract = SOURCES.get(sid)
        rights = bool(
            contract and contract.production_status == "verified"
            and "internal_acquisition" in contract.allowed_uses
            and "identity" in contract.roles
            and contract.raw_resale_allowed is False
        )
        seen = set()
        accepted = 0
        held = 0
        source_reasons = Counter()
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("invalid_business_observation")
            company = row.get("business_name")
            if not isinstance(company, str) or not 4 <= len(company.strip()) <= 200:
                source_reasons["invalid_company_name"] += 1
                held += 1
                continue
            if row.get("source_id") != sid or row.get("outbound_authorized") is not False:
                source_reasons["source_or_outbound_contract_failed"] += 1
                held += 1
                continue
            if sid == "gb_recc_solar":
                unique_id = row.get("member_url")
            elif sid == "us_cms_nppes_dental_npi2":
                unique_id = row.get("organization_npi")
            else:
                unique_id = row.get("license_number")
            if not isinstance(unique_id, str) or not unique_id or unique_id in seen:
                source_reasons["duplicate_or_missing_source_business_id"] += 1
                held += 1
                continue
            seen.add(unique_id)
            if sid == "gb_recc_solar":
                if (not _valid_recc_url(unique_id)
                    or row.get("source_internal_use_only") is not True
                    or row.get("source_raw_resale_allowed") is not False
                    or row.get("niche") != "solar"
                    or row.get("territory") != "GB"
                    or row.get("verified_canonical_prospect_id") is not None):
                    source_reasons["recc_source_provenance_invalid"] += 1
                    held += 1
                    continue
            elif sid == "us_cms_nppes_dental_npi2":
                if (not re.fullmatch(r"\d{10}", unique_id)
                    or row.get("country_code") != "US"
                    or row.get("niche") != "dental"
                    or row.get("consumer_or_patient_record") is not False
                    or row.get("canonical_empiredb_prospect_id") is not None
                    or row.get("has_confirmed_buyer_intent") is not False):
                    source_reasons["nppes_business_scope_invalid"] += 1
                    held += 1
                    continue
            else:
                if (row.get("country_code") != "US"
                    or row.get("state") != "NY"
                    or row.get("niche") != "general_contractor"
                    or row.get("specific_roofing_solar_hvac_trade_verified") is not False
                    or row.get("canonical_empiredb_prospect_id") is not None
                    or row.get("real_business_independently_verified") is not False):
                    source_reasons["nyc_business_scope_invalid"] += 1
                    held += 1
                    continue
            if not rights:
                source_reasons["source_rights_for_canonical_ingest_not_approved"] += 1
                held += 1
                continue
            if not _fresh(row.get("observed_at"), current):
                source_reasons["source_observation_stale_or_missing"] += 1
                held += 1
                continue
            candidate = {
                "name": company.strip(),
                "niche": "solar",
                "metro": "United Kingdom",
                "country_code": "GB",
                "source": "recc_solar",  # existing registered crawler source
                "lead_score": 0,  # DIRECTORY CERTIFICATION != BUYING INTENT
                "url": unique_id,
                "raw": {
                    "recc_member_url": unique_id,
                    "raw_resale_allowed": False,
                    "source_business_identity_only": True,
                    "source_observed_at": row["observed_at"],
                },
            }
            decision = assess_candidate(candidate)
            if not decision.accepted or decision.entity_kind != "business":
                source_reasons["canonical_quality_hold"] += 1
                held += 1
                continue
            p = prepare_candidate(candidate)
            if p["prospect"].get("buy_signal_score") != 0:
                raise ValueError("source_candidate_mislabelled_as_buyer_intent")
            # This is a preparation in memory, not a canonical write request.
            if not prospect_identity_keys(p):
                raise ValueError("prepared_identity_missing")
            prepared.append(p)
            accepted += 1
        reasons.update(source_reasons)
        by_source.append({
            "source_id": sid,
            "observed_research_rows": len(rows),
            "canonical_prepared_for_read_only_review": accepted,
            "held_by_scope_or_rights": held,
            "hold_reasons": dict(sorted(source_reasons.items())),
            "registered_internal_acquisition_rights": rights,
        })

    lookup_counts = Counter()
    lookup_status = "NOT_REQUESTED"
    if reader is not None:
        lookup_status = "CANONICAL_READ_ONLY_ATTEMPTED"
        for p in prepared[:max_canonical_lookups]:
            try:
                result = reader.lookup_existing(p)
                status = result.get("decision") if isinstance(result, Mapping) else None
                if status not in ("matched", "ambiguous", "new"):
                    raise ValueError("untrusted_canonical_lookup")
                lookup_counts[status] += 1
            except Exception:
                lookup_counts["read_failed_or_incomplete"] += 1
        if len(prepared) > max_canonical_lookups:
            lookup_counts["deferred_after_lookup_cap"] = len(prepared) - max_canonical_lookups
        lookup_status = (
            "CANONICAL_READER_HOLD" if lookup_counts["read_failed_or_incomplete"]
            else "CANONICAL_READ_ONLY_PARTIAL" if lookup_counts["deferred_after_lookup_cap"]
            else "CANONICAL_READ_ONLY_RECONCILED"
        )
    return {
        "schema_version": SCHEMA,
        "mode": "OFFICIAL_TO_CANONICAL_REVIEW_ONLY",
        "source_rows_observed": sum(x["observed_research_rows"] for x in by_source),
        "company_source_rows_prepared_not_ingested": len(prepared),
        "held_source_rows": sum(x["held_by_scope_or_rights"] for x in by_source),
        "sources": by_source,
        "canonical_lookup_state": lookup_status,
        "canonical_lookup_decisions_not_verified_new_inventory": dict(sorted(lookup_counts.items())),
        "verified_net_new_empiredb_prospects": 0,
        "buying_intent_verified": 0,
        "canonical_insert_authorized": False,
        "exchange_inventory_added": 0,
        "outbound_authorized": False,
        "customer_export_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }
