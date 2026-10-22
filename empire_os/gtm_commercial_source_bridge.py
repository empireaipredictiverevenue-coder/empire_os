"""Bounded JEV, organic visibility, and first-party enquiry receipts for EXISTING GTM.

No network, no SQL, no CRM access, no PII, no additional timer/agent, no sends.
Never equate Google impressions, public buyer-pain mentions and enquiries.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

JEV_RELATIVE = Path("runtime/jev_client_pain_discovery/aggregate_latest.json")
GSC_OWNER_DIR = Path("/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022")
# Owner-delivered count-only receipt from the existing canonical source reader.
# Intentionally absent unless independently supplied by an authorised owner.
ENQUIRY_RELATIVE = Path("runtime/gtm_pipeline/owner_sales_enquiry_counts_latest.json")
BROKERAGE_RELATIVE = Path("runtime/data_brokerage/internal_product_catalog_latest.json")
JEV_SCHEMA = "empire.jev.client_pain_production_observe.v1"
GSC_SCHEMA = "empire.search.weekly_two_page_outcome_observer.v1"
SALES_SCHEMA = "empire.founder.canonical_sales_source_aggregate.v1"
TARGETS = (
    "https://empire-ai.co.uk/predictive-revenue",
    "https://empire-ai.co.uk/industries/roofing",
)
COUNT_KEYS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)
MAX_BYTES = 100_000


def _read(path: Path, *, now: datetime, max_age: timedelta) -> dict[str, Any] | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        file_stat = path.stat()
        if not 0 < file_stat.st_size <= MAX_BYTES:
            return None
        delta = now.timestamp() - file_stat.st_mtime
        if not 0 <= delta <= max_age.total_seconds():
            return None
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return packet if isinstance(packet, dict) else None


def _ts(value: Any, now: datetime, age: timedelta) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if parsed.tzinfo is None:
        return False
    delta = now - parsed.astimezone(timezone.utc)
    return timedelta(0) <= delta <= age


def review_jev(aggregate: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "HELD_UNVERIFIED_JEV_RECEIPT",
        "review_only": True, "verified_buyers": 0, "promoted_prospects": 0,
        "pain_theme_review_count": 0, "pain_theme_reviews": [],
    }
    if not isinstance(aggregate, Mapping) or any((
        aggregate.get("schema_version") != JEV_SCHEMA,
        aggregate.get("mode") != "OBSERVE",
        aggregate.get("status") != "CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
        aggregate.get("execution_authority") != "none",
        aggregate.get("verified_individual_clients") != 0,
        aggregate.get("verified_contracts") != 0,
        aggregate.get("prospects_verified") != 0,
        aggregate.get("source_rights_and_consent_verified") is not False,
        aggregate.get("crm_writes") is not False,
        aggregate.get("database_writes") is not False,
        aggregate.get("outbound_sent") != 0,
        not _ts(aggregate.get("generated_at_utc"), now, timedelta(hours=24)),
    )):
        return result
    pain = aggregate.get("pain_counts")
    if not isinstance(pain, dict) or len(pain) > 100:
        return result
    reviews = []
    for key, raw in sorted(pain.items()):
        if (not isinstance(key, str) or not key.isidentifier()
                or len(key) > 80 or not isinstance(raw, dict)
                or type(raw.get("observations")) is not int
                or not 0 < raw["observations"] <= 500
                or not isinstance(raw.get("matched_offer_to_validate"), str)
                or not 0 < len(raw["matched_offer_to_validate"]) <= 120):
            return result
        reviews.append({
            "handoff_id": sha256(f"jev|{key}".encode()).hexdigest()[:24],
            "pain_key": key,
            "observation_count": raw["observations"],
            "offer_to_validate": raw["matched_offer_to_validate"],
            "status": "PUBLIC_PAIN_HYPOTHESIS_ONLY",
            "next_action": "source_intelligence_research",
            "buyer_identity_verified": False,
            "contact_authorized": False,
        })
    result.update(
        status=("JEV_PUBLIC_PAIN_THEMES_REVIEW_ONLY" if reviews
                else "NO_CONCRETE_JEV_PAIN_THEMES_IN_CURRENT_RECEIPT"),
        pain_theme_review_count=len(reviews),
        pain_theme_reviews=reviews,
    )
    return result


def review_organic(report: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "HELD_UNVERIFIED_GSC_RECEIPT",
        "review_only": True, "gsc_page_metrics": [],
        "search_to_enquiry_join_verified": False,
        "organic_sales_attributed": None,
    }
    if not isinstance(report, Mapping) or any((
        report.get("schema_version") != GSC_SCHEMA,
        report.get("status") != "READ_ONLY_WEEKLY_REPORT",
        report.get("source_property") != "sc-domain:empire-ai.co.uk",
        report.get("dimensions") != ["page"],
        report.get("execution_authority") != "NONE",
        report.get("website_mutations") is not False,
        report.get("qualified_buyer_enquiries_verified") is not False,
        report.get("realised_revenue_verified") is not False,
        report.get("automatic_jev_model_calls") != 0,
    )):
        return result
    try:
        as_of = date.fromisoformat(report["as_of"])
    except (TypeError, ValueError, KeyError):
        return result
    if not 0 <= (now.date() - as_of).days <= 7:
        return result
    window = report.get("current_window")
    if not isinstance(window, Mapping) or not isinstance(window.get("pages"), list):
        return result
    pages = window["pages"]
    source_state = window.get("source_status")
    if (source_state not in {"FINAL_PAGE_ROWS", "SOURCE_UNAVAILABLE", "NOT_YET_FINAL"}
            or len(pages) != 2
            or tuple(p.get("url") for p in pages if isinstance(p, dict)) != TARGETS
            or not isinstance(report.get("source_errors"), list)):
        return result
    rows = []
    for p in pages:
        state = p.get("status")
        if (source_state == "FINAL_PAGE_ROWS"
                and state not in {"MEASURED_ZERO", "MEASURED_PAGE_METRICS", "NO_PAGE_IN_RETURNED_GSC_ROWS"}):
            return result
        if source_state == "SOURCE_UNAVAILABLE" and state != "SOURCE_UNAVAILABLE":
            return result
        if source_state == "NOT_YET_FINAL" and state != "NOT_YET_REPORTED":
            return result
        if state in {"MEASURED_ZERO", "MEASURED_PAGE_METRICS"}:
            clicks, imp = p.get("clicks"), p.get("impressions")
            if (type(clicks) is not int or type(imp) is not int
                    or not 0 <= clicks <= imp <= 1_000_000_000
                    or not isinstance(p.get("evidence_refs"), list)
                    or not p["evidence_refs"]):
                return result
        elif state in {"NOT_YET_REPORTED", "NO_PAGE_IN_RETURNED_GSC_ROWS",
                       "SOURCE_UNAVAILABLE"}:
            clicks = imp = None
        else:
            return result
        rows.append({
            "page": p["url"], "status": state, "gsc_clicks": clicks,
            "gsc_impressions": imp, "search_enquiries_verified": None,
        })
    result.update(
        status=("GSC_PAGE_EVIDENCE_OBSERVED_NOT_CONVERSION_PROOF"
                if any(r["gsc_clicks"] is not None for r in rows)
                else "GSC_PAGE_METRICS_NOT_YET_AVAILABLE"),
        gsc_page_metrics=rows,
    )
    return result


def review_sales_counts(receipt: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "HELD_NO_OWNER_VERIFIED_ENQUIRY_COUNTS",
        "verified_source": False, "enquiries_observed": None,
        "consent_verified_aggregate": False,
        "crm_delivery_verified": False,
        "individual_enquiry_promoted": False,
        "search_attribution_verified": False,
        "outbound_authorized": False,
    }
    if not isinstance(receipt, Mapping) or any((
        receipt.get("schema_version") != SALES_SCHEMA,
        receipt.get("mode") != "OBSERVE",
        receipt.get("read_only") is not True,
        receipt.get("source") != "CANONICAL_EMPIREDB",
        receipt.get("execution_authority") != "NONE",
        receipt.get("customer_rows_disclosed") is not False,
        receipt.get("contact_data_disclosed") is not False,
        receipt.get("database_writes") is not False,
        receipt.get("outbound_sent") is not False,
        receipt.get("payment_action") is not False,
        receipt.get("founder_crm_delivery_verified") is not False,
        not _ts(receipt.get("observed_at_utc"), now, timedelta(hours=24)),
    )):
        return result
    nums = {k:receipt.get(k) for k in COUNT_KEYS}
    if any(type(v) is not int or not 0 <= v <= 20_000_000 for v in nums.values()):
        return result
    total = nums["sales_acquisition_rows"]
    if (nums["commercial_acquisition_rows"] + nums["predictive_acquisition_rows"] != total
            or nums["distinct_sales_prospects"] > total
            or nums["source_evidence_consistent_rows"] > total
            or nums["founder_binding_exact_one_rows"]
             + nums["founder_binding_missing_or_ambiguous_rows"] != total
            or nums["entity_unlinked_acquisition_rows"] > total):
        return result
    status = ("NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES"
              if total == 0 else "ENQUIRY_COUNTS_OBSERVED_FOUNDER_REVIEW_REQUIRED")
    expected = ("NO_SALES_ACQUISITION_IN_CANONICAL_SOURCE" if total == 0
                else "SALES_ACQUISITION_SOURCE_OBSERVED_REVIEW_REQUIRED")
    if receipt.get("status") != expected:
        return result
    result.update(
        status=status, verified_source=True, enquiries_observed=total,
        consent_verified_aggregate=(
            nums["source_evidence_consistent_rows"] == total and total > 0),
    )
    return result


def review_brokerage_catalog(catalog: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    """Observe old internal brokerage inventory, NEVER contact or distribution rights."""
    result = {
        "status": "HELD_UNVERIFIED_BROKERAGE_INVENTORY",
        "internal_product_count": None,
        "source_rights_cleared_for_sale": False,
        "independently_verified_buyers": None,
        "enquiry_receipts_verified": False,
        "product_publication_authorized": False,
        "buyer_matching_authorized": False,
    }
    if not isinstance(catalog, Mapping) or any((
        catalog.get("schema_version") != "empire.data_brokerage.internal_product_catalog.v1",
        catalog.get("status") != "FOUR_ORIGINAL_DATA_PRODUCTS_IN_INTERNAL_BROKERAGE_REVIEW",
        catalog.get("mode") != "OBSERVE",
        catalog.get("execution_authority") != "none",
        catalog.get("canonical_database") != "EmpireDB",
        catalog.get("billing_activation_enabled") is not False,
        catalog.get("product_publication_authorized") is not False,
        catalog.get("third_party_resale_authorized") is not False,
        catalog.get("external_paid_sources_used") is not False,
        catalog.get("marketing_outbound_sent") is not False,
        catalog.get("independently_verified_buyer_count") != 0,
        catalog.get("verified_payment_count") != 0,
        catalog.get("customer_distributions_approved") != 0,
        not _ts(catalog.get("generated_at"), now, timedelta(days=7)),
    )):
        return result
    products = catalog.get("products")
    count = catalog.get("product_count")
    if (type(count) is not int or count != 4 or not isinstance(products, list)
            or len(products) != count):
        return result
    return {
        **result,
        "status": "BROKERAGE_INTERNAL_RESEARCH_PRODUCTS_RIGHTS_AND_BUYERS_HELD",
        "internal_product_count": count,
        "independently_verified_buyers": 0,
    }


def observe_product_sources(
    root: Path, *, now: datetime | None = None,
    gsc_directory: Path = GSC_OWNER_DIR,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    jev = _read(root / JEV_RELATIVE, now=current, max_age=timedelta(hours=24))
    gsc_report = None
    if gsc_directory.is_dir() and not gsc_directory.is_symlink():
        files = sorted(gsc_directory.glob("weekly_two_page_*.json"), reverse=True)
        if len(files) <= 60:
            for path in files:
                gsc_report = _read(path, now=current, max_age=timedelta(days=7))
                if gsc_report is not None:
                    break
    brokerage = _read(root / BROKERAGE_RELATIVE, now=current,
                      max_age=timedelta(days=7))
    sales_path = root / ENQUIRY_RELATIVE
    sales = _read(sales_path, now=current, max_age=timedelta(hours=24))
    # The count receipt must be delivered by the authorised root-level DB
    # owner, never written by this worker or supplied via public/user input.
    if sales is not None and (sales_path.is_symlink() or sales_path.stat().st_uid != 0):
        sales = None
    return {
        "jev": review_jev(jev, now=current),
        "organic_search": review_organic(gsc_report, now=current),
        "first_party_enquiries": review_sales_counts(sales, now=current),
        "brokerage": review_brokerage_catalog(brokerage, now=current),
        "source_category_separation_enforced": True,
        "automatic_acquisition_or_outbound_authorized": False,
        "execution_authority": "none",
    }
