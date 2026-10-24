"""Build-stage packaging for *public* SaaS demand inside original EmpireOS.

This is NOT a new prospect/CRM repository. It composes the original product
catalog and public first-party research samples. No live prospect ingest,
outreach, billing, HubSpot operation or external procurement submission.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit

from empire_os.predictive_revenue_products import predictive_revenue_product

SOURCE_REL = Path("docs/commercial/SAAS_DEMAND_BUILD_SOURCE_20261024.json")
OUTPUT_REL = Path("runtime/acquisition_research/saas_demand_build_stage_latest.json")
PRODUCT_CODE = "predictive_revenue_diagnostic"
ALLOWED_KINDS = frozenset({
    "MARKETPLACE_EXTERNAL_SERVICE_REQUEST", "COMPANY_OFFICIAL_HIRING",
})
ALLOWED_ROUTES = frozenset({
    "PLATFORM_APPLICATION_ONLY", "FOUNDER_PROFESSIONAL_INTRO_REVIEW",
    "COMMERCIAL_CONTACT_UNVERIFIED",
})
ALLOWED_HOSTS = frozenset({
    "www.upwork.com", "www.clueso.io", "jobs.ashbyhq.com", "credal.ai",
})
ALLOWED_SCOPES = frozenset({
    "HUBSPOT_IMPLEMENTATION_MANDATORY", "SALES_PROCESS_BUILD", "NONE",
})
MAX_ROWS = 20
MAX_INPUT_BYTES = 80_000
MAX_SAMPLE_BYTES = 120_000


class SourceHold(ValueError):
    pass


def _string(value, *, max_length=700) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise SourceHold("UNTRUSTED_SOURCE_FIELD")
    if any(ord(c) < 32 for c in value):
        raise SourceHold("CONTROL_CHARACTER_IN_SOURCE_FIELD")
    return value.strip()


def _read_source(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise SourceHold("EXISTING_SOURCE_UNAVAILABLE_OR_UNSAFE")
    payload = json.loads(path.read_text(encoding="utf8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "empire.saas_demand_build_source.v1"
    ):
        raise SourceHold("SOURCE_SCHEMA_UNTRUSTED")
    return payload


def build(root: Path, source: dict, *, now: date | None = None,
          suppression_fresh: bool = False) -> dict:
    root = Path(root)
    product = predictive_revenue_product(PRODUCT_CODE)
    if product.product_code != PRODUCT_CODE:
        raise SourceHold("ORIGINAL_CATALOGUE_PRODUCT_MISMATCH")
    observed_date = date.fromisoformat(_string(source.get("as_of"), max_length=10))
    today = now or datetime.now(timezone.utc).date()
    if observed_date > today or (today - observed_date).days > 7:
        raise SourceHold("SOURCE_COHORT_STALE_RE_REVIEW_REQUIRED")
    rows = source.get("records")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise SourceHold("BOUNDED_SOURCE_ROWS_REQUIRED")
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    results = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise SourceHold("SOURCE_RECORD_NOT_MAPPING")
        rid = _string(raw.get("id"), max_length=90)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_]{5,89}", rid):
            raise SourceHold("SOURCE_ID_INVALID")
        name = _string(raw.get("display_name"), max_length=160)
        url = _string(raw.get("source_url"), max_length=1100)
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.netloc not in ALLOWED_HOSTS
                or not parsed.path or parsed.username or parsed.password
                or parsed.fragment or parsed.query):
            raise SourceHold("SOURCE_URL_NOT_APPROVED_FIRST_PARTY_OR_MARKETPLACE")
        # A hostname alone is not a source citation. The exact original
        # publication class/path must be observed, never a vendor homepage.
        prefixes = {
            "www.upwork.com": "/freelance-jobs/apply/",
            "www.clueso.io": "/careers/",
            "jobs.ashbyhq.com": "/Paragon/",
            "credal.ai": "/careers",
        }
        if not parsed.path.startswith(prefixes[parsed.netloc]):
            raise SourceHold("SOURCE_PUBLISHER_PATH_NOT_EVIDENCED")
        if rid in seen_ids or url in seen_urls:
            raise SourceHold("DUPLICATE_COMPANY_EVIDENCE_SOURCE")
        seen_ids.add(rid)
        seen_urls.add(url)
        kind = raw.get("source_kind")
        route = raw.get("route_type")
        scope = raw.get("external_procurement_scope")
        if kind not in ALLOWED_KINDS or route not in ALLOWED_ROUTES or scope not in ALLOWED_SCOPES:
            raise SourceHold("SOURCE_KIND_ROUTE_OR_SCOPE_INVALID")
        requested = raw.get("buyer_request_observed")
        company_id = raw.get("company_identity_verified")
        technical = raw.get("technical_delivery_credentials_verified")
        if any(type(v) is not bool for v in (requested, company_id, technical)):
            raise SourceHold("QUALIFICATION_FLAGS_MUST_BE_BOOLEAN")
        if kind == "COMPANY_OFFICIAL_HIRING":
            if requested or not company_id or scope != "NONE" or route == "PLATFORM_APPLICATION_ONLY":
                raise SourceHold("HIRING_SIGNAL_MASQUERADES_AS_PURCHASE_INTENT")
            if raw.get("claim_stage") != "PUBLIC_HIRING_FIT_HYPOTHESIS":
                raise SourceHold("JOB_AD_INTENT_NOT_HYPOTHESIS")
        else:
            if not requested or company_id or route != "PLATFORM_APPLICATION_ONLY":
                raise SourceHold("PLATFORM_ANONYMOUS_BUYER_MUST_STAY_ANONYMOUS")
            if raw.get("claim_stage") != "PUBLIC_REQUEST_NOT_VERIFIED_BUYER" or scope == "NONE":
                raise SourceHold("PROCUREMENT_INTENT_EVIDENCE_UNTRUSTED")
        evidence_date = date.fromisoformat(_string(raw.get("observed_at"), max_length=10))
        if evidence_date > today or (today - evidence_date).days > 7:
            raise SourceHold("EVIDENCE_TOO_OLD_TO_PRESENT_AS_FRESH")
        observation = _string(raw.get("source_observation"), max_length=750)
        sample = raw.get("sample_path")
        sample_ready = False
        sample_sha256 = None
        if sample is not None:
            sample = _string(sample, max_length=175)
            if (not re.fullmatch(r"docs/commercial/[A-Z0-9_]+_20261024\.md", sample)):
                raise SourceHold("SAMPLE_NOT_ORIGINAL_COMMERCIAL_DOCUMENT")
            dest = root / sample
            if (dest.is_symlink() or not dest.is_file() or
                    not 350 <= dest.stat().st_size <= MAX_SAMPLE_BYTES or
                    not dest.resolve().is_relative_to((root / "docs/commercial").resolve())):
                raise SourceHold("PUBLIC_SAMPLE_MISSING_OR_UNSAFE")
            from hashlib import sha256
            sample_sha256 = sha256(dest.read_bytes()).hexdigest()
            sample_ready = True
        # BUILD_STAGE refers exclusively to public-sample preparation. Neither
        # a real buyer conversation nor customer-specific diagnostic is implied.
        build_state = ("PUBLIC_EVIDENCE_SAMPLE_BUILT" if sample_ready
                       else "PUBLIC_SIGNAL_RESEARCH_ONLY")
        blocks = ["BUYER_RESPONSE_NOT_VERIFIED",
                  "RECIPIENT_AND_CONTACT_PURPOSE_NOT_VERIFIED",
                  "CANONICAL_SUPPRESSION_FRESHNESS_NOT_PROVEN"]
        if not suppression_fresh:
            blocks.append("EXISTING_MAILBOX_EVIDENCE_STALE")
        if kind == "MARKETPLACE_EXTERNAL_SERVICE_REQUEST":
            blocks.extend(["ANONYMOUS_BUYER_COMPANY_IDENTITY",
                           "FREELANCER_PLATFORM_ELIGIBILITY_UNVERIFIED"])
            if not technical:
                blocks.append("BUYER_REQUIRED_TECHNICAL_DELIVERY_PROOF_MISSING")
        else:
            blocks.append("EXTERNAL_BUYING_SIGNAL_NOT_PROVEN")
        results.append({
            "source_id": rid, "display_name": name, "signal_kind": kind,
            "source_url": url, "evidence_observed_at": evidence_date.isoformat(),
            "public_observation": observation,
            "external_request_observed": requested,
            "verified_company_identity": company_id,
            "person_bound_recipient_verified": False,
            "buyer_interest_in_empire_verified": False,
            "approved_catalog_product": PRODUCT_CODE,
            "stage": build_state,
            "sample_path": sample if sample_ready else None,
            "sample_sha256": sample_sha256,
            "client_private_data_accessed": False,
            "technical_delivery_credentials_verified": technical,
            "next_owner": ("PLATFORM_ELIGIBILITY_AND_CAPABILITY_REVIEW"
                           if requested else "SOURCED_COMMERCIAL_INTRO_REVIEW"),
            "gate_blocks": sorted(set(blocks)),
            "contact_channel_type": route,
            "outbound_ready": False, "outbound_authorized": False,
            "crm_promotion_authorized": False, "buyer_quote_authorized": False,
            "accepted_customer_scope": False, "realised_revenue_verified": False,
        })
    results.sort(key=lambda r: (
        0 if r["external_request_observed"] else 1,
        0 if r["sample_path"] else 1, r["source_id"]))
    counts = Counter(r["stage"] for r in results)
    return {
        "schema_version": "empire.predictive_revenue.saas_demand_build_stage.v1",
        "mode": "BUILD_STAGE_PRIVATE_RESEARCH",
        "existing_os": "EmpireOS",
        "existing_database": "EmpireDB",
        "existing_crm": "Smart CRM",
        "existing_catalog_product_code": product.product_code,
        "existing_catalog_product_name": product.name,
        "original_product_entry_price_cents": product.deployment_price_cents,
        "original_product_currency": product.currency,
        "approved_price_is_not_an_accepted_buyer_quote": True,
        "reviewed_source_date": observed_date.isoformat(),
        "public_signal_count": len(results),
        "external_service_requests_observed": sum(
            row["external_request_observed"] for row in results),
        "company_hiring_fit_hypotheses": sum(
            row["signal_kind"] == "COMPANY_OFFICIAL_HIRING" for row in results),
        "private_public_evidence_samples_built": counts["PUBLIC_EVIDENCE_SAMPLE_BUILT"],
        "real_buyer_conversations_verified": 0,
        "signed_scope_verified": 0, "paid_customer_count_verified": 0,
        "canonical_suppression_fresh": suppression_fresh,
        "customer_rows_written": 0, "new_emails_sent": 0,
        "outbound_send_authorized": False,
        "production_site_mutated": False, "new_product_created": False,
        "new_crm_created": False, "new_scheduler_created": False,
        "realised_revenue_verified": False, "build_queue": results,
    }


def write_private(path: Path, report: dict) -> None:
    # Writes one private READ MODEL in the existing acquisition-research folder;
    # never a prospect or CRM record, and never a live-site file.
    path = Path(path)
    parent = path.parent
    if (parent.is_symlink() or not parent.is_dir() or path.is_symlink()):
        raise SourceHold("PRIVATE_RUNTIME_DESTINATION_UNSAFE")
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        if not path.is_file() or mode & 0o077:
            raise SourceHold("EXISTING_PRIVATE_RUNTIME_FILE_NOT_PRIVATE")
    fd, temp = tempfile.mkstemp(prefix=".saas-demand-build-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf8") as f:
            os.fchmod(f.fileno(), 0o600)
            json.dump(report, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
