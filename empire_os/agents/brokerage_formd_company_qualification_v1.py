"""Form D SEC issuer qualification for EXISTING Search Fabric + Data Brokerage.

Qualifies *issuer filings*, NOT independently proven startup legal entities or
realised financing. Uses only the exact first-party SEC XML linked by the
previously signed original owner source report, followed by existing verified
buyer-fit aggregate readback. No new timer, credential, CRM write, outreach
or commercial distribution. Does not save officers, contacts or other PII.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from empire_os.search_fabric.sec_formd_source_quality_v1 import digest, atomic_private
from empire_os.supply_quality_twin import SupplyQualityObservation, build_supply_quality_twin

SCHEMA = "empire.brokerage.sec_formd_issuer_qualification.v1"
MAX_DOCS = 12
MAX_XML_BYTES = 150_000
MAX_SOURCE_AGE = timedelta(hours=48)
SECTOR_DENY = {"Pooled Investment Fund", "Hedge Fund", "Private Equity Fund"}
FINANCIAL_SECTOR = re.compile(r"\b(?:banking|financial services|investing|asset management|insurance|broker|investment bank)\b", re.I)
FUND_NAME = re.compile(r"\b(?:fund|feeder|portfolio|investment vehicle|bancshares|holdings|parent|strategic value)\b", re.I)
OPERATING_TYPES = {"Corporation", "Limited Liability Company", "Limited Partnership"}
FILING_PATH = re.compile(r"^https://www[.]sec[.]gov/Archives/edgar/data/([1-9][0-9]{0,9})/([0-9]{10}-[0-9]{2}-[0-9]{6})[.]txt$")
SOURCE_REUSE = "US_GOV_SEC_OFFICIAL_FILING_METADATA_RESEARCH"
USER_AGENT = "Empire AI research phil@empire-ai.co.uk"


def _time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def _issuer_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _number(value: Any) -> int | None:
    if not isinstance(value, str) or not value.isascii() or not re.fullmatch(r"[0-9]{1,15}", value):
        return None
    number = int(value)
    return number if 0 <= number <= 100_000_000_000_000 else None


def _text(root: ET.Element, path: str) -> str | None:
    node = root.find(path)
    return node.text.strip() if node is not None and node.text is not None else None


def parse_formd_xml(raw: bytes, *, evidence: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Read SEC-reported company-level fields only; never store officer details."""
    if not isinstance(raw, bytes) or not 100 <= len(raw) <= MAX_XML_BYTES:
        raise ValueError("sec_issuer_xml_payload_invalid")
    if any(k not in evidence for k in ("cik", "company_filer_name", "form_type", "evidence_url", "evidence_id", "filed_date")):
        raise ValueError("source_reference_missing")
    match = FILING_PATH.fullmatch(evidence["evidence_url"])
    if not match or match.group(1) != evidence["cik"]:
        raise ValueError("untrusted_original_sec_filing_url")
    try:
        doc = ET.fromstring(raw)
    except ET.ParseError:
        raise ValueError("malformed_sec_filing_xml") from None
    if doc.tag != "edgarSubmission" or _text(doc, "testOrLive") != "LIVE":
        raise ValueError("non_live_form_d")
    form = _text(doc, "submissionType")
    cik = _text(doc, "./primaryIssuer/cik")
    name = _text(doc, "./primaryIssuer/entityName")
    if form != evidence["form_type"] or not cik or not cik.isdecimal() or int(cik) != int(evidence["cik"]):
        raise ValueError("sec_filing_cik_or_form_type_mismatch")
    if not name or _issuer_name(name) != _issuer_name(evidence["company_filer_name"]):
        raise ValueError("sec_filing_company_name_mismatch")
    industry = _text(doc, "./offeringData/industryGroup/industryGroupType")
    entity_type = _text(doc, "./primaryIssuer/entityType")
    state = _text(doc, "./primaryIssuer/issuerAddress/stateOrCountry")
    state = state if state and re.fullmatch(r"[A-Z0-9]{2,3}", state) else None
    sale_date = _text(doc, "./offeringData/typeOfFiling/dateOfFirstSale/value")
    if sale_date:
        try:
            dt = datetime.fromisoformat(sale_date).date()
            if dt > now.date() + timedelta(days=1):
                raise ValueError("future_sales_date")
        except ValueError:
            raise ValueError("sec_first_sale_date_invalid") from None
    amount_sold = _number(_text(doc, "./offeringData/offeringSalesAmounts/totalAmountSold"))
    amount_offered = _number(_text(doc, "./offeringData/offeringSalesAmounts/totalOfferingAmount"))
    reported_investor_count = _number(_text(doc, "./offeringData/investors/totalNumberAlreadyInvested"))
    revenue_range = _text(doc, "./offeringData/issuerSize/revenueRange")
    # The SEC's issuer classification is primary evidence of sector, not
    # independent corporate registration and not proof of startup age.
    is_fund = industry in SECTOR_DENY or bool(FUND_NAME.search(name))
    is_finance = bool(FINANCIAL_SECTOR.search(industry or ""))
    explicit_operating = (
        not is_fund and not is_finance and
        entity_type in OPERATING_TYPES and
        isinstance(industry, str) and industry not in {"Other", ""}
    )
    if is_fund:
        tier = "FUND_OR_NON_OPERATING_VEHICLE_EXCLUDED"
    elif is_finance:
        tier = "FINANCIAL_ISSUER_RESEARCH_HOLD"
    elif explicit_operating:
        tier = "SEC_SECTOR_CANDIDATE_NEEDS_INDEPENDENT_COMPANY_CORROBORATION"
    else:
        tier = "UNCLEAR_ISSUER_NEEDS_INDEPENDENT_COMPANY_CORROBORATION"
    return {
        "evidence_id": evidence["evidence_id"],
        "cik": evidence["cik"],
        "sec_issuer_name": name,
        "sec_issuer_type": entity_type,
        "issuer_state_or_country": state,
        "sec_industry_group": industry,
        "sec_revenue_range_reported": revenue_range,
        "filing_type": form,
        "index_filed_date": evidence["filed_date"],
        "sec_primary_doc_url": (
            f"https://www.sec.gov/Archives/edgar/data/{match.group(1)}/"
            f"{match.group(2).replace('-', '')}/primary_doc.xml"
        ),
        "sec_official_index_url": evidence["evidence_url"],
        "first_sale_date_reported": sale_date,
        "total_offering_amount_reported_usd": amount_offered,
        "total_amount_sold_reported_usd": amount_sold,
        "reported_number_of_investors": reported_investor_count,
        "issuer_sector_classification_supported_by_sec": explicit_operating,
        "sec_issuer_financial_sector_held": is_finance,
        "qualification_tier": tier,
        "self_reported_formd_financials": True,
        "actual_capital_received_independently_verified": False,
        "startup_stage_independently_verified": False,
        "independent_corporate_registry_verified": False,
        "named_investor_relationship_verified": False,
        "data_rights_status": SOURCE_REUSE,
        "pii_retained": False,
        "buyer_purchase_request_verified": False,
    }


