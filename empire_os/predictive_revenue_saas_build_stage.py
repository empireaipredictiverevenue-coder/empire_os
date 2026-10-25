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


def verify_clueso_official_sources(*, get=None) -> dict:
    """Optional bounded GET of two exact first-party pages; no contact capture.

    Verifies source availability, NOT buying intent or permission to send.
    """
    from hashlib import sha256
    from urllib.request import Request, urlopen

    pages = (
        ("founding_ae", "https://www.clueso.io/careers/founding-ae",
         ("Neel Balar", "PLG signups", "Oct 13, 2026")),
        ("contact_routes", "https://www.clueso.io/contact",
         ("Partnerships and referrals", "Privacy and data requests")),
    )
    def real_get(url: str) -> tuple[str, int, bytes]:
        req = Request(
            url, method="GET",
            headers={"User-Agent": "EmpireOS-SaaS-Official-Source-GET-Only/1"})
        with urlopen(req, timeout=10) as response:
            return response.geturl(), response.status, response.read(250_001)

    getter = get or real_get
    checks = []
    for label, url, markers in pages:
        try:
            final_url, status, data = getter(url)
            parsed = urlsplit(final_url)
            valid = (
                status == 200 and len(data) <= 250_000 and
                parsed.scheme == "https" and
                parsed.netloc == "www.clueso.io" and
                parsed.path == urlsplit(url).path and
                all(marker in data.decode("utf8", "replace") for marker in markers)
            )
            checks.append({
                "source": label, "official_url": url,
                "verified": valid,
                "content_sha256_if_verified": sha256(data).hexdigest() if valid else None,
            })
        except (OSError, ValueError, TypeError):
            checks.append({
                "source": label, "official_url": url,
                "verified": False, "content_sha256_if_verified": None,
            })
    success = len(checks) == 2 and all(c["verified"] for c in checks)
    return {
        "schema_version": "empire.saas.clueso_first_party_source_check.v1",
        "status": ("OFFICIAL_CLUESO_PAGES_GET_VERIFIED"
                   if success else "OFFICIAL_CLUESO_PAGES_HELD"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_checks": checks,
        "independent_external_procurement_verified": False,
        "linkedin_outreach_authorized": False,
        "email_outreach_authorized": False,
        "sender_or_company_contact_data_collected": False,
        "customer_records_written": False,
    }


def commercial_truth(
    observer: dict | None, buyer_queue: dict | None, *,
    now: datetime | None = None,
) -> dict:
    """Conservative aggregate projection of existing owner read models only.

    Never infer a CRM row, genuine buyer identity or signed sale from a count.
    HELD, stale, malformed and missing canonical observations remain UNKNOWN.
    """
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None or when.utcoffset() is None:
        raise SourceHold("SOURCE_REVIEW_TIME_MUST_BE_AWARE")
    source_status = "OWNER_SOURCE_NOT_AVAILABLE"
    observed_at = None
    observed_count = None
    status = "CANONICAL_SOURCE_UNKNOWN"
    if isinstance(observer, dict) and observer.get("schema_version") == (
        "empire.gtm.integration_observer.v1"
    ):
        raw = observer.get("canonical_sales_source_ops")
        if isinstance(raw, dict):
            source_status = str(raw.get("status") or "OWNER_SOURCE_NOT_AVAILABLE")[:125]
            observed_at = observer.get("generated_at")
            try:
                snapshot_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
                age = (when - snapshot_at).total_seconds()
            except (ValueError, AttributeError, TypeError):
                age = float("inf")
            if (
                0 <= age <= 3600
                and source_status == "CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED"
                and raw.get("source_count_verified") is True
                and all(
                    type(raw.get(k)) is int and raw[k] == 0
                    for k in ("canonical_sales_acquisitions",
                              "canonical_commercial_enquiries",
                              "canonical_predictive_revenue_enquiries")
                )
            ):
                observed_count = 0
                status = "RECENT_CANONICAL_SOURCE_ZERO_OBSERVED"
    queue_timestamp_fresh = False
    if isinstance(buyer_queue, dict):
        try:
            queue_date = datetime.fromisoformat(
                buyer_queue["generated_at"].replace("Z", "+00:00"))
            age = (when - queue_date).total_seconds()
            queue_timestamp_fresh = 0 <= age <= 3600
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
    snapshot_fresh = (
        queue_timestamp_fresh and isinstance(buyer_queue, dict)
        and buyer_queue.get("schema_version") == "buyer-network-candidate-queue-v1"
        and buyer_queue.get("gmail_snapshot_fresh") is True
    )
    return {
        "status": status, "original_gtm_source_status": source_status,
        "gtm_observed_at": observed_at,
        "canonical_sales_acquisitions_if_verified": observed_count,
        "original_buyer_network_gmail_snapshot_fresh": snapshot_fresh,
        "named_real_buyer_identity_verified": False,
        "source_to_tenant_crm_lineage_verified": False,
        "accepted_sale_verified": False,
        "payments_verified": False,
        "outbound_authority": False,
    }


def priority_action(row: dict) -> dict:
    """Actionable *review* order only, never an outbound/CRM execution decision."""
    rid = row["source_id"]
    sample = row["sample_path"]
    request = row["external_request_observed"]
    route = row["contact_channel_type"]
    if request:
        rank = (4 if rid == "xorlab_enterprise_revops_20261025"
                else 3 if "hubspot" in rid else 2)
        basis = (
            "PUBLIC_REQUEST_SELF_IDENTIFIES_XORLAB_BUT_CLIENT_REFERENCES_AND_HUBSPOT_DELIVERY_UNVERIFIED"
            if rid == "xorlab_enterprise_revops_20261025"
            else "STRICT_HUBSPOT_DELIVERY_CASE_STUDY_UNVERIFIED"
            if "hubspot" in rid
            else "LIGHTWEIGHT_FOUR_PERSON_SALES_PROCESS_FITS_DOCUMENTED_SAMPLE"
        )
        return {
            "source_id": rid, "review_rank": rank,
            "owner": "EXISTING_COMMERCIAL_ACQUISITION_OWNER",
            "action": "RECHECK_PLATFORM_REQUEST_AND_ELIGIBILITY",
            "review_priority_basis": basis,
            "deliverable": "Evidence of active client request, legitimate platform"
                           " application eligibility, qualified delivery owner and"
                           " honest matched scope",
            "free_sample_available": bool(sample),
            "reason_not_send_ready": "ANONYMOUS_MARKETPLACE_BUYER_AND_DELIVERY_GATES",
            "channel": "ORIGINAL_MARKETPLACE_ONLY",
            "ready_for_email": False,
            "ready_for_application": False,
        }
    if route == "FOUNDER_PROFESSIONAL_INTRO_REVIEW":
        rank, action, reason = (
            1, "VERIFY_FOUNDER_NETWORK_CHANNEL_AND_CANONICAL_SUPPRESSION",
            "NO_VERIFIED_BUYER_INTENT_OR_APPROVED_INTRO"
        )
    elif sample:
        rank, action, reason = (
            4, "VERIFY_APPROPRIATE_COMMERCIAL_PERSON_AND_CHANNEL",
            "PUBLIC_HIRING_ROLE_NOT_EXTERNAL_PROCUREMENT"
        )
    else:
        rank, action, reason = (
            5, "BUILD_COMPANY_RELEVANT_PUBLIC_VALUE_SAMPLE",
            "NO_SAMPLE_NO_BUYING_INTENT_NO_CONTACT_AUTHORITY"
        )
    return {
        "source_id": rid, "review_rank": rank,
        "owner": "EXISTING_COMMERCIAL_ACQUISITION_OWNER",
        "action": action,
        "deliverable": ("One company-specific public source review, confirmed"
                        " business purpose, exact contact-history and suppression"
                        " receipt before individually reviewed outreach"
                        if sample else "One-page attributable, public-only diagnostic"
                        " example with source date and no private claims"),
        "free_sample_available": bool(sample),
        "reason_not_send_ready": reason,
        "channel": route,
        "ready_for_email": False, "ready_for_application": False,
    }


def build(root: Path, source: dict, *, now: date | None = None,
          suppression_fresh: bool = False,
          intake_observer: dict | None = None,
          buyer_queue: dict | None = None) -> dict:
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
            if (not re.fullmatch(r"docs/commercial/[A-Z0-9_]+_2026102[45]\.md", sample)):
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
    review_actions = sorted((priority_action(row) for row in results),
                            key=lambda action: (action["review_rank"],
                                                action["source_id"]))
    commercial_observation = commercial_truth(intake_observer, buyer_queue)
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
        "original_commercial_truth": commercial_observation,
        "next_review_actions": review_actions,
        "review_order_is_not_expected_revenue": True,
        "marketplace_submission_authorized": False,
        "founder_linkedin_outreach_authorized": False,
    }


