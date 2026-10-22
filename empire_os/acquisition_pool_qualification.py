"""Read-only qualification across VC prospect and contractor acquisition pools.

Raw discoveries remain research candidates, never buyers or approved contacts.
Only owner-verified offers can be passed to the canonical copy brief bridge.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from empire_os.acquisition_copy_bridge import prepare_acquisition_copy

LANES = ("vc_portfolio", "contractor_quote")

def qualify_pool(*, lane: str, records: Sequence[Mapping]) -> dict:
    if lane not in LANES:
        raise ValueError("unsupported lane")
    if not isinstance(records, (list, tuple)) or len(records) > 1000:
        raise ValueError("bounded records required")
    seen = set()
    results = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("record mapping required")
        ref = record.get("prospect_ref")
        if not isinstance(ref, str) or not ref.strip() or len(ref)>128 or ref in seen:
            raise ValueError("unique opaque prospect_ref required")
        seen.add(ref)
        verified_company = record.get("company_identity_verified") is True
        current_trigger = record.get("dated_commercial_trigger_verified") is True
        fit = record.get("product_fit_verified") is True
        suppression = record.get("suppression_checked") is True
        permission = record.get("contact_permission_cleared") is True
        copy = prepare_acquisition_copy(lane=lane, evidence=record)
        missing = [key for key, passed in (
            ("company_identity_verified",verified_company),
            ("dated_commercial_trigger_verified",current_trigger),
            ("product_fit_verified",fit),
        ) if not passed]
        if copy["status"] == "HOLD":
            missing.extend("copy." + field for field in copy["missing_evidence"])
        reviewable = not missing
        results.append({
            "prospect_ref": ref, "lane": lane,
            "status": "QUALIFIED_FOR_REVIEW" if reviewable else "RESEARCH_ONLY",
            "copy_brief_ready": reviewable,
            "contact_review_ready": reviewable and suppression and permission,
            "missing_evidence": missing,
            "outbound_authorized": False,
        })
    return {
        "schema_version": "empire.acquisition_pool_qualification.v1",
        "mode": "OBSERVE", "lane": lane,
        "discovered": len(results),
        "qualified_for_review": sum(r["status"] == "QUALIFIED_FOR_REVIEW" for r in results),
        "contact_review_ready": sum(r["contact_review_ready"] for r in results),
        "records": results,
        "crm_writes": False, "outbound_authorized": False,
        "verified_buyers": None, "realised_revenue": None,
    }