def fetch_formd_xml(evidence: Mapping[str, Any], *, timeout: float = 6.0) -> bytes:
    ref = evidence.get("evidence_url")
    m = FILING_PATH.fullmatch(ref) if isinstance(ref, str) else None
    if not m or m.group(1) != evidence.get("cik"):
        raise ValueError("untrusted_sec_ref")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{m.group(1)}/"
        f"{m.group(2).replace('-', '')}/primary_doc.xml"
    )
    with urlopen(Request(url, method="GET", headers={
        "User-Agent": USER_AGENT, "Accept": "application/xml",
    }), timeout=min(8.0, max(1.0, timeout))) as res:
        if res.status != 200:
            raise OSError("sec_document_non_200")
        data = res.read(MAX_XML_BYTES+1)
    if not 100 <= len(data) <= MAX_XML_BYTES:
        raise ValueError("sec_document_too_large")
    return data


def read_signed_source(source: Mapping[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    if not isinstance(source, Mapping) or source.get("schema_version") != "empire.search_fabric.sec_formd_source_quality.v1":
        raise ValueError("original_sec_owner_schema_required")
    expected = source.get("integrity_sha256")
    body = dict(source)
    body.pop("integrity_sha256", None)
    if expected != digest(body):
        raise ValueError("tampered_original_sec_source_receipt")
    observed = _time(source.get("as_of"))
    if observed is None or observed > now + timedelta(minutes=5) or now - observed > MAX_SOURCE_AGE:
        raise ValueError("stale_or_future_sec_source_receipt")
    items = source.get("source_candidate_index", source.get("source_candidate_preview"))
    if (source.get("customer_data_distribution_enabled") is not False
            or source.get("individual_startups_independently_verified") != 0
            or type(source.get("official_sec_index_filer_records")) is not int
            or not 1 <= source["official_sec_index_filer_records"] <= 750
            or not isinstance(items, list) or len(items) > 750
            or (source.get("source_records_complete_in_private_receipt") is True
                and len(items) != source["official_sec_index_filer_records"])):
        raise ValueError("original_sec_source_authority_invalid")
    seen = set()
    allowed = []
    for item in items:
        if not isinstance(item, dict) or item.get("form_type") not in {"D","D/A"}:
            raise ValueError("untrusted_sec_candidate")
        if item.get("evidence_id") in seen:
            raise ValueError("duplicate_sec_filing_in_original_preview")
        seen.add(item["evidence_id"])
        if not isinstance(item.get("evidence_id"), str) or not re.fullmatch("[a-f0-9]{64}", item["evidence_id"]):
            raise ValueError("invalid_sec_evidence_id")
        if (FILING_PATH.fullmatch(item.get("evidence_url", "")) is None
                or item.get("sec_filing_record_verified") is not True
                or item.get("startup_stage_verified") is not False):
            raise ValueError("untrusted_sec_preview_evidence")
        allowed.append(dict(item))
    return allowed


def evaluate_buyer_fitness(buyer: Mapping[str, Any]) -> dict[str, Any]:
    """Only reuse existing validated buyer-fit summaries, no personal records."""
    if (not isinstance(buyer, Mapping)
            or buyer.get("schema_version") != "empire.data_brokerage.first_party_buyer_fit.v1"
            or buyer.get("crm_writes") is not False
            or buyer.get("outbound_authorized") is not False
            or buyer.get("revenue_verified") is not False):
        raise ValueError("untrusted_original_buyer_fit_owner")
    requests = buyer.get("research_purchase_requests_verified")
    orgs = buyer.get("total_organisations")
    rows = buyer.get("classification")
    if (type(requests) is not int or requests < 0
            or type(orgs) is not int or not 0 <= orgs <= 150
            or not isinstance(rows, list) or len(rows) != orgs):
        raise ValueError("untrusted_original_buyer_fit_counts")
    if requests != sum(r.get("direct_report_purchase_request_verified") is True for r in rows if isinstance(r, Mapping)):
        raise ValueError("reported_buyer_requests_do_not_match_records")
    startup_intel_request_count = sum(
        r.get("direct_report_purchase_request_verified") is True
        and r.get("original_product") == "startup_intelligence"
        for r in rows if isinstance(r, Mapping)
    )
    return {
        "original_buyer_fit_source_evaluated_at": buyer.get("evaluated_at"),
        "original_buyer_fit_organisations": orgs,
        "original_research_purchase_requests_verified": requests,
        "startup_intelligence_purchase_requests_verified": startup_intel_request_count,
        "first_party_product_fit_not_inferred": startup_intel_request_count == 0,
        "buyer_delivery_authorized_by_this_review": False,
        "crm_mutations": False,
        "sales_made": None,
        "next_sales_action": "RESEARCH_FIRST_PARTY_BUYBOX_FOR_FUNDRAISING_COMPANY_INTELLIGENCE",
    }


def summarize_same_day_multi_filers(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Index-only duplicate-risk signal; do not manufacture financing events.

    A shared SEC CIK is evidence of the same filer, NOT definitive proof of a
    single offering. Amendments can change material details; all original
    accession references remain attached for original-document comparison.
    """
    if not isinstance(items, list) or len(items) > 750:
        raise ValueError("unbounded_original_sec_index_grouping")
    by_cik: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if (not isinstance(item, dict) or not isinstance(item.get("cik"), str)
                or not re.fullmatch(r"[1-9][0-9]{0,9}", item["cik"])
                or item.get("form_type") not in ("D", "D/A")
                or FILING_PATH.fullmatch(str(item.get("evidence_url") or "")) is None):
            raise ValueError("invalid_original_sec_index_grouping_record")
        by_cik.setdefault(item["cik"], []).append(item)
    groups = [
        {
            "cik": cik,
            "filing_count": len(rows),
            "form_types": sorted({row["form_type"] for row in rows}),
            "source_accession_urls": sorted(row["evidence_url"] for row in rows),
            "review_state": "SAME_FILER_MULTI_RECORD_REVIEW_ORIGINAL_AMENDMENT_FIELDS",
            "same_offering_independently_verified": False,
            "new_capital_transfer_verified": False,
        }
        for cik, rows in sorted(by_cik.items())
        if len(rows) > 1
    ]
    return {
        "status": "SEC_OFFICIAL_INDEX_REPEATED_FILER_REVIEW",
        "scope": "SAME_DAY_SAME_SEC_CIK_NOT_SAME_CONFIRMED_OFFERING",
        "source_index_records": len(items),
        "unique_filer_ciks": len(by_cik),
        "multi_filing_cik_count": len(groups),
        "filings_in_multi_filing_groups": sum(group["filing_count"] for group in groups),
        "additional_rows_above_one_per_cik": sum(group["filing_count"]-1 for group in groups),
        "groups": groups[:24],
        "group_preview_truncated": len(groups) > 24,
        "financial_delta_verified_by_index_only": False,
        "independently_verified_new_funding_events": 0,
        "customer_distribution_authorized": False,
        "extra_external_requests": 0,
    }


def review_same_day_amendment_xml(
    source_rows: list[dict[str, Any]], *, now: datetime,
    fetch: Callable[..., bytes], max_groups: int = 3,
    max_docs: int = 9,
) -> dict[str, Any]:
    """Bounded primary-source D/A check within original six-hour SEC owner.

    Only repeated same-day filer groups with both D and D/A qualify. Each
    accession is parsed independently. Failures remain explicitly held and
    incomplete groups are never promoted as verified numeric comparisons.
    """
    if not isinstance(source_rows, list) or len(source_rows) > 750 or max_groups != 3 or max_docs != 9:
        raise ValueError("amendment_original_owner_bounds_required")
    index = summarize_same_day_multi_filers(source_rows)
    lookup = {r["evidence_url"]: r for r in source_rows}
    selected: list[dict[str, Any]] = []
    blocked_groups: list[dict[str, Any]] = []
    for g in index["groups"]:
        if not {"D", "D/A"}.issubset(g["form_types"]):
            continue
        members = [lookup[ref] for ref in g["source_accession_urls"]]
        if len(members) > max_docs or len(selected) + len(members) > max_docs or len(selected) and len(selected) >= max_docs:
            blocked_groups.append({"cik": g["cik"], "reason": "BOUNDED_GROUP_NOT_SELECTED"})
            continue
        if len({r["cik"] for r in selected}) >= max_groups:
            blocked_groups.append({"cik": g["cik"], "reason": "BOUNDED_GROUP_NOT_SELECTED"})
            continue
        selected.extend(members)
    verified_by_cik: dict[str, list[dict[str, Any]]] = {}
    failure_ciks: set[str] = set()
    for row in selected:
        try:
            original_xml = fetch(row)
            parsed = parse_formd_xml(original_xml, evidence=row, now=now)
            verified_by_cik.setdefault(row["cik"], []).append(parsed)
        except (OSError, TimeoutError, ValueError, TypeError, KeyError, ET.ParseError):
            failure_ciks.add(row["cik"])
    verified = [record for cik, records in sorted(verified_by_cik.items())
                if cik not in failure_ciks for record in records]
    change_report = compare_same_issuer_amendments(verified)
    status = ("AMENDMENT_SOURCE_REVIEW_PARTIAL_HOLD" if failure_ciks or blocked_groups
              else "AMENDMENT_SOURCE_REVIEW_VERIFIED" if change_report["amendments_compared_to_prior_document"]
              else "AMENDMENT_NO_COMPARABLE_DOCUMENTS")
    return {
        "status": status,
        "official_xml_requests_attempted": len(selected),
        "official_xml_documents_validated": sum(len(v) for cik, v in verified_by_cik.items()
                                                 if cik not in failure_ciks),
        "failed_group_ciks": sorted(failure_ciks),
        "bounded_group_holds": blocked_groups,
        "signed_comparison": change_report,
        "source_lineage_is_original_signed_index": True,
        "independently_confirmed_financings": 0,
        "customer_release_authorized": False,
    }


def qualify(*, source: Mapping[str, Any], buyer: Mapping[str, Any],
            now: datetime, fetch: Callable[..., bytes] = fetch_formd_xml,
            fetch_submission: Callable[[str], Mapping[str, Any]] | None = None,
            previous_ids: set[str] | None = None, limit: int = MAX_DOCS) -> dict[str, Any]:
    if now.tzinfo is None or not 1 <= limit <= MAX_DOCS:
        raise ValueError("aware_clock_and_bounded_limit_required")
    now = now.astimezone(timezone.utc)
    candidates = read_signed_source(source, now=now)
    repeated_filer_index = summarize_same_day_multi_filers(candidates)
    buyer_review = evaluate_buyer_fitness(buyer)
    previously = previous_ids if previous_ids is not None else set()
    if len(previously) > 1000 or any(not re.fullmatch("[a-f0-9]{64}", x) for x in previously):
        raise ValueError("invalid_existing_doc_identity_history")
    # Prioritise recently filed NEW D disclosures, then non-obvious fund
    # vehicles and high SEC CIKs as a *weak search-efficiency heuristic*.
    # SEC CIK sequence is NOT company formation date or startup proof.
    # This prevents old registered listed firms dominating each bounded
    # owner refresh. CIK-dedupe avoids repeated accession requests.
    unique_issuer = {}
    for item in sorted(candidates, key=lambda r: (
            r["form_type"] != "D",
            bool(FUND_NAME.search(r["company_filer_name"])),
            -int(r["cik"]), r["evidence_id"])):
        if item["cik"] not in unique_issuer and item["evidence_id"] not in previously:
            unique_issuer[item["cik"]] = item
    selected = list(unique_issuer.values())[:limit]
    reviews, held = [], Counter()
    submission_reader = fetch_submission or fetch_sec_company_submission
    processed = set()
    for item in selected:
        try:
            data = fetch(item)
            review = parse_formd_xml(data, evidence=item, now=now)
            submission_confirmed = False
            try:
                submission = submission_reader(item["cik"])
                review = crosscheck_sec_submission(review, submission)
                submission_confirmed = True
            except (OSError, TimeoutError, ValueError, TypeError, KeyError):
                review["sec_submission_cik_confirmed"] = False
                review["sec_submission_current_name_matches_filing"] = False
                review["sec_existence_of_listing_evidence"] = None
                review["qualification_tier"] = "SEC_SUBMISSIONS_CROSSCHECK_UNAVAILABLE_HOLD"
                review["issuer_sector_classification_supported_by_sec"] = False
                held["SEC_SUBMISSIONS_CROSSCHECK_UNAVAILABLE_OR_MISMATCH"] += 1
            reviews.append(review)
            if submission_confirmed:
                processed.add(item["evidence_id"])
        except (OSError, TimeoutError, ValueError, TypeError, KeyError, ET.ParseError):
            held["SEC_ISSUER_XML_UNAVAILABLE_OR_IDENTITY_MISMATCH"] += 1
    twin_items = [
        SupplyQualityObservation(
            observation_key=f"sec_company_file:{r['evidence_id']}",
            supply_id=f"sec_company_cik:{r['cik']}",
            source_keys=("sec_edgar_formd_primary_doc",),
            product_key="startup_intelligence", market_key="us_exempt_offerings",
            evidence_refs=(r["sec_primary_doc_url"],),
            source_healthy=True,
            # SEC issuer identity does NOT prove independently registered company.
            identity_accepted=None,
            delivered=None, buyer_accepted=None, recognized_revenue_cents=None,
        ) for r in reviews
    ]
    if not twin_items:
        twin_items.append(SupplyQualityObservation(
            observation_key="no_successful_sec_company_docs",
            supply_id="no_successful_sec_company_docs",
            source_keys=("sec_edgar_formd_primary_doc",),
            product_key="startup_intelligence", market_key="us_exempt_offerings",
            evidence_refs=(source["index_url"],),
            source_healthy=False,
        ))
    twin = build_supply_quality_twin(
        twin_items, source_key="sec_edgar_formd_primary_doc",
        product_key="startup_intelligence", market_key="us_exempt_offerings",
    )
    if twin.canonical_writes or twin.source_policy_mutation or twin.execution_authority != "none":
        raise ValueError("original_supply_quality_twin_execution_invalid")
    counts = Counter(r["qualification_tier"] for r in reviews)
    result = {
        "schema_version": SCHEMA,
        "status": "SEC_FORMD_ORIGINAL_ISSUER_QUALIFICATION_REVIEW",
        "as_of": now.isoformat(),
        "original_sec_index_sha256": source["integrity_sha256"],
        "original_buyer_fit_evaluated_at": buyer_review["original_buyer_fit_source_evaluated_at"],
        "candidate_selection": "NEW_D_THEN_NON_FUND_NAME_THEN_DESCENDING_CIK_RESEARCH_ONLY",
        "cik_order_is_not_company_age_or_startup_stage": True,
        "selected_new_filing_count": len(selected),
        "same_day_multi_filer_index_review": repeated_filer_index,
        "independent_original_sec_docs_verified": len(reviews),
        "source_failure_count": sum(held.values()),
        "held_counts": dict(sorted(held.items())),
        "qualification_tiers": dict(sorted(counts.items())),
        "verified_sec_issuer_operating_sector_candidates": counts["SEC_SECTOR_CANDIDATE_NEEDS_INDEPENDENT_COMPANY_CORROBORATION"],
        "independently_verified_new_startups": 0,
        "verified_independent_company_registry_matches": 0,
        "reported_formd_financials_not_confirmed_capital_transfer": True,
        "buyer_fit": buyer_review,
        "original_supply_quality_twin": {
            "source_healthy_observation_count": twin.source_healthy_count,
            "buyer_accepted_count": twin.buyer_accepted_count,
            "commercial_outcome_count": twin.attributed_commercial_outcome_count,
            "independently_accepted_company_identity_count": twin.identity_accepted_count,
            "mode": twin.mode,
        },
        "qualified_research_candidates": reviews,
        "reviewed_source_evidence_ids": sorted(processed),
        "source_document_contact_information_exported": False,
        "customer_delivery_authorized": False,
        "outreach_sent": False,
        "production_database_writes": False,
        "revenue_verified": False,
    }
    result["integrity_sha256"] = digest(result)
    return result


# Original owner bounded cadence. It is run as a substep of the EXISTING
# Search Fabric scheduled source cycle; never a new scheduler or agent.
from pathlib import Path
from datetime import timedelta
import os
import stat
from empire_os.search_fabric.sec_formd_source_quality_v1 import atomic_private
import fcntl

STATE_SCHEMA = "empire.brokerage.sec_formd_company_review_owner_cursor.v1"
REFRESH_GAP = timedelta(hours=6)
CANONICAL_SEARCH_ROOT = Path("/srv/empire_os/runtime/search_fabric_evidence")
CANONICAL_BUYER_PATH = Path("/srv/empire_os/runtime/data_brokerage/first_party_buyer_fit_latest.json")


def _private_read(path: Path, *, cap: int) -> Mapping[str, Any]:
    if path.is_symlink():
        raise ValueError("original_owner_file_symlink")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > cap or meta.st_mode & 0o077:
            raise ValueError("untrusted_original_owner_evidence_custody")
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            return json.load(handle)
    finally:
        if fd >= 0:
            os.close(fd)


def run_original_owner_company_review(
    *, root: Path = CANONICAL_SEARCH_ROOT,
    buyer_path: Path = CANONICAL_BUYER_PATH,
    now: datetime | None = None,
    fetch: Callable[..., bytes] = fetch_formd_xml,
    fetch_submission: Callable[[str], Mapping[str, Any]] | None = None,
    limit: int = MAX_DOCS,
) -> dict[str, Any]:
    """Read original owner receipt and original existing buyer-fit owner.

    Does not read or mutate original CRM/DB. No private filer personal fields
    exported or archived.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_clock_required")
    now = now.astimezone(timezone.utc)
    if (root.is_symlink() or not root.is_dir() or buyer_path.is_symlink()
            or not 1 <= limit <= MAX_DOCS):
        raise ValueError("invalid_original_owner_source_location")
    lock_path = root / "sec_formd_company_review_owner.lock"
    if lock_path.is_symlink():
        raise ValueError("owner_company_review_lock_symlink")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as locker:
            fd = -1
            try:
                fcntl.flock(locker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"status": "SEC_FORMD_COMPANY_REVIEW_ALREADY_RUNNING", "external_requests": 0,
                        "outreach_sent": False, "db_writes": False}
            state_path = root / "sec_formd_company_review_owner_cursor_v1.json"
            review_path = root / "sec_formd_company_review_latest.json"
            if state_path.exists():
                state = _private_read(state_path, cap=180_000)
                if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA:
                    raise ValueError("untrusted_company_review_cursor")
                proof = state.get("integrity_sha256")
                frame = dict(state);frame.pop("integrity_sha256", None)
                if proof != digest(frame):
                    raise ValueError("tampered_company_review_cursor")
                tried = state.get("completed_evidence_ids")
                if (not isinstance(tried,list) or len(tried)>1000
                        or any(not isinstance(x,str) or re.fullmatch("[a-f0-9]{64}",x) is None
                               for x in tried)):
                    raise ValueError("invalid_company_review_history")
                last = _time(state.get("last_run_at"))
                if last is None or last > now + timedelta(minutes=5):
                    raise ValueError("invalid_company_review_runtime_clock")
                if now-last < REFRESH_GAP:
                    return {
                        "status": "SEC_FORMD_COMPANY_REVIEW_ALREADY_FRESH",
                        "external_requests": 0,
                        "last_review_at": last.isoformat(),
                        "company_operating_candidates": state["last_verified_sector_candidate_count"],
                        "completed_filing_reviews": len(tried),
                        "outreach_sent": False,
                        "db_writes": False,
                    }
                completed = set(tried)
            else:
                completed = set()
            source = _private_read(root/"sec_formd_source_quality_latest.json", cap=900_000)
            buyer = _private_read(buyer_path, cap=200_000)
            report = qualify(
                source=source, buyer=buyer, now=now,
                fetch=fetch, fetch_submission=fetch_submission,
                previous_ids=completed, limit=limit,
            )
            # Same original owner, same six-hour lock and verified source index.
            # A separate capped XML comparison never invents funding events.
            report["same_day_amendment_xml_comparison"] = review_same_day_amendment_xml(
                read_signed_source(source, now=now), now=now, fetch=fetch,
            )
            report["integrity_sha256"] = digest({
                k: v for k, v in report.items() if k != "integrity_sha256"
            })
            if report["production_database_writes"] or report["outreach_sent"] or report["customer_delivery_authorized"]:
                raise ValueError("company_review_authority_violation")
            updated = sorted(completed.union(
                r["evidence_id"] for r in report["qualified_research_candidates"]))
            updated = updated[-1000:]
            state = {
                "schema_version": STATE_SCHEMA,
                "last_run_at": now.isoformat(),
                "source_report_sha256": report["original_sec_index_sha256"],
                "completed_evidence_ids": updated,
                "last_verified_sector_candidate_count": report["verified_sec_issuer_operating_sector_candidates"],
                "last_qualification_receipt_sha256": report["integrity_sha256"],
            }
            state["integrity_sha256"] = digest(state)
            atomic_private(review_path, report)
            atomic_private(state_path, state)
            return {
                "status": report["status"],
                "original_source_sha256": report["original_sec_index_sha256"],
                "new_documents_qualified": report["independent_original_sec_docs_verified"],
                "funds_or_vehicles_excluded": report["qualification_tiers"].get(
                    "FUND_OR_NON_OPERATING_VEHICLE_EXCLUDED", 0),
                "operating_sector_candidates": report["verified_sec_issuer_operating_sector_candidates"],
                "new_startups_independently_verified": 0,
                "real_buyer_purchase_requests_from_existing_owner": report["buyer_fit"]["startup_intelligence_purchase_requests_verified"],
                "report_sha256": report["integrity_sha256"],
                "external_requests_upper_bound": limit * 2,
                "outreach_sent": False, "db_writes": False,
                "commercial_release": False,
            }
    finally:
        if fd >= 0: os.close(fd)


SEC_SUBMISSIONS_MAX_BYTES = 2_000_000


def fetch_sec_company_submission(cik: str, *, timeout: float = 6.0) -> Mapping[str, Any]:
    if not isinstance(cik, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", cik):
        raise ValueError("sec_company_cik_required")
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    with urlopen(Request(url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }), timeout=min(8, max(1, timeout))) as response:
        if response.status != 200:
            raise OSError("sec_submission_non_200")
        payload = response.read(SEC_SUBMISSIONS_MAX_BYTES+1)
    if not 100 <= len(payload) <= SEC_SUBMISSIONS_MAX_BYTES:
        raise ValueError("sec_submission_size_invalid")
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        raise ValueError("sec_submission_json_invalid") from None
    if not isinstance(data, dict):
        raise ValueError("sec_submission_not_object")
    return data


def crosscheck_sec_submission(
    row: Mapping[str, Any], submission: Mapping[str, Any],
) -> dict[str, Any]:
    """Corroborate current SEC registration and exclude listed issuers.

    This is an independent SEC endpoint, NOT independent legal registry or
    third-party startup-stage validation. Never disclose EIN, contacts or
    individual officers from the SEC submissions packet.
    """
    if not isinstance(submission, Mapping):
        raise ValueError("missing_sec_company_submission")
    cik = submission.get("cik")
    if isinstance(cik, bool) or not isinstance(cik, (str, int)) or not str(cik).isdecimal() or str(int(cik)) != row["cik"]:
        raise ValueError("sec_company_submission_cik_mismatch")
    name = submission.get("name")
    if not isinstance(name, str) or _issuer_name(name) != _issuer_name(row["sec_issuer_name"]):
        raise ValueError("sec_company_submission_name_mismatch")
    tickers = submission.get("tickers")
    exchanges = submission.get("exchanges")
    if (not isinstance(tickers, list) or len(tickers) > 30
            or not isinstance(exchanges, list) or len(exchanges) > 30
            or any(not isinstance(t, str) or re.fullmatch(r"[A-Z0-9.-]{1,12}", t) is None
                   for t in tickers)
            or any(not isinstance(e, str) or len(e) > 80 for e in exchanges)):
        raise ValueError("untrusted_sec_market_listing_evidence")
    result = dict(row)
    result["sec_submission_cik_confirmed"] = True
    result["sec_submission_current_name_matches_filing"] = True
    result["sec_reported_tickers"] = sorted(set(tickers))
    result["sec_reported_exchanges"] = sorted(set(exchanges))
    result["sec_existence_of_listing_evidence"] = bool(tickers or exchanges)
    if result["sec_existence_of_listing_evidence"]:
        result["qualification_tier"] = "SEC_LISTED_ISSUER_EXCLUDE_FROM_STARTUP_SHORTLIST"
        result["issuer_sector_classification_supported_by_sec"] = False
    result["separate_corporate_registry_check_completed"] = False
    result["not_listed_does_not_prove_private_or_early_stage"] = True
    return result


# A pure comparator for already verified company-only SEC XML projections.
# This never requests SEC data, changes the original scheduler or asserts funding.
def compare_same_issuer_amendments(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Report Form D/A numeric corrections, without inventing financing events.

    Input must be the privacy-minimised output of parse_formd_xml. Matching
    CIK, issuer name and first-sale date is only a possible same-offering
    cluster; it does NOT independently establish offering or corporate identity.
    """
    if not isinstance(rows, list) or len(rows) > MAX_DOCS:
        raise ValueError("bounded_official_xml_projection_required")
    xml_ref = re.compile(
        r"^https://www[.]sec[.]gov/Archives/edgar/data/([1-9][0-9]{0,9})/"
        r"([0-9]{18})/primary_doc[.]xml$"
    )
    numeric_fields = (
        "total_offering_amount_reported_usd",
        "total_amount_sold_reported_usd",
        "reported_number_of_investors",
    )
    groups: dict[tuple[str, str, str], list[tuple[str, Mapping[str, Any]]]] = {}
    seen_refs: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or row.get("self_reported_formd_financials") is not True:
            raise ValueError("verified_company_only_formd_projection_required")
        cik, name, sold_on = (row.get("cik"), row.get("sec_issuer_name"),
                              row.get("first_sale_date_reported"))
        ref, form = row.get("sec_primary_doc_url"), row.get("filing_type")
        match = xml_ref.fullmatch(ref) if isinstance(ref, str) else None
        if (not isinstance(cik, str) or not cik.isdecimal() or not match
                or str(int(match.group(1))) != str(int(cik))
                or not isinstance(name, str) or not _issuer_name(name)
                or not isinstance(sold_on, str) or not re.fullmatch(r"\d{4}-\d\d-\d\d", sold_on)
                or form not in {"D", "D/A"} or ref in seen_refs):
            raise ValueError("issuer_amendment_source_identity_invalid")
        for key in numeric_fields:
            val = row.get(key)
            if val is not None and (isinstance(val, bool) or not isinstance(val, int)
                                    or val < 0 or val > 100_000_000_000_000):
                raise ValueError("issuer_amendment_untrusted_numeric_value")
        seen_refs.add(ref)
        groups.setdefault((cik, _issuer_name(name), sold_on), []).append((match.group(2), row))
    comparisons: list[dict[str, Any]] = []
    for (cik, _, date), documents in sorted(groups.items()):
        # Filing-agent prefixes can differ for one CIK: accession lexical
        # order is NOT verified time order. Compare within same-day group
        # with D baseline preceding D/A; never assert actual chronology.
        documents.sort(key=lambda record: (record[1]["filing_type"] == "D/A", record[0]))
        for offset, (_, amended) in enumerate(documents):
            if amended["filing_type"] != "D/A":
                continue
            if offset == 0:
                # Do not invent an original filing that isn't in this sample.
                continue
            previous = documents[offset - 1][1]
            changed, unchanged, unknown = {}, [], []
            for key in numeric_fields:
                before, after = previous.get(key), amended.get(key)
                if before is None or after is None:
                    unknown.append(key)
                elif before != after:
                    changed[key] = {"before": before, "after": after,
                                    "difference_reported": after - before}
                else:
                    unchanged.append(key)
            comparisons.append({
                "cik": cik,
                "sec_issuer_name": amended["sec_issuer_name"],
                "first_sale_date_reported": date,
                "prior_primary_document_url": previous["sec_primary_doc_url"],
                "amended_primary_document_url": amended["sec_primary_doc_url"],
                "status": ("REPORTED_NUMERIC_CORRECTION_OBSERVED" if changed
                           else "NUMERIC_COMPARISON_INCOMPLETE" if unknown
                           else "COMPARED_NUMERIC_FIELDS_UNCHANGED"),
                "changed_fields": changed,
                "unchanged_fields": unchanged,
                "uncomparable_fields": unknown,
                "possible_same_offering_not_verified": True,
                "original_to_amendment_order_is_assumed_not_timestamp_verified": True,
                "numeric_difference_not_verified_cash_flow": True,
            })
    report: dict[str, Any] = {
        "schema_version": "empire.brokerage.sec_formd_amendment_numeric_comparison.v1",
        "official_original_xml_documents_compared": len(rows),
        "possible_same_offering_groups_observed": sum(len(v) > 1 for v in groups.values()),
        "amendments_compared_to_prior_document": len(comparisons),
        "amendments_with_numeric_changes": sum(
            bool(c["changed_fields"]) for c in comparisons),
        "amendments_with_unchanged_compared_numeric_fields": sum(
            c["status"] == "COMPARED_NUMERIC_FIELDS_UNCHANGED" for c in comparisons),
        "comparisons": comparisons,
        "economic_funding_events_independently_verified": 0,
        "issuer_corporate_registry_matches_independently_verified": 0,
        "commercial_distribution_authorized": False,
        "source_rights": "INTERNAL_OFFICIAL_SEC_RESEARCH_ONLY",
        "additional_network_requests_executed_by_comparator": 0,
        "crm_writes": False,
        "sales_outreach": False,
    }
    report["integrity_sha256"] = digest(report)
    return report
