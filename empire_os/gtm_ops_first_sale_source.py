"""Observe the EXISTING privileged Ops Control first-sale source receipt.

This does not run SQL: only the authorized Ops owner executes the bounded
canonical EmpireDB source query. A source count is not an authenticated
customer, exact CRM receipt, contact approval, payment or recognized revenue.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

OPS = Path("runtime/ops_control/latest.json")
OPS_SCHEMA = "empire.ops_control_cycle.v1"
FIRST_SALE_SCHEMA = "empire.commercial.first_sale_live_conversion_observer.v1"
COUNTS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)


def assess_owner_ops(receipt: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    held: dict[str, Any] = {
        "status": "HELD_CANONICAL_ACQUISITION_OWNER_OPS_RECEIPT_REQUIRED",
        "canonical_commercial_enquiries": None,
        "canonical_predictive_revenue_enquiries": None,
        "canonical_sales_acquisitions": None,
        "source_count_verified": False,
        "exact_crm_readback_verified": False,
        "specific_response_consent_current_verified": False,
        "individual_buyer_identity_verified": False,
        "outreach_authorized": False,
        "payments_authorized": False,
        "database_writes": False,
        "execution_authority": "none",
    }
    if not isinstance(receipt, Mapping) or now.utcoffset() is None:
        return held
    if (receipt.get("schema_version") != OPS_SCHEMA
        or receipt.get("mode") != "OBSERVE"):
        return held
    try:
        ts = datetime.fromisoformat(str(receipt["observed_at"]).replace("Z", "+00:00"))
        if ts.utcoffset() is None or not timedelta(0) <= now - ts.astimezone(timezone.utc) <= timedelta(minutes=30):
            return held
    except (TypeError, ValueError, KeyError):
        return held
    first = receipt.get("first_sale_conversion_readiness")
    if (not isinstance(first, Mapping)
        or first.get("schema_version") != FIRST_SALE_SCHEMA
        or first.get("mode") != "OBSERVE"
        or first.get("execution_authority") != "none"
        or first.get("outbound_sent") is not False
        or first.get("crm_mutations") is not False
        or first.get("database_writes") is not False
        or first.get("payment_action") is not False
        or first.get("public_post_or_customer_submission_attempted") is not False
        or first.get("first_party_source_count_not_authenticated_buyer") is not True
        or first.get("verified_first_sale") is not None
        or first.get("recognized_revenue_cents") is not None):
        return held
    counts = first.get("canonical_sales_acquisition_counts")
    if not isinstance(counts, Mapping) or set(counts) != set(COUNTS):
        return held
    if any(type(counts[k]) is not int or not 0 <= counts[k] <= 20_000_000 for k in COUNTS):
        return held
    total = counts["sales_acquisition_rows"]
    if (counts["commercial_acquisition_rows"] + counts["predictive_acquisition_rows"] != total
        or counts["distinct_sales_prospects"] > total
        or counts["source_evidence_consistent_rows"] > total
        or counts["entity_unlinked_acquisition_rows"] > total
        or counts["founder_binding_exact_one_rows"] + counts["founder_binding_missing_or_ambiguous_rows"] != total):
        return held
    status = first.get("status")
    if status == "NO_CANONICAL_FIRST_PARTY_SALES_ENQUIRIES" and total == 0:
        new_status = "CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED"
    elif status == "FIRST_PARTY_ENQUIRY_TO_FOUNDER_BINDING_HOLD" and total > 0 and counts["founder_binding_exact_one_rows"] == 0:
        new_status = "CANONICAL_SALES_ENQUIRIES_FOUNDER_BINDING_HOLD"
    elif status == "FIRST_PARTY_ENQUIRY_PRESENT_OWNER_REVIEW_REQUIRED" and total > 0 and counts["founder_binding_exact_one_rows"] > 0:
        new_status = "CANONICAL_SALES_ENQUIRIES_PRESENT_EXACT_READBACK_REQUIRED"
    else:
        return held
    return {
        **held,
        "status": new_status,
        "canonical_commercial_enquiries": counts["commercial_acquisition_rows"],
        "canonical_predictive_revenue_enquiries": counts["predictive_acquisition_rows"],
        "canonical_sales_acquisitions": total,
        "source_count_verified": True,
    }


def observe_owner_ops_first_sale(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    path = root / OPS
    try:
        if (path.is_symlink() or (root / OPS.parent).is_symlink()
            or not path.is_file()):
            return assess_owner_ops(None, now=clock)
        stats = path.stat()
        if (stats.st_uid != 0 or stats.st_mode & 0o007
            or not 0 < stats.st_size <= 200_000):
            return assess_owner_ops(None, now=clock)
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return assess_owner_ops(None, now=clock)
    return assess_owner_ops(packet, now=clock)