FOUNDER_CLUESO_REPORT_REL = Path(
    "docs/commercial/CLUESO_FOUNDER_REPORTED_LINKEDIN_FIRST_TOUCH_20261025.json"
)


def load_founder_clueso_first_touch(path: Path) -> dict | None:
    """Exact owner statement, not independently verified LinkedIn telemetry."""
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000:
        raise SourceHold("FOUNDER_FIRST_TOUCH_SOURCE_UNSAFE")
    try:
        receipt = json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        raise SourceHold("FOUNDER_FIRST_TOUCH_SOURCE_INVALID") from None
    if not isinstance(receipt, dict):
        raise SourceHold("FOUNDER_FIRST_TOUCH_SOURCE_NOT_OBJECT")
    return receipt


def apply_founder_clueso_first_touch(report: dict, receipt: dict, *,
                                     now: date | None = None) -> dict:
    """Mark a founder-*reported* LinkedIn first touch as no-repeat/await reply.

    A user statement is evidence of what the user says they did, not platform
    delivery, a reply, verified buyer interest, authorisation to follow up or
    a CRM/economic receipt. Keep all prior external gates unchanged.
    """
    from copy import deepcopy

    expected = {
        "schema_version": "empire.saas.founder_reported_first_touch.v1",
        "prospect_source_id": "clueso_founding_ae_20261024",
        "company": "Clueso",
        "recipient_public_profile": "https://www.linkedin.com/in/neelbalar7",
        "channel": "LINKEDIN_MANUAL",
        "report_source": "FOUNDER_DIRECT_CONFIRMATION_IN_CHAT",
        "founder_reported_sent": True,
        "provider_message_id": None,
        "provider_delivered_verified": False,
        "actual_send_timestamp_verified": False,
        "actual_message_body_independently_verified": False,
        "positive_reply_verified": False,
        "buying_intent_verified": False,
        "suppression_provider_reconciled": False,
        "authorizes_repeat_first_touch": False,
        "authorizes_followup": False,
        "crm_promotion_authorized": False,
        "payment_authorized": False,
        "next_action": "AWAIT_AUTHENTIC_REPLY_NO_DUPLICATE_INTRO",
        "approved_draft_reference":
            "docs/commercial/CLUESO_FOUNDER_INTRO_SOURCE_VERIFIED_20261024.md",
    }
    if not isinstance(receipt, dict) or any(
        receipt.get(key) != value or type(receipt.get(key)) is not type(value)
        for key, value in expected.items()
    ):
        raise SourceHold("FOUNDER_FIRST_TOUCH_ATTESTATION_CONTRACT_INVALID")
    try:
        reported = date.fromisoformat(receipt["reported_date_utc"])
    except (KeyError, ValueError, TypeError):
        raise SourceHold("FOUNDER_FIRST_TOUCH_REPORT_DATE_INVALID") from None
    today = now or datetime.now(timezone.utc).date()
    if reported > today:
        raise SourceHold("FOUNDER_FIRST_TOUCH_REPORT_DATE_IN_FUTURE")
    # Historic no-repeat receipts do not expire: a stale source does not
    # restore permission to repeat an introduction.
    updated = deepcopy(report)
    target = "clueso_founding_ae_20261024"
    matching_rows = [row for row in updated.get("build_queue", [])
                     if row.get("source_id") == target]
    matching_actions = [item for item in updated.get("next_review_actions", [])
                        if item.get("source_id") == target]
    if len(matching_rows) != 1 or len(matching_actions) != 1:
        raise SourceHold("FOUNDER_FIRST_TOUCH_TARGET_NOT_IN_EXISTING_QUEUE")
    row = matching_rows[0]
    row.update({
        "founder_reported_contact_status":
            "FOUNDER_REPORTED_LINKEDIN_SENT_PROVIDER_UNVERIFIED",
        "founder_reported_sent_on": reported.isoformat(),
        "sender_platform_message_id_verified": False,
        "first_touch_no_repeat": True,
        "reply_verified": False, "accepted_customer_scope": False,
        "buyer_interest_in_empire_verified": False,
        "outbound_ready": False, "outbound_authorized": False,
        "crm_promotion_authorized": False,
    })
    action = matching_actions[0]
    action.update({
        "review_rank": 6,
        "action": "AWAIT_AUTHENTIC_LINKEDIN_REPLY_NO_DUPLICATE_INTRO",
        "deliverable": "Wait for a genuine LinkedIn reply; if supplied, "
                       "verify exact sender/thread and offer existing free "
                       "Clueso sample only upon positive buyer interest.",
        "reason_not_send_ready": "FOUNDER_REPORTED_FIRST_TOUCH_NO_DUPLICATE",
        "contact_status": "FOUNDER_REPORTED_SENT_PLATFORM_UNVERIFIED",
        "first_touch_no_repeat": True,
        "ready_for_email": False, "ready_for_application": False,
        "approved_followup": False,
    })
    updated["next_review_actions"].sort(
        key=lambda item: (item["review_rank"], item["source_id"]))
    updated["founder_reported_linkedin_manual_first_touch_count"] = 1
    updated["founder_reported_first_touch"] = {
        "source_id": target,
        "channel": "LINKEDIN_MANUAL",
        "report_source": "FOUNDER_DIRECT_CONFIRMATION_IN_CHAT",
        "reported_date_utc": reported.isoformat(),
        "platform_send_or_delivery_verified": False,
        "reply_verified": False, "first_touch_no_repeat": True,
        "followup_authorized": False,
    }
    return updated


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
