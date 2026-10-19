"""Evidence-only Scrapling-to-Empire-Waterfall planning and offline replay.

Read-only integration with the EXISTING Waterfall. Never calls .enrich(), .search(),
a crawler, a database, an LLM or a customer endpoint. Source observations are
not canonical leads, verified contacts, qualified claimants or sellable records.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
import re

from empire_os.source_intelligence import SOURCES
from empire_os.waterfall import LeadContact, build_default_waterfall


REPORT_SCHEMA = "empire.scrapling_source_evidence.v1"
MAX_REVIEW_RECORDS = 25
REVIEW_PURPOSE = "internal_b2b_research"

# Only business-identity scopes. In particular never accept a person involved
# in a tort, illness, insurance claim, debt or other vulnerable situation.
VERTICAL_TARGETS: dict[str, frozenset[str]] = {
    "roofing": frozenset({"contractor"}),
    "solar": frozenset({"contractor"}),
    "hvac": frozenset({"contractor"}),
    "restoration": frozenset({"contractor"}),
    "plumbing": frozenset({"contractor"}),
    "dental": frozenset({"medical_practice"}),
    "insurance": frozenset({
        "insurance_broker", "insurance_agent", "insurance_carrier",
        "third_party_administrator", "managed_repair_network",
    }),
    "legal": frozenset({"law_firm"}),
    "mass_torts": frozenset({"law_firm"}),
    "general_contractor": frozenset({"contractor"}),
}

# No regulated vertical may skip a jurisdiction-specific B2B review.
REGULATED_VERTICALS = frozenset({"insurance", "legal", "mass_torts", "dental"})
REGULATED_REQUIREMENTS = {
    "insurance": "insurance_b2b_jurisdiction_review",
    "legal": "law_firm_b2b_jurisdiction_review",
    "mass_torts": "mass_tort_firm_jurisdiction_legal_review",
    "dental": "healthcare_practice_jurisdiction_b2b_review",
}


@dataclass(frozen=True)
class EvidenceReview:
    vertical: str
    target_kind: str
    jurisdiction: str
    company_identity_ref: str = ""
    jurisdiction_policy_ref: str = ""
    verified_first_party_website: str = ""
    website_verification_ref: str = ""
    purpose: str = REVIEW_PURPOSE


def _evidence_ref(text: Any) -> bool:
    return (
        isinstance(text, str) and 5 <= len(text) <= 300
        and text == text.strip() and not any(ord(c) < 32 for c in text)
    )


def _verified_public_https(url: str) -> bool:
    if not isinstance(url, str) or not url or len(url) > 2048:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
            return False
        host = (parsed.hostname or "").lower().strip(".")
    except ValueError:
        return False
    # Deliberately restrict to DNS names: no localhost, internal hosts, IP
    # literals or custom ports. Actual network resolution is NOT performed.
    if not re.fullmatch(r"[a-z0-9.-]+", host) or "." not in host:
        return False
    if host.startswith((".", "-")) or host.endswith((".", "-")):
        return False
    if host.endswith((".local", ".internal", ".localhost")):
        return False
    if re.fullmatch(r"\d+(?:\.\d+){3}", host):
        return False
    return True


def _source_niche_allowed(source_niches: tuple[str, ...], vertical: str) -> bool:
    return "all" in source_niches or vertical in source_niches


def _blank_result(review: EvidenceReview, reasons: list[str]) -> dict[str, Any]:
    """Public-safe status only; no raw consumer details or contact data."""
    return {
        "schema_version": "empire.waterfall_source_bridge.v1",
        "mode": "OFFLINE_REVIEW_ONLY",
        "vertical": str(review.vertical),
        "target_kind": str(review.target_kind),
        "jurisdiction": str(review.jurisdiction),
        "state": "HOLD" if reasons else "EVIDENCE_REVIEW_READY",
        "reasons": sorted(set(reasons)),
        "provider_order_review_only": [],
        "provider_execution_authorized": False,
        "contact_promotion_authorized": False,
        "canonical_insert_authorized": False,
        "outbound_authorized": False,
        "customer_export_authorized": False,
        "claims_handling_authorized": False,
        "verified_lead_count": 0,
        "source_observation_only": True,
        "waterfall_factory": "empire_os.waterfall.build_default_waterfall",
        "execution_authority": "none",
    }


def build_waterfall_source_review(
    report: Mapping[str, Any],
    *,
    record_index: int,
    review: EvidenceReview,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Propose source/provider order without running any providers.

    Evidence refs are *assertions to audit*, never a substitute for an
    independent rights/identity/compliance determination.
    """
    if type(record_index) is not int or not 0 <= record_index < MAX_REVIEW_RECORDS:
        raise ValueError("record_index must be a bounded integer")
    if not isinstance(report, Mapping):
        raise TypeError("report must be mapping")
    if not isinstance(review, EvidenceReview):
        raise TypeError("review must be EvidenceReview")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")
    reasons: list[str] = []
    if report.get("schema_version") != REPORT_SCHEMA or report.get("mode") != "OFFLINE_REVIEW_ONLY":
        reasons.append("untrusted_source_report")
    if report.get("live_network_access") is not False or report.get("canonical_empiredb_writes") is not False:
        reasons.append("source_report_not_observe_only")
    if report.get("sellable_inventory_verified") is not False:
        reasons.append("source_report_invalid_commercial_claim")
    if not isinstance(review.vertical, str) or review.vertical not in VERTICAL_TARGETS:
        reasons.append("vertical_not_approved")
    elif review.target_kind not in VERTICAL_TARGETS[review.vertical]:
        reasons.append("not_an_approved_business_entity")
    if review.purpose != REVIEW_PURPOSE:
        reasons.append("unsupported_purpose")
    if not _evidence_ref(review.company_identity_ref):
        reasons.append("missing_independently_reviewed_company_identity")
    if not _evidence_ref(review.jurisdiction) or len(review.jurisdiction) > 100:
        reasons.append("jurisdiction_required")
    if review.vertical in REGULATED_VERTICALS and not _evidence_ref(review.jurisdiction_policy_ref):
        reasons.append(REGULATED_REQUIREMENTS[review.vertical])

    source_id = report.get("source_id")
    source = SOURCES.get(source_id) if isinstance(source_id, str) else None
    if source is None or "internal_acquisition" not in source.allowed_uses:
        reasons.append("source_rights_not_registered")
    else:
        if source.production_status != "verified":
            reasons.append("source_contract_not_production_verified")
        if not _source_niche_allowed(source.niches, review.vertical):
            reasons.append("source_not_authorized_for_vertical")
        claimed_url = report.get("source_url")
        if (not _verified_public_https(claimed_url)
                or urlparse(str(claimed_url)).hostname != urlparse(source.url).hostname):
            reasons.append("source_url_host_mismatch")
        if not isinstance(review.jurisdiction, str) or not review.jurisdiction.upper().startswith(source.country_code + "-"):
            reasons.append("source_jurisdiction_mismatch")
    refs = report.get("review_evidence_refs")
    if not isinstance(refs, list) or len(refs) < 3 or not all(_evidence_ref(r) for r in refs):
        reasons.append("source_governance_receipts_missing")
    stamp = report.get("observed_at")
    try:
        timestamp = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("naive timestamp")
        age_days = (current - timestamp).total_seconds() / 86400
        if age_days < -1 or age_days > 90:
            reasons.append("stale_or_future_source_evidence")
    except (TypeError, ValueError, OverflowError):
        reasons.append("source_observed_at_invalid")
    if (not isinstance(report.get("content_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", report["content_sha256"])):
        reasons.append("source_document_digest_missing")
    records = report.get("records")
    if not isinstance(records, list) or len(records) > MAX_REVIEW_RECORDS or record_index >= len(records):
        reasons.append("record_not_in_bounded_report")
        record: Mapping[str, Any] = {}
    else:
        value = records[record_index]
        record = value if isinstance(value, Mapping) else {}
        if record.get("source_id") != source_id or record.get("source_url") != report.get("source_url"):
            reasons.append("record_source_mismatch")
        if record.get("niche_observed") != review.vertical:
            reasons.append("record_niche_mismatch")
        if not isinstance(record.get("business_name"), str) or not record["business_name"].strip():
            reasons.append("business_identity_unobserved")
        if record.get("canonical_prospect_id") is not None or record.get("quality") != "unverified_source_observation":
            reasons.append("record_incorrectly_promoted")
        if record.get("commercial_resale_authorized") is not False:
            reasons.append("record_resale_claim_forbidden")

    site = review.verified_first_party_website
    if site or review.website_verification_ref:
        if not (_verified_public_https(site) and _evidence_ref(review.website_verification_ref)):
            reasons.append("verified_first_party_site_proof_required")

    output = _blank_result(review, reasons)
    if reasons:
        return output

    # Derive the exact candidate provider names from our EXISTING factory;
    # never instantiate any new provider type, invoke search() or .enrich().
    default_names = tuple(p.name for p in build_default_waterfall().providers)
    if site:
        preferred = ("empire_hunter", "registry_scraper", "site_crawler")
    else:
        # An observed directory listing is NOT proof of a company-owned site.
        preferred = ("registry_scraper",)
    order = [name for name in preferred if name in default_names]
    output.update({
        "provider_order_review_only": order,
        "default_provider_names": list(default_names),
        "observed_business": str(record["business_name"])[:250],
        "observed_source_id": source_id,
        "observed_document_sha256": report.get("content_sha256"),
        "observed_at": stamp,
        "company_identity_review_ref": review.company_identity_ref,
        "jurisdiction_policy_ref": review.jurisdiction_policy_ref or None,
        "website_evidence_ref": review.website_verification_ref or None,
        "first_party_website_review_only": site or None,
        "next_steps": [
            "independently verify company identity and source rights",
            "confirm contact belongs to decision maker through current waterfall gate",
            "run separate suppression and outreach authority checks",
            "confirm buyer capacity and delivery before commercial promotion",
        ],
    })
    return output


def replay_existing_waterfall_gate(
    plan: Mapping[str, Any],
    provider_observations: Mapping[str, LeadContact | None],
) -> dict[str, Any]:
    """Re-evaluate pre-existing provider responses WITHOUT provider execution.

    This is a fixture/diagnostic replay; even a valid contact cannot be sent or
    promoted. Untrusted provider return data never authorises activation.
    """
    if plan.get("schema_version") != "empire.waterfall_source_bridge.v1":
        raise ValueError("invalid plan schema")
    if plan.get("execution_authority") != "none" or plan.get("provider_execution_authorized") is not False:
        raise ValueError("execution authority not permitted")
    if not isinstance(provider_observations, Mapping):
        raise TypeError("provider_observations must be mapping")
    if plan.get("state") != "EVIDENCE_REVIEW_READY":
        return {
            "schema_version": "empire.waterfall_gate_replay.v1",
            "status": "HOLD", "checked": [], "would_pass": False,
            "execution_authority": "none", "contact_promotion_authorized": False,
        }
    order = plan.get("provider_order_review_only", [])
    actual = tuple(p.name for p in build_default_waterfall().providers)
    if not isinstance(order, list) or not order or len(order) > len(actual) or len(order) != len(set(order)) or any(name not in actual for name in order):
        raise ValueError("unapproved provider order")
    gate = build_default_waterfall().gate
    checked = []
    selected = None
    for provider_name in order:
        observed = provider_observations.get(provider_name)
        passed = isinstance(observed, LeadContact) and gate.validate(observed)
        checked.append({"provider": provider_name, "gate_passed": bool(passed)})
        if passed:
            selected = provider_name
            break
    return {
        "schema_version": "empire.waterfall_gate_replay.v1",
        "status": "OFFLINE_VALIDATION_ONLY",
        "checked": checked,
        "would_pass": selected is not None,
        "would_select_provider": selected,
        "contact_promotion_authorized": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }


def review_provider_order_by_verified_yield(
    plan: Mapping[str, Any],
    receipts: Mapping[str, Mapping[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Conservative empirical yield ranking; not model prediction or execution.

    Every available provider needs >=20 comparable, time-bounded, provenance-
    referenced attempts. Existing in-process Waterfall metrics alone have no
    niche/territory/time proofs and MUST NOT be accepted as these receipts.
    CORTEX/OMEGA predictions do not substitute for observed, validated wins.
    """
    if plan.get("schema_version") != "empire.waterfall_source_bridge.v1":
        raise ValueError("invalid waterfall plan")
    if plan.get("execution_authority") != "none" or plan.get("provider_execution_authorized") is not False:
        raise ValueError("unauthorised waterfall execution plan")
    if not isinstance(receipts, Mapping):
        raise TypeError("receipts must be mapping")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")
    names = plan.get("provider_order_review_only", [])
    original = list(names) if isinstance(names, list) else []
    existing_names = tuple(p.name for p in build_default_waterfall().providers)
    if (not original or len(original) != len(set(original))
            or any(name not in existing_names for name in original)
            or len(original) > len(existing_names)):
        original = []
    reasons = []
    yields: dict[str, tuple[int, int]] = {}
    if plan.get("state") != "EVIDENCE_REVIEW_READY" or not original:
        reasons.append("source_review_hold")
    else:
        for name in original:
            r = receipts.get(name)
            if not isinstance(r, Mapping):
                reasons.append(f"{name}:receipt_missing")
                continue
            n, w = r.get("attempts"), r.get("validated_wins")
            if (type(n) is not int or type(w) is not int
                    or not 20 <= n <= 100000 or not 0 <= w <= n):
                reasons.append(f"{name}:unreliable_sample")
                continue
            if (r.get("vertical") != plan.get("vertical")
                    or r.get("jurisdiction") != plan.get("jurisdiction")):
                reasons.append(f"{name}:cohort_mismatch")
                continue
            if not _evidence_ref(r.get("receipt_ref")):
                reasons.append(f"{name}:provenance_unverified")
                continue
            try:
                stamp = datetime.fromisoformat(
                    str(r.get("observed_at")).replace("Z", "+00:00")
                )
                if stamp.tzinfo is None:
                    raise ValueError("naive timestamp")
                age_days = (current - stamp).total_seconds() / 86400
                if age_days < -1 or age_days > 14:
                    reasons.append(f"{name}:stale_or_future_sample")
                    continue
            except (TypeError, ValueError, OverflowError):
                reasons.append(f"{name}:timestamp_invalid")
                continue
            yields[name] = (w, n)

    # Fail-closed to ORIGINAL order if ANY provider lacks comparable evidence.
    if reasons:
        reordered = original
        state = "DEFAULT_ORDER_PRESERVED"
    else:
        initial = {name: i for i, name in enumerate(original)}
        # Exact cross-products avoid floating-point ties / invented confidence.
        from functools import cmp_to_key

        def compare(a: str, b: str) -> int:
            aw, an = yields[a]
            bw, bn = yields[b]
            difference = aw * bn - bw * an
            if difference:
                return -1 if difference > 0 else 1
            return initial[a] - initial[b]

        reordered = sorted(original, key=cmp_to_key(compare))
        state = "EVIDENCE_BASED_OFFLINE_ORDER_PROPOSAL"

    return {
        "schema_version": "empire.waterfall_yield_review.v1",
        "mode": "OFFLINE_REVIEW_ONLY",
        "state": state,
        "default_order": original,
        "recommended_order_review_only": reordered,
        "evidence_cohort_complete": not reasons,
        "reasons": sorted(reasons),
        "provider_validated_yield": {
            name: {"validated_wins": wins, "attempts": attempts}
            for name, (wins, attempts) in sorted(yields.items())
        },
        "execution_authority": "none",
        "provider_execution_authorized": False,
        "contact_promotion_authorized": False,
        "outbound_authorized": False,
        "model_weight_mutation_authorized": False,
    }
