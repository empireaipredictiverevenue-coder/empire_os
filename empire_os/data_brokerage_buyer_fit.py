"""Brokerage buyer-fit and deliverability on ORIGINAL reports, not lead counts.

The canonical Data Brokerage sample/qualified-domain report/site verifier
belong to existing Search Fabric and Brokerage owners. This module consumes
their signed-by-hash local evidence read-only and reuses original product/
monetisation contracts. No new CRM, buyer record, source scraper or sales offer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from collections.abc import Mapping
from typing import Any
import json
import re
import stat

from empire_os.data_brokerage_product_catalog import (
    validate_internal_brokerage_catalog,
)
from empire_os.data_brokerage_monetization_portfolio import (
    build_monetization_portfolio, validate_portfolio,
)

SCHEMA = "empire.data_brokerage.agency_buyer_fit.v1"
SAMPLE = Path("runtime/data_brokerage/agency_market_intelligence_sample_latest.json")
QUALIFIED = Path("runtime/data_brokerage/qualified_domain_intelligence_latest.json")
ORIGINAL_MD = Path("runtime/data_brokerage/agency_market_intelligence_sample_latest.md")
SITE = Path("runtime/buyer_network_intelligence/direct_site_verification_latest.json")
CATALOG = Path("runtime/data_brokerage/internal_product_catalog_latest.json")
SHA = re.compile(r"[a-f0-9]{64}\Z")
DOMAIN = re.compile(r"[a-z0-9][a-z0-9.-]{2,230}[a-z0-9]\Z")


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or len(value) > 70:
        return None
    try:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return out.astimezone(timezone.utc) if out.utcoffset() is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def _source_blob(root: Path, relative: Path, *, maximum: int) -> tuple[bytes, str] | None:
    loc = root / relative
    try:
        if (loc.is_symlink() or not loc.is_file() or loc.stat().st_size > maximum
                or loc.stat().st_size < 2):
            return None
        before = loc.stat()
        if before.st_mode & stat.S_IWOTH:
            return None
        blob = loc.read_bytes()
        after = loc.stat()
        if (len(blob) != before.st_size
                or (before.st_ino, before.st_mtime_ns, before.st_size) !=
                (after.st_ino, after.st_mtime_ns, after.st_size)):
            return None
        return blob, sha256(blob).hexdigest()
    except OSError:
        return None


def _json_source(root: Path, path: Path, *, maximum: int) -> tuple[dict, str] | None:
    found = _source_blob(root, path, maximum=maximum)
    if not found:
        return None
    try:
        obj = json.loads(found[0])
        return (obj, found[1]) if type(obj) is dict else None
    except (ValueError, UnicodeError, TypeError):
        return None


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "status": reason,
        "matched_canonical_product_id": None,
        "verified_paid_buyers": None,
        "customer_approval": False, "offer_price_accepted": False,
        "delivery_approved": False, "outbound_authorized": False,
        "external_delivery": False, "crm_writes": False,
        "execution_authority": "none",
    }


def qualify_existing_agency_report(root: Path, *, now: datetime) -> dict[str, Any]:
    """Validate the original dated agency study against ORIGINAL offer gates."""
    if now.utcoffset() is None:
        raise ValueError("TIMEZONE_AWARE_BROKERAGE_ASSESSMENT_REQUIRED")
    clock = now.astimezone(timezone.utc)
    sources = (
        _json_source(root, SAMPLE, maximum=110_000),
        _json_source(root, QUALIFIED, maximum=1_500_000),
        _source_blob(root, ORIGINAL_MD, maximum=30_000),
        _source_blob(root, SITE, maximum=3_000_000),
        _json_source(root, CATALOG, maximum=80_000),
    )
    if not all(sources):
        return _hold("ORIGINAL_AGENCY_SOURCE_OR_CATALOG_MISSING")
    (sample, sample_sha), (qualified, qualified_sha), (md, md_sha), (site_blob, site_sha), (catalog, catalog_sha) = sources
    expected = sample.get("source")
    if not isinstance(expected, Mapping):
        return _hold("ORIGINAL_AGENCY_SOURCE_MANIFEST_ABSENT")
    pinned_site_sha = expected.get("direct_site_verifier_sha256")
    if (expected.get("brokerage_report_sha256") != qualified_sha
            or not isinstance(pinned_site_sha, str)
            or not SHA.fullmatch(pinned_site_sha)
            or not isinstance(expected.get("brokerage_research_fingerprint"), str)
            or not SHA.fullmatch(expected["brokerage_research_fingerprint"])
            or qualified.get("source_fingerprint") != expected["brokerage_research_fingerprint"]):
        return _hold("ORIGINAL_AGENCY_CROSS_SOURCE_INTEGRITY_HOLD")
    try:
        site_observer = json.loads(site_blob)
    except (ValueError, UnicodeError, TypeError):
        return _hold("DIRECT_SITE_ORIGINAL_EVIDENCE_INVALID")
    if (not isinstance(site_observer, dict)
            or site_observer.get("schema_version") != "buyer-direct-site-verification-v1"
            or site_observer.get("authority") != "OBSERVE"
            or not isinstance(site_observer.get("results"), list)
            or len(site_observer["results"]) > 6000
            or not isinstance(site_observer.get("governance"), Mapping)
            or any(site_observer["governance"].get(k) is not False for k in (
                "commercial_terms", "db_write", "forms",
                "funds", "logins", "outbound", "traffic_activation",
            ))):
        return _hold("ORIGINAL_DIRECT_SITE_OWNER_EVIDENCE_UNTRUSTED")
    site_by_domain = {
        row["domain"]: row
        for row in site_observer["results"]
        if isinstance(row, Mapping) and isinstance(row.get("domain"), str)
    }
    if len(site_by_domain) != len([
        row for row in site_observer["results"]
        if isinstance(row, Mapping) and isinstance(row.get("domain"), str)
    ]):
        return _hold("DUPLICATED_DIRECT_SITE_SOURCE_IDENTITY")
    created = _utc(sample.get("as_of_utc"))
    checked = _utc(expected.get("site_observed_at_utc"))
    current_verifier_time = _utc(site_observer.get("generated_at"))
    if (created is None or checked is None or current_verifier_time is None
            or not timedelta(0) <= clock-created <= timedelta(days=7)
            or not timedelta(0) <= clock-checked <= timedelta(days=7)
            or not timedelta(0) <= clock-current_verifier_time <= timedelta(days=7)
            or current_verifier_time < checked):
        return _hold("ORIGINAL_AGENCY_PROVENANCE_STALE_OR_FUTURE")
    summary = qualified.get("summary")
    cases = sample.get("case_studies")
    records = qualified.get("records")
    flags = (
        sample.get("schema_version") == SCHEMA.replace("agency_buyer_fit","agency_market_intelligence_sample")
        and qualified.get("schema_version") == "empire.data_brokerage.domain_qualification.v1"
        and sample.get("report_type") == "FOUNDER_REVIEW_BUYER_FACING_SAMPLE_UNSENT"
        and sample.get("customer_preview_sent") is False
        and sample.get("buyer_or_contract_verified") is False
        and sample.get("customer_redistribution_permission_verified") is False
        and sample.get("pricing_or_revenue_verified") is False
        and sample.get("founder_approved_to_send") is False
        and sample.get("crm_writes") is False
        and sample.get("external_outbound") is False
        and sample.get("source_market_country") == "UNKNOWN"
        and sample.get("existing_product_catalog_key") == "founder_original_intelligence_reports"
        and isinstance(summary, Mapping)
        and qualified.get("contracts_or_revenue_verified") is False
        and qualified.get("source_rights_represented_as_verified") is False
        and isinstance(records, list) and len(records) == sample.get("cohort_size")
        and len(records) <= 1000 and len(records) > 0
        and isinstance(cases, list) and len(cases) == 5
        and sample.get("first_party_signal_corrob") == summary.get("site_corroborated")
        and summary.get("verified_buyer_contracts") == 0
        and summary.get("source_redist_rights_proven") == 0
        and summary.get("canonical_tenant_crm_dedup_verified") is False
    )
    if not flags:
        return _hold("ORIGINAL_AGENCY_BUYER_OR_RIGHTS_CLAIMS_UNTRUSTED")
    records_by_domain = {}
    for rec in records:
        if type(rec) is not dict or not isinstance(rec.get("domain"), str):
            return _hold("UNTRUSTED_ORIGINAL_AGENCY_RECORDS")
        domain = rec["domain"]
        if domain in records_by_domain or not DOMAIN.fullmatch(domain):
            return _hold("DUPLICATE_OR_INVALID_AGENCY_ENTITY")
        records_by_domain[domain] = rec
    sample_domains = []
    for case in cases:
        if not isinstance(case, Mapping):
            return _hold("AGENCY_CASE_SOURCE_SCHEMA_INVALID")
        domain, url = case.get("domain"), case.get("observed_first_party_url")
        if not isinstance(domain, str) or not isinstance(url, str):
            return _hold("AGENCY_CASE_SOURCE_SCHEMA_INVALID")
        row = records_by_domain.get(domain)
        # The actual direct-site verifier is source-authoritative; the
        # summary cannot assert buyer purchasing or geographic coverage.
        if (row is None or row.get("site_corrob") is not True
                or row.get("verification_stage") != "DIRECT_SITE_CORROBORATED"
                or row.get("source_rights_state") != "INTERNAL_RESEARCH_HOLD"
                or row.get("site_observed_at") != case.get("first_party_observed_utc")
                or not url.startswith("https://" + domain + "/")
                or case.get("buyer_contract_verified") is not False
                or case.get("country_or_market_verified") is not False):
            return _hold("AGENCY_CASE_NOT_MATCHED_TO_ORIGINAL_SOURCE")
        site_item = site_by_domain.get(domain)
        if (not isinstance(site_item, Mapping)
                or site_item.get("corroborated") is not True
                or site_item.get("observed_at") != case.get("first_party_observed_utc")
                or type(site_item.get("pages_successful")) is not int
                or site_item["pages_successful"] < 1
                or not isinstance(site_item.get("evidence"), Mapping)
                or not isinstance(site_item.get("pages"), list)
                or not any(
                    isinstance(page, Mapping)
                    and page.get("url") == url
                    and page.get("http_status") == 200
                    and page.get("status") == "PASS"
                    for page in site_item["pages"]
                )
                or case.get("website_signal_categories") != {
                    key: site_item["evidence"].get(key) is True
                    for key in ("active_demand", "compliance", "economics",
                                "integration", "publisher_program")
                }):
            return _hold("ORIGINAL_CASE_NOT_IN_VERIFIED_FIRST_PARTY_PAGES")
        obs = _utc(case.get("first_party_observed_utc"))
        if obs is None or obs > clock or clock-obs > timedelta(days=7):
            return _hold("AGENCY_CASE_SOURCE_TOO_OLD")
        sample_domains.append(domain)
    if len(set(sample_domains)) != 5:
        return _hold("AGENCY_CASE_DUPLICATE")
    # Original source product catalogue and commercial research hypotheses.
    if not validate_internal_brokerage_catalog(catalog):
        return _hold("CANONICAL_BROKERAGE_PRODUCT_CATALOG_INVALID")
    try:
        portfolio = build_monetization_portfolio(catalog, assessed_at=clock)
    except (ValueError, KeyError, TypeError):
        return _hold("ORIGINAL_BROKERAGE_MONETISATION_CONTRACT_MISSING")
    if not validate_portfolio(portfolio):
        return _hold("ORIGINAL_BROKERAGE_MONETISATION_NOT_VALIDATED")
    offer = next((x for x in portfolio["options"]
                  if x.get("offer_code") == "agency_white_label_search"), None)
    if (offer is None
            or offer.get("existing_product_id") != "founder_original_intelligence_reports"
            or offer.get("published") is not False
            or offer.get("buyer_verified") is not False
            or offer.get("signed_agreement_verified") is not False
            or offer.get("source_specific_delivery_rights_verified") is not False
            or offer.get("price_hypothesis",{}).get("buyer_accepted") is not False):
        return _hold("ORIGINAL_AGENCY_OFFER_NOT_IN_UNAPPROVED_STATE")
    if b"Empire" not in md or b"founder" not in md.lower():
        return _hold("ORIGINAL_DERIVED_REPORT_NOT_PRESENT")
    published = summary.get("existing_communication_observed")
    known = summary.get("overlap_with_existing_commercial_research_registry")
    if type(published) is not int or type(known) is not int:
        return _hold("ORIGINAL_COMMERCIAL_RELATIONSHIP_COUNTS_INVALID")
    result = {
        "schema_version": SCHEMA, "status": "ORIGINAL_RESEARCH_CONFIRMED_NO_PAID_BUYER",
        "evidence_observed_at": created.isoformat(),
        "evaluated_at": clock.isoformat(),
        "source_report_sha256": sample_sha,
        "qualified_domain_source_sha256": qualified_sha,
        "original_private_report_sha256": md_sha,
        "direct_site_verifier_sha256": site_sha,
        "original_sample_pinned_site_verifier_sha256": pinned_site_sha,
        "site_verifier_snapshot_changed_since_sample": site_sha != pinned_site_sha,
        "current_five_case_studies_independently_rechecked": True,
        "canonical_catalog_source_sha256": catalog_sha,
        "source_manifest_fingerprint": expected["brokerage_research_fingerprint"],
        "original_private_report": str(ORIGINAL_MD),
        "sample_scope": {
            "registered_domains_researched": len(records),
            "direct_site_corroborated_domains": sample["first_party_signal_corrob"],
            "original_case_studies": len(cases),
            "source_market_country": sample["source_market_country"],
            "existing_communication_observations": published,
            "commercial_research_overlap": known,
            "canonical_crm_suppression_verified": False,
            "all_site_signals_are_contracts": False,
            "market_geo_validated": False,
        },
        "matched_canonical_product_id": "founder_original_intelligence_reports",
        "existing_unpriced_discovery_code": "brokerage_agency_discovery",
        "corresponding_existing_offer": "agency_white_label_search",
        "source_buyer_problem": "Publisher-network, programme, economics and source-compliance landscape",
        "existing_offer_problem": "Agency white-label client-local competitor and market research",
        "fit_assessment": "OFFER_SCOPE_MISMATCH_NEEDS_EXPLICIT_PAID_BUYER_BRIEF",
        "current_buyer_job_validated": False,
        "requirements_for_paid_buyer_fit": [
            "named_authorised buyer asking for this analysis",
            "specific industry and geography or explicitly cross-market scope",
            "decision, report content, recipients, source-date SLA and corrections",
            "accepted price and confidentiality/permitted downstream usage",
            "proven permission to deliver original derived analysis",
        ],
        "delivery_evidence": {
            "actual_private_original_preview_exists": True,
            "source_hashes_match_first_party_research": True,
            "current_first_party_pages_rechecked_under_source_rollover": True,
            "sample_contains_contact_records": False,
            "raw_external_source_rows_included": False,
            "rights_for_external_customer_delivery_verified": False,
            "third_party_licence_and_attribution_review_completed": False,
            "customer_recipient_identity_and_rights_verified": False,
            "customer_delivery_workflow_tested": False,
        },
        "price_hypothesis_not_validated": offer.get("price_hypothesis"),
        "verified_paid_buyers": None,
        "customer_approval": False, "offer_price_accepted": False,
        "delivery_approved": False, "outbound_authorized": False,
        "external_delivery": False, "crm_writes": False,
        "execution_authority": "none",
    }
    return result


def validate_agency_fit_receipt(report: Any) -> bool:
    if not isinstance(report, Mapping) or report.get("schema_version") != SCHEMA:
        return False
    if (report.get("customer_approval") is not False
            or report.get("offer_price_accepted") is not False
            or report.get("delivery_approved") is not False
            or report.get("outbound_authorized") is not False
            or report.get("external_delivery") is not False
            or report.get("crm_writes") is not False
            or report.get("execution_authority") != "none"
            or report.get("verified_paid_buyers") is not None):
        return False
    if report.get("status") != "ORIGINAL_RESEARCH_CONFIRMED_NO_PAID_BUYER":
        allowed_source_holds = {
            "ORIGINAL_AGENCY_SOURCE_OR_CATALOG_MISSING",
            "ORIGINAL_AGENCY_SOURCE_MANIFEST_ABSENT",
            "ORIGINAL_AGENCY_CROSS_SOURCE_INTEGRITY_HOLD",
            "DIRECT_SITE_ORIGINAL_EVIDENCE_INVALID",
            "ORIGINAL_DIRECT_SITE_OWNER_EVIDENCE_UNTRUSTED",
            "DUPLICATED_DIRECT_SITE_SOURCE_IDENTITY",
            "ORIGINAL_AGENCY_PROVENANCE_STALE_OR_FUTURE",
            "ORIGINAL_AGENCY_BUYER_OR_RIGHTS_CLAIMS_UNTRUSTED",
            "UNTRUSTED_ORIGINAL_AGENCY_RECORDS",
            "DUPLICATE_OR_INVALID_AGENCY_ENTITY",
            "AGENCY_CASE_SOURCE_SCHEMA_INVALID",
            "AGENCY_CASE_NOT_MATCHED_TO_ORIGINAL_SOURCE",
            "ORIGINAL_CASE_NOT_IN_VERIFIED_FIRST_PARTY_PAGES",
            "AGENCY_CASE_SOURCE_TOO_OLD",
            "AGENCY_CASE_DUPLICATE",
            "CANONICAL_BROKERAGE_PRODUCT_CATALOG_INVALID",
            "ORIGINAL_BROKERAGE_MONETISATION_CONTRACT_MISSING",
            "ORIGINAL_BROKERAGE_MONETISATION_NOT_VALIDATED",
            "ORIGINAL_AGENCY_OFFER_NOT_IN_UNAPPROVED_STATE",
            "ORIGINAL_DERIVED_REPORT_NOT_PRESENT",
            "ORIGINAL_COMMERCIAL_RELATIONSHIP_COUNTS_INVALID",
        }
        return report.get("status") in allowed_source_holds and report.get("matched_canonical_product_id") is None
    scope, evidence = report.get("sample_scope"), report.get("delivery_evidence")
    price = report.get("price_hypothesis_not_validated")
    return bool(
        report.get("matched_canonical_product_id") == "founder_original_intelligence_reports"
        and report.get("corresponding_existing_offer") == "agency_white_label_search"
        and report.get("fit_assessment") == "OFFER_SCOPE_MISMATCH_NEEDS_EXPLICIT_PAID_BUYER_BRIEF"
        and report.get("current_buyer_job_validated") is False
        and isinstance(scope, Mapping)
        and type(scope.get("registered_domains_researched")) is int
        and 0 < scope["registered_domains_researched"] <= 1000
        and type(scope.get("direct_site_corroborated_domains")) is int
        and 0 < scope["direct_site_corroborated_domains"] <= scope["registered_domains_researched"]
        and scope.get("original_case_studies") == 5
        and type(scope.get("existing_communication_observations")) is int
        and 0 <= scope["existing_communication_observations"] <= scope["registered_domains_researched"]
        and type(scope.get("commercial_research_overlap")) is int
        and 0 <= scope["commercial_research_overlap"] <= scope["registered_domains_researched"]
        and scope.get("source_market_country") == "UNKNOWN"
        and scope.get("all_site_signals_are_contracts") is False
        and scope.get("canonical_crm_suppression_verified") is False
        and scope.get("market_geo_validated") is False
        and isinstance(evidence, Mapping)
        and evidence.get("actual_private_original_preview_exists") is True
        and evidence.get("current_first_party_pages_rechecked_under_source_rollover") is True
        and report.get("current_five_case_studies_independently_rechecked") is True
        and isinstance(report.get("site_verifier_snapshot_changed_since_sample"), bool)
        and evidence.get("rights_for_external_customer_delivery_verified") is False
        and evidence.get("customer_delivery_workflow_tested") is False
        and isinstance(price, Mapping)
        and price.get("buyer_accepted") is False
        and price.get("market_price_verified") is False
        and all(isinstance(report.get(key), str) and SHA.fullmatch(report[key])
                for key in (
                    "source_report_sha256", "qualified_domain_source_sha256",
                    "original_private_report_sha256", "direct_site_verifier_sha256",
                    "original_sample_pinned_site_verifier_sha256",
                    "canonical_catalog_source_sha256", "source_manifest_fingerprint",
                ))
    )


# Two verified public purchasing-need anchors. These are public procurement
# notices, NOT customer enquiries or approved bids. The existing UK official
# procurement adapter owns all HTTP retrieval (no new scraper/provider).
PUBLIC_REQUIREMENT_SCHEMA = "empire.data_brokerage.public_research_requirement.v1"
OFFICIAL_FTS_PACKAGE = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages/"
PUBLIC_RESEARCH_ANCHORS = (
    ("099702-2026", "ocds-h6vhtk-078d56", "FRC_EXISTING_PLATFORM"),
    ("106838-2026", "ocds-h6vhtk-07b8ee", "ACE_PRIMARY_SURVEY"),
)


def _official_notice_package(url: str) -> Mapping[str, Any]:
    from empire_os.acquisition_official_tender_intake import _fetch_package
    if url not in {OFFICIAL_FTS_PACKAGE + name for name, *_ in PUBLIC_RESEARCH_ANCHORS}:
        raise ValueError("UNAPPROVED_OFFICIAL_NOTICE_ID")
    return _fetch_package(url)


def assess_existing_public_buyer_requirement(
    package: Mapping[str, Any], *, notice: str, ocid: str,
    capability: str, now: datetime,
) -> dict[str, Any]:
    """Verify genuine external public demand without inventing our eligibility."""
    if (now.utcoffset() is None or not isinstance(package, Mapping)
            or notice not in {name for name, *_ in PUBLIC_RESEARCH_ANCHORS}):
        raise ValueError("UNTRUSTED_PUBLIC_REQUIREMENT_INPUT")
    expected = next(((oid, kind) for name, oid, kind in PUBLIC_RESEARCH_ANCHORS
                     if name == notice), None)
    if expected != (ocid, capability):
        raise ValueError("UNRECOGNISED_PUBLIC_PROCUREMENT_HYPOTHESIS")
    releases = package.get("releases")
    if not isinstance(releases, list) or not 1 <= len(releases) <= 8:
        raise ValueError("UNTRUSTED_OFFICIAL_NOTICE_RELEASES")
    by_date = []
    for row in releases:
        if (not isinstance(row, Mapping) or row.get("ocid") != ocid
                or not isinstance(row.get("tender"), Mapping)):
            raise ValueError("PUBLIC_NOTICE_OCID_OR_SCHEMA_CONFLICT")
        stamp = _utc(row.get("date"))
        if stamp is None or stamp > now.astimezone(timezone.utc):
            raise ValueError("OFFICIAL_RELEASE_DATE_IN_FUTURE")
        by_date.append((stamp, row))
    _, current = max(by_date, key=lambda pair: pair[0])
    t = current["tender"]
    buyer = current.get("buyer")
    description, title = t.get("description"), t.get("title")
    deadline = _utc((t.get("tenderPeriod") or {}).get("endDate"))
    if (not isinstance(buyer, Mapping)
            or not isinstance(buyer.get("name"), str)
            or not 3 <= len(buyer["name"]) <= 170
            or not isinstance(description, str) or not 30 <= len(description) <= 15000
            or not isinstance(title, str) or not 5 <= len(title) <= 180
            or deadline is None):
        raise ValueError("OFFICIAL_REQUIREMENT_TEXT_OR_DEADLINE_UNVERIFIED")
    lower = description.casefold()
    if capability == "FRC_EXISTING_PLATFORM":
        needs = (
            "existing, established web-based market intelligence and document search platform"
            in lower
            and "rather than a purpose-built solution" in lower
            and "aggregated, indexed national and global content" in lower
        )
        evidence_job = "EXISTING_GLOBAL_MARKET_INTELLIGENCE_DOCUMENT_SEARCH_SUBSCRIPTION"
        mismatch = "ORIGINAL_REPORT_IS_NOT_ESTABLISHED_GLOBAL_SEARCH_PLATFORM"
        required = [
            "already operating searchable global platform",
            "established national and international indexed content access",
            "verified licence, end-user access and service support",
        ]
    else:
        needs = ("sector-wide survey" in lower
                 and "quantitative data collection" in lower
                 and "young people aged 14 and above" in lower)
        evidence_job = "MIXED_METHOD_PRIMARY_RESEARCH_AND_SECTOR_SURVEY"
        mismatch = "ORIGINAL_REPORT_DOES_NOT_PROVE_SURVEY_DELIVERY_CAPABILITY"
        required = [
            "approved sector-wide primary research and survey delivery",
            "demonstrated respondent recruitment, ethics and data protection",
            "age-appropriate outputs and tender-specific quality credentials",
        ]
    if not needs:
        raise ValueError("BUYER_PUBLIC_REQUIREMENT_NOT_IN_OFFICIAL_RECORD")
    amount = (t.get("value") or {}).get("amount")
    currency = (t.get("value") or {}).get("currency")
    if type(amount) not in (int, float) or not 0 <= amount <= 1e9 or currency != "GBP":
        amount = None
    return {
        "original_public_official_notice_id": notice,
        "official_ocid": ocid,
        "original_buyer": buyer["name"],
        "original_notice_title": title,
        "official_url": "https://www.find-tender.service.gov.uk/Notice/" + notice,
        "official_api_uri": OFFICIAL_FTS_PACKAGE + notice,
        "official_raw_package_sha256": sha256(json.dumps(
            package, sort_keys=True, default=str, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
        "published_notice_date": min(row[0] for row in by_date).isoformat(),
        "submission_deadline": deadline.isoformat(),
        "status_as_of_assessment": ("OFFICIAL_TENDER_CURRENTLY_OPEN"
                                   if t.get("status") == "active"
                                   and now.astimezone(timezone.utc) < deadline
                                   else "NOTICE_NOT_OPEN_AT_ASSESSMENT"),
        "public_published_estimate_gbp": amount,
        "estimate_is_not_our_revenue": True,
        "real_public_procurement_requirement_proven": True,
        "requirement_category": evidence_job,
        "matching_original_product": "founder_original_intelligence_reports",
        "existing_product_capability_fit": "NOT_VERIFIED",
        "specific_mismatch": mismatch,
        "missing_product_capabilities": required,
        "buyer_accepted_our_product": False,
        "bid_eligibility_approved": False,
        "documents_fully_reviewed": False,
        "customer_enquiry_received": False,
        "outbound_or_bid_authorized": False,
        "automatic_registration_authorized": False,
        "revenue_verified": False,
        "raw_procurement_document_redistribution_authorized": False,
    }


def verify_public_research_demand(
    *, now: datetime, fetch=None,
) -> dict[str, Any]:
    """Monitor two already-discovered real procurement requirements."""
    if now.utcoffset() is None:
        raise ValueError("PROCUREMENT_BUYER_REQUIREMENT_CLOCK_NEEDED")
    get = fetch or _official_notice_package
    reviewed = []
    errors = []
    for notice, ocid, capability in PUBLIC_RESEARCH_ANCHORS:
        try:
            package = get(OFFICIAL_FTS_PACKAGE + notice)
            reviewed.append(assess_existing_public_buyer_requirement(
                package, notice=notice, ocid=ocid,
                capability=capability, now=now,
            ))
        except (OSError, ValueError, KeyError, TypeError, TimeoutError):
            errors.append({"notice": notice, "status": "ORIGINAL_NOTICE_FETCH_OR_SCHEMA_HOLD"})
    return {
        "schema_version": PUBLIC_REQUIREMENT_SCHEMA,
        "status": "PUBLIC_REQUIREMENTS_COMPARED_TO_ORIGINAL_PRODUCT",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "official_notices_assessed": len(reviewed),
        "official_notice_errors": errors,
        "source_specific_findings": reviewed,
        "unverified_agency_customers_inferred": False,
        "buyer_intent_directed_at_empire_ai": False,
        "suitable_bid_or_customer_order_verified": False,
        "automatic_outbound_or_bid_authorized": False,
        "crm_customer_rows_created": False,
        "revenue_verified": False,
        "execution_authority": "none",
    }


def validate_public_research_demand(report: Any) -> bool:
    if not isinstance(report, Mapping):
        return False
    if (report.get("schema_version") != PUBLIC_REQUIREMENT_SCHEMA
            or report.get("status") != "PUBLIC_REQUIREMENTS_COMPARED_TO_ORIGINAL_PRODUCT"
            or report.get("unverified_agency_customers_inferred") is not False
            or report.get("buyer_intent_directed_at_empire_ai") is not False
            or report.get("suitable_bid_or_customer_order_verified") is not False
            or report.get("automatic_outbound_or_bid_authorized") is not False
            or report.get("crm_customer_rows_created") is not False
            or report.get("revenue_verified") is not False
            or report.get("execution_authority") != "none"):
        return False
    findings = report.get("source_specific_findings")
    if not isinstance(findings, list) or len(findings) > len(PUBLIC_RESEARCH_ANCHORS):
        return False
    if report.get("official_notices_assessed") != len(findings):
        return False
    if _utc(report.get("observed_at")) is None:
        return False
    seen = set()
    for row in findings:
        if not isinstance(row, Mapping):
            return False
        notice = row.get("original_public_official_notice_id")
        expected = next((o for n, o, _ in PUBLIC_RESEARCH_ANCHORS if n == notice), None)
        expected_kind = next((kind for n, _, kind in PUBLIC_RESEARCH_ANCHORS
                              if n == notice), None)
        expected_mismatch = (
            "ORIGINAL_REPORT_IS_NOT_ESTABLISHED_GLOBAL_SEARCH_PLATFORM"
            if expected_kind == "FRC_EXISTING_PLATFORM"
            else "ORIGINAL_REPORT_DOES_NOT_PROVE_SURVEY_DELIVERY_CAPABILITY"
        )
        if (not expected or notice in seen or row.get("official_ocid") != expected
                or row.get("official_api_uri") != OFFICIAL_FTS_PACKAGE + notice
                or row.get("official_url") != "https://www.find-tender.service.gov.uk/Notice/" + notice
                or row.get("existing_product_capability_fit") != "NOT_VERIFIED"
                or row.get("matching_original_product") != "founder_original_intelligence_reports"
                or row.get("specific_mismatch") != expected_mismatch
                or not isinstance(row.get("missing_product_capabilities"), list)
                or len(row["missing_product_capabilities"]) < 3
                or _utc(row.get("published_notice_date")) is None
                or _utc(row.get("submission_deadline")) is None
                or row.get("real_public_procurement_requirement_proven") is not True
                or row.get("buyer_accepted_our_product") is not False
                or row.get("bid_eligibility_approved") is not False
                or row.get("customer_enquiry_received") is not False
                or row.get("outbound_or_bid_authorized") is not False
                or row.get("revenue_verified") is not False
                or row.get("automatic_registration_authorized") is not False
                or row.get("raw_procurement_document_redistribution_authorized") is not False
                or row.get("status_as_of_assessment") not in (
                    "OFFICIAL_TENDER_CURRENTLY_OPEN", "NOTICE_NOT_OPEN_AT_ASSESSMENT")
                or not isinstance(row.get("official_raw_package_sha256"), str)
                or not SHA.fullmatch(row["official_raw_package_sha256"])):
            return False
        seen.add(notice)
    failures = report.get("official_notice_errors")
    return (isinstance(failures, list)
            and len(failures) + len(findings) == len(PUBLIC_RESEARCH_ANCHORS)
            and len({f.get("notice") for f in failures if isinstance(f, Mapping)}) == len(failures)
            and all(isinstance(f, Mapping)
                    and f.get("status") == "ORIGINAL_NOTICE_FETCH_OR_SCHEMA_HOLD"
                    and f.get("notice") in {n for n, *_ in PUBLIC_RESEARCH_ANCHORS}
                    and f.get("notice") not in seen
                    for f in failures))
