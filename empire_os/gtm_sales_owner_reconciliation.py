"""Read a DB-owner-approved aggregate sales/CRM reconciliation for original GTM.

No database, credentials, identity resolution, or contact access in this module.
Count agreement never proves an exact source->prospect->tenant receipt match.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Mapping

RECEIPT = Path("runtime/gtm_pipeline/owner_sales_reconciliation_latest.json")
SCHEMA = "empire.gtm.owner_sales_reconciliation.v1"
OWNER_SCHEMA = "empire.founder.sales_acquisition_crm_reconciliation.v1"
SOURCE_KEYS = (
    "commercial_acquisition_rows", "predictive_acquisition_rows",
    "sales_acquisition_rows", "distinct_sales_prospects",
    "source_evidence_consistent_rows", "entity_unlinked_acquisition_rows",
    "founder_binding_exact_one_rows",
    "founder_binding_missing_or_ambiguous_rows",
)
TENANT_KEYS = (
    "visible_commercial_sales_prospects",
    "visible_predictive_revenue_prospects", "visible_total_prospects",
)
ALL_KEYS = SOURCE_KEYS + TENANT_KEYS
ALLOWED = frozenset({
    "NO_CANONICAL_SALES_ACQUISITION_OBSERVED",
    "CANONICAL_INTAKE_EVIDENCE_INCONSISTENT",
    "IDENTITY_LINK_GAP_DETECTED",
    "TENANT_BINDING_GAP_DETECTED",
    "CRM_PROJECTION_GAP_DETECTED",
    "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH",
})

def public_review(receipt: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    """Return no personal data and NO authority, even on verified counts."""
    held = {
        "status": "HELD_OWNER_SOURCE_AND_CRM_RECONCILIATION_REQUIRED",
        "source_status": None,
        "canonical_sales_acquisitions": None,
        "tenant_visible_sales_prospects": None,
        "source_and_tenant_aggregate_valid": False,
        "exact_enquiry_lineage_verified": False,
        "contact_consent_for_this_enquiry_verified": False,
        "founder_crm_delivery_verified": False,
        "outreach_authorized": False,
        "payments_authorized": False,
        "crm_write_authorized": False,
        "execution_authority": "none",
    }
    if now.tzinfo is None or not isinstance(receipt, Mapping):
        return held
    if (receipt.get("schema_version") != SCHEMA
        or receipt.get("source_schema_version") != OWNER_SCHEMA
        or receipt.get("read_only") is not True
        or receipt.get("execution_authority") != "none"
        or receipt.get("source_status") not in ALLOWED):
        return held
    try:
        at = datetime.fromisoformat(str(receipt["generated_at_utc"]).replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError):
        return held
    if at.tzinfo is None or not timedelta(0) <= now - at <= timedelta(hours=24):
        return held
    nums = {key: receipt.get(key) for key in ALL_KEYS}
    if any(type(v) is not int or not 0 <= v <= 20_000_000 for v in nums.values()):
        return held
    total = nums["sales_acquisition_rows"]
    if (nums["commercial_acquisition_rows"] + nums["predictive_acquisition_rows"] != total
        or nums["distinct_sales_prospects"] > total
        or nums["source_evidence_consistent_rows"] > total
        or nums["entity_unlinked_acquisition_rows"] > total
        or nums["founder_binding_exact_one_rows"] +
           nums["founder_binding_missing_or_ambiguous_rows"] != total
        or nums["visible_commercial_sales_prospects"] +
           nums["visible_predictive_revenue_prospects"] > nums["visible_total_prospects"]):
        return held
    status = receipt["source_status"]
    if (status == "NO_CANONICAL_SALES_ACQUISITION_OBSERVED") != (total == 0):
        return held
    if status == "CANONICAL_INTAKE_EVIDENCE_INCONSISTENT" and nums["source_evidence_consistent_rows"] == total:
        return held
    if status == "IDENTITY_LINK_GAP_DETECTED" and nums["entity_unlinked_acquisition_rows"] == 0:
        return held
    if status == "TENANT_BINDING_GAP_DETECTED" and nums["founder_binding_missing_or_ambiguous_rows"] == 0:
        return held
    if status == "CRM_PROJECTION_GAP_DETECTED" and (
        nums["visible_commercial_sales_prospects"] + nums["visible_predictive_revenue_prospects"] != 0):
        return held
    if status == "NONZERO_SOURCE_AND_CRM_REQUIRE_RECEIPT_MATCH" and (
        nums["source_evidence_consistent_rows"] != total
        or nums["entity_unlinked_acquisition_rows"] != 0
        or nums["founder_binding_missing_or_ambiguous_rows"] != 0
        or nums["visible_commercial_sales_prospects"] +
           nums["visible_predictive_revenue_prospects"] == 0):
        return held
    return {
        **held,
        "status": ("NO_CANONICAL_SALES_ACQUISITIONS_IN_OWNER_READ"
                   if total == 0 else "SOURCE_OR_CRM_EVIDENCE_NEEDS_FOUNDER_REVIEW"),
        "source_status": status,
        "canonical_sales_acquisitions": total,
        "tenant_visible_sales_prospects": (
            nums["visible_commercial_sales_prospects"] +
            nums["visible_predictive_revenue_prospects"]),
        "source_and_tenant_aggregate_valid": True,
    }


def observe_owner_sales(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    path = root / RECEIPT
    try:
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_uid != 0
                or path.stat().st_mode & 0o077
                or not 0 < path.stat().st_size <= 10000
                or (root / RECEIPT.parent).is_symlink()):
            return public_review(None, now=clock)
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return public_review(None, now=clock)
    return public_review(packet, now=clock)
