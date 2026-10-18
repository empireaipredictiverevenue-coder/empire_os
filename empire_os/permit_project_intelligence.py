"""Permit project intelligence: source-date truth, cross-source evidence, no sales fiction.

Analyses a bounded first-recorded acquisition cohort, never creates a prospect,
guesses an insured loss, infers demand from a permit, or calls an external model.
Uses the EXISTING NYC permit source + Market GPS and keeps the official filing,
issuance and source-refresh dates separate. Project dossiers are private,
first-party review aids, not licensed raw data for resale or outreach lists.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit
import json
import re

from empire_os.permit_intelligence_runtime import PERMIT_SOURCES


SCHEMA = "empire.permit_project_intelligence.v1"
INBOX = Path("runtime/acquisition/signal_inbox.json")
MARKET_GPS = Path("runtime/market_sweeps/revenue_gps_latest.json")
OFFICIAL_HOST = "a810-biswebportal.nyc.gov"
OFFICIAL_PATH = "/bisweb/PropertyOverflowDetails.jsp"
# A2 and A1 are filing types, not roofing, solar, or buyer intent.
DIRECT_WORK_TYPES = {"PL": "plumbing", "EL": "electrical"}
RECENT_PROJECT_DAYS = 30
COHORT_HOURS = 24
MAX_REVIEW_DOSSIERS = 5
# Never include owner or permittee free-text/contact fields in a review payload.


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return ts.astimezone(timezone.utc) if ts.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _official_day(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    val = value.strip()
    try:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", val):
            return datetime.strptime(val, "%m/%d/%Y").replace(tzinfo=timezone.utc)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?)?", val):
            return datetime.fromisoformat(val).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return None


def _recent(day: datetime | None, now: datetime) -> bool:
    return day is not None and timedelta(0) <= now - day <= timedelta(days=RECENT_PROJECT_DAYS)


def _official_url(value: Any, job: str) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{5,12}", job):
        return None
    try:
        parsed = urlsplit(value)
        query = parse_qs(parsed.query, keep_blank_values=True)
        if (parsed.scheme == "https" and parsed.hostname == OFFICIAL_HOST
                and parsed.netloc == OFFICIAL_HOST
                and parsed.path == OFFICIAL_PATH
                and not parsed.fragment and query == {"job": [job]}):
            return value
    except ValueError:
        return None
    return None


def _id(value: Any, digits: tuple[int, ...]) -> str | None:
    val = str(value).strip() if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    return val if val.isdigit() and len(val) in digits else None


def _code(value: Any, *, limit: int = 15) -> str | None:
    if not isinstance(value, str):
        return None
    val = value.strip().upper()
    return val if len(val) <= limit and re.fullmatch(r"[A-Z0-9_-]+", val) else None


def _market_summary(payload: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    stamp = _time(payload.get("generated_at"))
    if (payload.get("execution_authority") != "none"
            or stamp is None or not timedelta(0) <= now - stamp <= timedelta(hours=24)):
        return {
            "state": "MARKET_GPS_UNAVAILABLE_OR_STALE",
            "commercial_demand_proven": False,
            "approved_buyer_capacity_proven": False,
            "observed_revenue_proven": False,
            "markets": {},
        }
    result: dict[str, Any] = {}
    for m in payload.get("markets", []):
        if not isinstance(m, dict) or str(m.get("metro") or "").strip().casefold() != "nyc":
            continue
        niche = str(m.get("niche") or "").strip().casefold()
        if niche not in {"general_contractor", "plumbing", "electrical", "hvac", "roofing"}:
            continue
        result[niche] = {
            "source": "existing_market_gps",
            "source_basis": "AGGREGATE_MARKET_ONLY_NOT_PROJECT_MATCH",
            "commercial_demand_state": str(m.get("commercial_demand_state") or "unknown")[:32],
            "commercial_reply_count": max(0, int(m.get("commercial_reply_count") or 0)),
            "approved_buyer_count": max(0, int(m.get("approved_buyer_count") or 0)),
            "verified_payment_count": max(0, int(m.get("verified_payment_count") or 0)),
            "project_buyer_matched": False,
        }
    return {
        "state": "FRESH_AGGREGATE_MARKET_CONTEXT" if result else "NYC_MARKET_UNMATCHED",
        "generated_at": stamp.isoformat(),
        "commercial_demand_proven": False,  # market aggregate never proves individual demand
        "approved_buyer_capacity_proven": False,
        "observed_revenue_proven": False,
        "markets": result,
    }



def _dossier_dobnow(row: Mapping[str, Any], now: datetime,
                    market: Mapping[str, Any]) -> dict[str, Any]:
    """DOB NOW alphanumeric job IDs MUST NOT masquerade as old BIS job URLs."""
    from empire_os.lead_sources.nyc_dobnow import DATASET_PAGE, JOB

    raw = row.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    job = raw.get("job_filing_number")
    filed = _official_day(raw.get("filing_date"))
    issued = _official_day(raw.get("issued_date"))
    first = _official_day(raw.get("first_permit_date"))
    bbl = _id(raw.get("bbl"), (10,))
    bin_id = _id(raw.get("bin"), (7,))
    codes = raw.get("work_types")
    valid_codes = (isinstance(codes, list)
                   and 1 <= len(codes) <= 40
                   and all(isinstance(x, str) and
                           re.fullmatch(r"[A-Za-z0-9_ -]{1,60}", x)
                           for x in codes))
    trusted = (
        row.get("source") == "permits_nyc_dobnow"
        and row.get("url") == DATASET_PAGE
        and isinstance(job, str) and JOB.fullmatch(job) is not None
        and raw.get("official_event_crosscheck") is True
        and filed is not None and issued is not None
        and first == issued and filed <= issued
        and raw.get("filing_reason") == "Initial Permit"
        and raw.get("permit_status") == "Permit Issued"
        and bbl is not None and bin_id is not None
        and valid_codes
    )
    if not trusted:
        stage = "UNTRUSTED_SOURCE_OR_MISSING_FILING_DATE"
    elif filed > now or issued > now:
        stage = "SOURCE_DATE_CONFLICT"
    elif _recent(issued, now):
        stage = "RECENT_ISSUANCE_FOR_PROJECT_REVIEW"
    else:
        stage = "HISTORICAL_PROJECT_SOURCE_ONLY"
    recent = stage == "RECENT_ISSUANCE_FOR_PROJECT_REVIEW"
    first_seen = _time(row.get("created_at"))
    last_seen = _time(row.get("last_seen_at"))
    market_row = (market.get("markets") or {}).get("general_contractor") or {}
    return {
        "project_ref": ("nyc_dobnow_job:" + job) if trusted else None,
        "source_evidence_url": DATASET_PAGE if trusted else None,
        "source_kind": ("NYC_DOBNOW_TWO_OFFICIAL_DATASET_EVENT"
                        if trusted else "UNTRUSTED"),
        "job_type_code": None,
        "work_type_code": ("MULTI" if valid_codes and len(codes) > 1 else
                           str(codes[0])[:32] if valid_codes else None),
        "industry_hypothesis": "general_contractor",
        "industry_basis": "GENERAL_CATEGORY_UNVERIFIED",
        "borough": str(raw.get("borough") or "")[:24] if trusted else None,
        "filing_status": None,
        "permit_status": "Permit Issued" if trusted else None,
        "first_imported_at": first_seen.isoformat() if first_seen else None,
        "last_source_observed_at": last_seen.isoformat() if last_seen else None,
        "official_source_run_date": None,
        "original_filing_date": filed.date().isoformat() if filed else None,
        "original_issuance_date": issued.date().isoformat() if issued else None,
        "date_truth_classification": stage,
        "genuine_recent_project_event_observed": recent,
        "property_reference": {
            "bbl": bbl if trusted else None,
            "bin": bin_id if trusted else None,
            "state": ("OFFICIAL_REFERENCE_NOT_INDEPENDENTLY_PROPERTY_VERIFIED"
                      if trusted else "MISSING"),
            "same_source_as_permit": True,
        },
        "identity_roles": {
            "owner_business_name_present_in_original": False,
            "permittee_business_name_present_in_original": False,
            "owner_and_permittee_must_not_be_conflated": True,
            "company_identity_independently_verified": False,
            "contact_details_exported": False,
        },
        "market_gps_context": {
            "state": market.get("state"), "niche": "general_contractor",
            "commercial_demand_state": market_row.get("commercial_demand_state"),
            "observed_reply_count": market_row.get("commercial_reply_count"),
            "approved_buyer_count": market_row.get("approved_buyer_count"),
            "matched_to_this_specific_project": False,
        },
        "intelligence_checks": {
            "permit_source_trust": ("TWO_OFFICIAL_DOB_DATASETS_CORROBORATED"
                                    if trusted else "HOLD"),
            "project_event_recency": stage,
            "cross_source_property_join": "NOT_INDEPENDENTLY_VERIFIED",
            "storm_damage_or_insurance_claim": "UNKNOWN",
            "real_business_buyer_interest": "UNKNOWN",
            "commercial_terms_or_revenue": "UNKNOWN",
            "model_review_performed": False,
            "resale_rights_independently_verified": False,
        },
        "route": {
            "department": "market_intelligence",
            "secondary_department": "product" if trusted else None,
            "action": ("REVIEW_CURRENT_OFFICIAL_ISSUANCE"
                       if recent else "HISTORICAL_DATA_QUALITY_REVIEW"),
            "sales_promotion_authorized": False,
            "external_contact_authorized": False,
        },
        "execution_authority": "none",
        "buyer_demand_proven": False, "realised_revenue_proven": False,
    }


def _dossier(row: Mapping[str, Any], now: datetime,
             market: Mapping[str, Any]) -> dict[str, Any]:
    if row.get("source") == "permits_nyc_dobnow":
        return _dossier_dobnow(row, now, market)
    raw = row.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    job = _id(raw.get("job__"), (6, 7, 8, 9, 10, 11, 12)) or ""
    official = _official_url(row.get("url"), job)
    first_recorded = _time(row.get("created_at"))
    last_seen = _time(row.get("last_seen_at"))
    filing = _official_day(raw.get("filing_date"))
    issued = _official_day(raw.get("issuance_date"))
    source_run = _official_day(raw.get("dobrundate"))
    status = _code(raw.get("permit_status"))
    filing_status = _code(raw.get("filing_status"))
    job_type = _code(raw.get("job_type"), limit=5)
    work_type = _code(raw.get("work_type"), limit=5)
    borough = _code(raw.get("borough"), limit=20)
    bbl = _id(raw.get("bbl"), (10,))
    bin_id = _id(raw.get("bin__"), (7,))
    niche = DIRECT_WORK_TYPES.get(work_type or "", "general_contractor")
    if not official or not filing:
        stage = "UNTRUSTED_SOURCE_OR_MISSING_FILING_DATE"
    elif (issued is not None and issued > now) or (filing is not None and filing > now):
        stage = "SOURCE_DATE_CONFLICT"
    elif status == "ISSUED" and _recent(issued, now):
        stage = "RECENT_ISSUANCE_FOR_PROJECT_REVIEW"
    elif _recent(filing, now):
        stage = "RECENT_FILING_FOR_PROJECT_REVIEW"
    else:
        stage = "HISTORICAL_PROJECT_SOURCE_ONLY"
    candidate = stage in ("RECENT_ISSUANCE_FOR_PROJECT_REVIEW",
                           "RECENT_FILING_FOR_PROJECT_REVIEW")
    market_row = (market.get("markets") or {}).get(niche, {})
    if not isinstance(market_row, dict):
        market_row = {}
    if not market_row and niche != "general_contractor":
        market_row = (market.get("markets") or {}).get("general_contractor", {})
        if not isinstance(market_row, dict):
            market_row = {}
    # Primary records can contain names, phone, street and insurance details.
    # ONLY schema-selected reference fields and boolean presence are exposed.
    return {
        "project_ref": f"nyc_dob_job:{job}" if official else None,
        "source_evidence_url": official,
        "source_kind": "NYC_OFFICIAL_PERMIT_OBSERVED" if official else "UNTRUSTED",
        "job_type_code": job_type,
        "work_type_code": work_type,
        "industry_hypothesis": niche,
        "industry_basis": "EXPLICIT_WORK_TYPE_CODE" if niche != "general_contractor"
                          else "GENERAL_CATEGORY_UNVERIFIED",
        "borough": borough,
        "filing_status": filing_status,
        "permit_status": status,
        "first_imported_at": first_recorded.isoformat() if first_recorded else None,
        "last_source_observed_at": last_seen.isoformat() if last_seen else None,
        "official_source_run_date": source_run.date().isoformat() if source_run else None,
        "original_filing_date": filing.date().isoformat() if filing else None,
        "original_issuance_date": issued.date().isoformat() if issued else None,
        "date_truth_classification": stage,
        "genuine_recent_project_event_observed": candidate,
        "property_reference": {
            "bbl": bbl,
            "bin": bin_id,
            "state": "OFFICIAL_REFERENCE_NOT_INDEPENDENTLY_PROPERTY_VERIFIED"
                     if bbl or bin_id else "MISSING",
            "same_source_as_permit": True,
        },
        "identity_roles": {
            "owner_business_name_present_in_original": bool(
                str(raw.get("owner_s_business_name") or "").strip()
            ),
            "permittee_business_name_present_in_original": bool(
                str(raw.get("permittee_s_business_name") or "").strip()
            ),
            "owner_and_permittee_must_not_be_conflated": True,
            "company_identity_independently_verified": False,
            "contact_details_exported": False,
        },
        "market_gps_context": {
            "state": market.get("state"),
            "niche": niche if market_row else None,
            "commercial_demand_state": market_row.get("commercial_demand_state"),
            "observed_reply_count": market_row.get("commercial_reply_count"),
            "approved_buyer_count": market_row.get("approved_buyer_count"),
            "matched_to_this_specific_project": False,
        },
        "intelligence_checks": {
            "permit_source_trust": "OFFICIAL_URL_VERIFIED" if official else "HOLD",
            "project_event_recency": stage,
            "cross_source_property_join": "NOT_INDEPENDENTLY_VERIFIED",
            "storm_damage_or_insurance_claim": "UNKNOWN",
            "real_business_buyer_interest": "UNKNOWN",
            "commercial_terms_or_revenue": "UNKNOWN",
            "model_review_performed": False,
            "resale_rights_independently_verified": False,
        },
        "route": {
            "department": "market_intelligence",
            "secondary_department": "product" if bbl or bin_id else None,
            "action": "REVERIFY_OFFICIAL_PROJECT" if candidate
                      else "HISTORICAL_DATA_QUALITY_REVIEW",
            "sales_promotion_authorized": False,
            "external_contact_authorized": False,
        },
        "execution_authority": "none",
        "buyer_demand_proven": False,
        "realised_revenue_proven": False,
    }


def classify_permit_event_source(
    signal: Mapping[str, Any], *, now: datetime | None = None,
) -> dict[str, Any]:
    """Shared, safe commercial candidate gate for a *true* event date.

    A permittee business can exist in an old public record, but the age of
    the latest import or official portal refresh is NOT a new project.
    """
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    project = _dossier(signal, now, {"state": "NO_MARKET_MATCH"})
    return {
        "date_truth_classification": project["date_truth_classification"],
        "official_source_verified": project["source_evidence_url"] is not None,
        "genuine_recent_project_event_observed": (
            project["genuine_recent_project_event_observed"]
        ),
        "owner_permittee_role_separation_required": True,
        "buyer_demand_verified": False,
        "execution_authority": "none",
    }


def analyze_permit_project_intelligence(
    repo_root: str | Path, *, now: datetime | None = None,
    max_dossiers: int = 3,
) -> dict[str, Any]:
    """Current intake cohort analysed against true official event chronology.

    No mutation, network calls, inference-provider usage, or business contact.
    """
    if not 1 <= max_dossiers <= MAX_REVIEW_DOSSIERS:
        raise ValueError("max_dossiers must be 1-5")
    root = Path(repo_root)
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    inbox = _read(root / INBOX)
    gps = _market_summary(_read(root / MARKET_GPS), now)
    cohort: list[tuple[str, Mapping[str, Any]]] = []
    durable_digest_inputs: list[tuple[Any, ...]] = []
    counts: Counter[str] = Counter()
    for value in inbox.values():
        if not isinstance(value, Mapping) or value.get("source") not in PERMIT_SOURCES:
            continue
        raw = value.get("raw")
        raw = raw if isinstance(raw, Mapping) else {}
        signal_id = str(value.get("signal_id") or "")
        # Stable source semantics fingerprint includes meaningful changes to
        # any permit (new issuance, filing, project status, building ID), not
        # rolling 24-hour windows nor raw personal/owner contact information.
        if signal_id and len(signal_id) <= 128:
            durable_digest_inputs.append((
                signal_id, value.get("source"),
                raw.get("job__") or raw.get("job_filing_number"),
                raw.get("filing_date"),
                raw.get("issuance_date") or raw.get("issued_date"),
                raw.get("first_permit_date"), raw.get("permit_status"),
                raw.get("filing_status"), raw.get("work_type"),
                tuple(raw.get("work_types") or ()),
                raw.get("job_type"), raw.get("bbl"),
                raw.get("bin__") or raw.get("bin"),
            ))
        first = _time(value.get("created_at"))
        if first is not None and timedelta(0) <= now - first <= timedelta(hours=COHORT_HOURS):
            cohort.append((first.isoformat(), value))
    cohort.sort(key=lambda item: (item[0], str(item[1].get("signal_id") or "")),
                reverse=True)
    reviewed: list[dict[str, Any]] = []
    for _, value in cohort:
        d = _dossier(value, now, gps)
        counts["first_imported_last_24h"] += 1
        if d["source_evidence_url"] is not None:
            counts["official_provenance_url_passed"] += 1
        status = d["date_truth_classification"]
        counts[status] += 1
        if d["genuine_recent_project_event_observed"]:
            counts["recent_original_filing_or_issuance"] += 1
        if d["property_reference"]["state"].startswith("OFFICIAL_"):
            counts["property_reference_present_unverified"] += 1
        if d["identity_roles"]["owner_business_name_present_in_original"]:
            counts["owner_label_present_not_verified"] += 1
        if d["identity_roles"]["permittee_business_name_present_in_original"]:
            counts["permittee_label_present_not_verified"] += 1
        reviewed.append(d)
    # Genuine recent events first, then a small quality-control sample.
    reviewed.sort(key=lambda d: (
        not d["genuine_recent_project_event_observed"],
        d["project_ref"] or "",
    ))
    dossiers = reviewed[:max_dossiers]
    digest = sha256(json.dumps(
        sorted(durable_digest_inputs, key=lambda x: str(x[0])),
        separators=(",", ":"), default=str,
    ).encode()).hexdigest() if durable_digest_inputs else None
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "generated_at": now.isoformat(),
        "source": str(INBOX),
        "intelligence_engines_consulted": [
            "official_permit_filing_and_issuance_chronology",
            "first_party_market_gps_aggregated_commercial_evidence",
            "canonical_property_reference_readiness",
            "existing_department_source_router",
        ],
        "market_gps": {
            "state": gps["state"],
            "generated_at": gps.get("generated_at"),
            "available_nyc_niches": sorted((gps.get("markets") or {}).keys()),
            "market_aggregate_is_not_project_demand": True,
        },
        "cohort": {
            "first_imported_last_24h": counts["first_imported_last_24h"],
            "official_provenance_url_passed": counts["official_provenance_url_passed"],
            "recent_original_filing_or_issuance": counts[
                "recent_original_filing_or_issuance"],
            "historical_project_source_only": counts[
                "HISTORICAL_PROJECT_SOURCE_ONLY"],
            "untrusted_or_missing_date": counts[
                "UNTRUSTED_SOURCE_OR_MISSING_FILING_DATE"] + counts[
                    "SOURCE_DATE_CONFLICT"],
            "property_reference_present_unverified": counts[
                "property_reference_present_unverified"],
            "owner_label_present_not_verified": counts[
                "owner_label_present_not_verified"],
            "permittee_label_present_not_verified": counts[
                "permittee_label_present_not_verified"],
            "newly_imported_does_not_mean_new_filing": True,
        },
        "review_dossiers": dossiers,
        "review_dossier_count": len(dossiers),
        "total_retained_source_semantics_digest": digest,
        "review_work_state": "HISTORICAL_SOURCE_QUALITY_REVIEW"
            if not counts["recent_original_filing_or_issuance"]
            else "SOME_RECENT_EVENTS_REQUIRE_INDEPENDENT_VERIFICATION",
        "commercial_qualification_state": "NOT_VERIFIED",
        "buyer_matched": False,
        "independent_cross_source_property_match_proven": False,
        "automatic_sales_promotion": False,
        "outbound_sent": False,
        "payment_executed": False,
        "recognised_revenue_proven": False,
        "paid_model_invoked": False,
        "execution_authority": "none",
    }
