"""First-payer exact-source/Quant bridge, for the existing Predictive owner.

This is private read-only REVIEW, not an authenticated buyer, signed offer,
model attestation, registry write, invoice, or revenue event. Reuses upstream
owner contracts. Never publishes raw tenant, opportunity, buyer, or source.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping

from empire_os.flagship_first_payer_owner_handoff import (
    review_current_first_payer_owner_handoff,
)
from empire_os.flagship_first_payer_quant_preflight import (
    review_first_payer_quant_preflight,
)
from empire_os.flagship_source_epoch_reconciliation import (
    review_source_epoch_reconciliation_runtime,
)
from empire_os.revenue_buyer_evidence_handoff import (
    review_one_commercial_evidence_request,
)
from empire_os.revenue_evidence_pathways import _read, market_identity_digest

SCHEMA = "empire.flagship.first_payer_scoped_quant_bridge.v1"
_GOOD_EPOCH = "FOUR_STAGE_SOURCE_IDENTITIES_ALIGNED"


def review_first_payer_scoped_quant_bridge(
    repo_root: str | Path, *, as_of: datetime,
    tenant_id: str | None = None,
    opportunity_key: str | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    quant_inputs: Mapping[str, Any] | None = None,
    source_receipts: Mapping[str, Mapping[str, Any]] | None = None,
    horizon_days: int = 30,
) -> dict[str, Any]:
    """Tie a scoped preview to an existing current source, never to a stale ID."""
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted timezone-aware clock required")
    if (tenant_id is None) != (opportunity_key is None):
        raise ValueError("tenant and opportunity must be supplied together")
    want_quant = any(value is not None for value in (
        model_name, model_version, quant_inputs, source_receipts,
    ))
    if want_quant and (tenant_id is None or model_name is None or model_version is None):
        raise ValueError("bounded scoped identity and explicit model required")
    if quant_inputs is not None and not isinstance(quant_inputs, Mapping):
        raise ValueError("original Quant inputs must be an explicit mapping")
    if source_receipts is not None and not isinstance(source_receipts, Mapping):
        raise ValueError("original receipt inputs must be an explicit mapping")
    root = Path(repo_root).resolve(strict=False)
    owner = review_current_first_payer_owner_handoff(root, as_of=as_of)
    epoch = review_source_epoch_reconciliation_runtime(root, as_of=as_of)
    result = {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SOURCE_EPOCH_HOLD",
        "owner_status": owner["status"],
        "source_epoch_status": epoch["status"],
        "opaque_opportunity_ref": None,
        "original_source_identity_bound": False,
        "original_market_revision_bound": False,
        "source_market_checked_from_current_snapshot": False,
        "tenant_scope_authenticated": False,
        "quant_preflight_status": None,
        "missing_quant_fields": None,
        "unsupported_source_fields": None,
        "quant_preview_checked": False,
        "original_model_probability_authenticated": False,
        "original_source_receipts_authenticated": False,
        "buyer_terms_authenticated": False,
        "buyer_capacity_authenticated": False,
        "buyer_specific_buybox_authenticated": False,
        "complete_original_registry_population_verified": False,
        "original_forecast_registered": False,
        "economic_memory_verified_terminal_pairs": None,
        "next_owner": "existing_opportunity_factory_owner",
        "next_action": "RESTORE_CONSISTENT_CANONICAL_SOURCE_EPOCH",
        "crm_accessed": False,
        "canonical_db_accessed": False,
        "database_writes": False,
        "outbound_sent": False,
        "payments_moved": False,
        "training_or_calibration_performed": False,
        "execution_authority": "none",
    }
    if epoch["status"] != _GOOD_EPOCH or epoch["join_result"] != "CANONICAL_PATHWAY_REVIEW_READY":
        return result

    state = owner["status"]
    if state not in (
        "FIRST_PAYER_BUYER_EVIDENCE_BLOCKED",
        "FIRST_PAYER_MARKET_IDENTITY_HELD",
    ):
        return dict(result, status="NO_CURRENT_FIRST_PAYER_SOURCE",
                    next_owner=owner["first_priority_owner"],
                    next_action=owner["first_priority_action"])
    ref = owner["opaque_opportunity_ref"]
    if not isinstance(ref, str) or not ref.startswith("oppref_"):
        raise ValueError("owner's current source ref missing")
    result["opaque_opportunity_ref"] = ref
    if state == "FIRST_PAYER_MARKET_IDENTITY_HELD":
        return dict(result, status="MARKET_IDENTITY_REQUIRED",
                    next_owner="market_intelligence",
                    next_action="VERIFY_SOURCE_MARKET_NICHE_BEFORE_BUYER_MATCH")
    if tenant_id is None:
        return dict(result, status="SCOPED_SOURCE_IDENTITY_REQUIRED",
                    next_owner="existing_buyer_crm_owner",
                    next_action="SUPPLY_EXACT_TENANT_AND_OPPORTUNITY_SOURCE_KEY_READONLY")

    if (not isinstance(tenant_id, str) or not tenant_id.strip()
            or len(tenant_id) > 128
            or not isinstance(opportunity_key, str)
            or not opportunity_key.strip() or len(opportunity_key) > 180):
        raise ValueError("invalid scoped original opportunity identity")
    derived = "oppref_" + sha256(opportunity_key.encode()).hexdigest()[:20]
    if ref != derived:
        return dict(result, status="SCOPED_OPPORTUNITY_IDENTITY_MISMATCH",
                    next_owner="existing_buyer_crm_owner",
                    next_action="RECHECK_SOURCE_IDENTITY_WITH_ORIGINAL_CRM_OWNER")

    # Re-read the current source and its independently selected owner item.
    # A matching hash is *not* by itself an authenticated tenant mapping.
    prepared = review_one_commercial_evidence_request(root, as_of=as_of)
    if (prepared.get("status") != "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED"
            or not isinstance(prepared.get("request"), Mapping)
            or prepared["request"].get("opportunity_ref") != ref
            or prepared["request"].get("source_pathway_fingerprint") !=
               owner["existing_source_fingerprint"]):
        return dict(result, status="SOURCE_REVISION_DRIFT",
                    next_owner="existing_opportunity_factory_owner",
                    next_action="RESELECT_CURRENT_FIRST_PAYER_SOURCE")
    request = prepared["request"]
    radar = _read(root, "radar")
    candidates = radar.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 250:
        raise ValueError("unbounded canonical radar source")
    matched = [
        row for row in candidates
        if isinstance(row, Mapping)
        and row.get("opportunity_key") == opportunity_key
    ]
    if len(matched) != 1:
        return dict(result, status="SOURCE_REVISION_DRIFT",
                    next_owner="existing_opportunity_factory_owner",
                    next_action="RESELECT_CURRENT_FIRST_PAYER_SOURCE")
    source = matched[0]
    if (market_identity_digest(source) != request.get("market_identity_digest")
            or source.get("niche") != owner["market_vertical"]
            or source.get("tenant_id") not in (None, tenant_id)):
        return dict(result, status="SOURCE_MARKET_OR_TENANT_MISMATCH",
                    next_owner="existing_buyer_crm_owner",
                    next_action="VERIFY_ORIGINAL_MARKET_AND_TENANT_SCOPE")

    result["original_source_identity_bound"] = True
    result["original_market_revision_bound"] = True
    result["source_market_checked_from_current_snapshot"] = True
    # The public Radar row has tenant_id=None: same key is NOT tenant auth.
    # Existing authenticated CRM owner alone may establish that separately.

    if want_quant:
        preview = review_first_payer_quant_preflight(
            tenant_id=tenant_id, opportunity_key=opportunity_key,
            model_name=model_name, model_version=model_version,
            quant_inputs=quant_inputs or {},
            source_receipts=source_receipts or {},
            assessed_at=as_of, horizon_days=horizon_days,
        )
        if (preview.get("execution_authority") != "none"
                or preview.get("source_refs_authenticated_by_this_review") is not False
                or preview.get("forecast_durably_registered") is not False
                or preview.get("database_writes") is not False):
            raise ValueError("original Quant preview overclaimed verification")
        result["quant_preflight_status"] = preview["status"]
        result["missing_quant_fields"] = list(preview["missing_quant_fields"])
        result["unsupported_source_fields"] = list(preview["unsupported_original_source_fields"])
        result["quant_preview_checked"] = True

    return dict(result, status="SAME_OPPORTUNITY_SCIENTIFIC_REVIEW_HELD",
                next_owner="existing_buyer_crm_owner",
                next_action="VERIFY_FIRST_PARTY_BUYER_TERMS_PRICE_TERRITORY_CAPACITY_AND_CUSTODY")
