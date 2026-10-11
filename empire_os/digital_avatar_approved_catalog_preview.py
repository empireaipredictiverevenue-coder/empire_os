"""Dry-run only Digital Avatar approved-price candidate for existing EmpireDB RPCs.

Reuses the founder-approved V1 proposal/policy and existing commercial package
definitions. NEVER calls a database, proposes a live version or enables a sale.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping
from pathlib import Path

from empire_os.digital_avatar_pricing_economics_proposal import (
    DIGITAL_AVATAR_PRICING_PROPOSALS,
    MINIMUM_MARGIN_BPS,
    TARGET_POLICY_MARGIN_BPS,
)
from empire_os.digital_avatar_commercial_packaging import (
    get_avatar_commercial_package,
)

SCHEMA = "empire.digital-avatar-approved-price-catalog-preview.v1"
APPROVAL_REF = "founder_approval:2026-10-02:digital_avatar_pricing_v1"
APPROVAL_SOURCE = "founder_chat_decision:2026-10-02T22:29:17Z"
APPROVAL_DOC = "docs/commercial/DIGITAL_AVATAR_PRICING_V1_FOUNDER_DECISION_20261011.md"
PRICE_PROPOSAL_DOC = "docs/DIGITAL_AVATAR_PRICING_ECONOMICS_PROPOSAL_V1.md"
CATALOG_SCHEMA = "empire.commercial-product-catalog.v1"
MAX_CATALOG_AGE = timedelta(hours=24)

# Enterprise is a quote-led policy floor, not a fourth activated catalog SKU.
ENTERPRISE_RECURRING_FLOOR_CENTS = 1_500_000


class CatalogStagingHold(ValueError):
    """Invalid approval, conflicting catalog or stale underlying evidence."""


def _utc(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 48:
        raise CatalogStagingHold("catalog_generated_at_invalid")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogStagingHold("catalog_generated_at_invalid") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise CatalogStagingHold("catalog_generated_at_naive")
    return dt.astimezone(timezone.utc)


def build_approved_avatar_catalog_preview(
    catalog: Mapping[str, Any],
    *,
    approval_reference: str = APPROVAL_REF,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Three proposed identity/version RPC *payloads*; zero invocation authority."""
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None or clock.utcoffset() is None:
        raise CatalogStagingHold("approval_preview_clock_must_be_aware")
    clock = clock.astimezone(timezone.utc)
    if approval_reference != APPROVAL_REF:
        raise CatalogStagingHold("exact_existing_founder_decision_reference_required")
    if not isinstance(catalog, Mapping):
        raise CatalogStagingHold("canonical_catalog_snapshot_required")
    if (catalog.get("schema_version") != CATALOG_SCHEMA
            or catalog.get("execution_authority") != "none"
            or catalog.get("actual_revenue") is not False):
        raise CatalogStagingHold("catalog_source_authority_or_schema_invalid")
    source_at = _utc(catalog.get("generated_at"))
    age = clock - source_at
    if age < -timedelta(minutes=2) or age > MAX_CATALOG_AGE:
        raise CatalogStagingHold("canonical_catalog_stale_or_future")
    products = catalog.get("products")
    if not isinstance(products, list) or len(products) > 500:
        raise CatalogStagingHold("canonical_catalog_unbounded")
    if type(catalog.get("product_count")) is not int or catalog["product_count"] != len(products):
        raise CatalogStagingHold("canonical_catalog_count_mismatch")
    if any(not isinstance(p, Mapping) or not isinstance(p.get("product_code"), str)
           for p in products):
        raise CatalogStagingHold("canonical_catalog_product_identity_invalid")
    existing = [p["product_code"] for p in products]
    if len(existing) != len(set(existing)):
        raise CatalogStagingHold("canonical_catalog_duplicate_products")
    policies = DIGITAL_AVATAR_PRICING_PROPOSALS
    if len(policies) != 3:
        raise CatalogStagingHold("exactly_three_approved_packages_required")
    target_codes = [p.product_code for p in policies]
    if len(set(target_codes)) != 3:
        raise CatalogStagingHold("duplicate_approved_package_codes")
    if any(code in existing for code in target_codes):
        raise CatalogStagingHold("existing_avatar_catalog_identity_requires_manual_reconciliation")

    prepared: list[dict[str, Any]] = []
    for policy in policies:
        spec = get_avatar_commercial_package(policy.package_key)
        if spec.product_code != policy.product_code:
            raise CatalogStagingHold("approved_package_identity_mismatch")
        approved = policy.as_founder_approved_price_candidate(approval_reference)
        if (approved["price_basis"]["state"] != "VERIFIED"
                or approved["price_basis"]["source_type"] != "founder_approved"
                or approved["acquisition_cost_basis"]["state"] != "PROPOSED"
                or approved["fulfilment_cost_basis"]["state"] != "PROPOSED"
                or approved["margin_policy"]["state"] != "PROPOSED"
                or approved["binding"] is not False
                or approved["catalog_mutation_authorized"] is not False
                or approved["checkout_authorized"] is not False
                or approved["payment_authority"] != "none"):
            raise CatalogStagingHold("candidate_exceeds_price_only_approval")
        if policy.policy_margin_bps != TARGET_POLICY_MARGIN_BPS or policy.minimum_margin_bps != MINIMUM_MARGIN_BPS:
            raise CatalogStagingHold("margin_policy_proposal_mismatch")

        configuration = {
            "approved_price_policy_ref": approval_reference,
            "implementation_fee_cents": policy.implementation_fee_cents,
            "included_active_avatars": policy.included_active_avatars,
            "included_verified_meetings_per_month": policy.included_verified_meetings_per_month,
            "proposed_concurrency_entitlement": policy.proposed_concurrency_entitlement,
            "overage_per_verified_meeting_cents": policy.overage_per_verified_meeting_cents,
            "entitlements_verified": False,
            "settlement_target": "USDT_BSC",
            "runtime_capacity_verified": False,
            "binding_terms_ready": False,
            "policy_cost_ceiling_not_observed": True,
            "allowed_meeting_modes": list(spec.allowed_meeting_modes),
            "white_label_supported": spec.supports_white_label,
        }
        identity_payload = {
            "p_product_code": policy.product_code,
            "p_product_name": spec.product_name,
            "p_product_family": "digital_avatar",
            "p_billing_model": "monthly_subscription",
            "p_configuration": configuration,
            "p_provenance": {
                "source": "digital_avatar_approved_price_policy",
                "approval_reference": approval_reference,
                "founder_decision_date": "2026-10-02",
                "approval_scope": "PRICE_POLICY_ONLY",
                "actual_revenue": False,
            },
            "p_actor": "founder-approved-avatar-catalog-proposer",
        }
        version_payload = {
            "p_product_code": policy.product_code,
            "p_billing_model": "monthly_subscription",
            "p_currency": "USD",
            "p_price_basis": {
                "state": "VERIFIED",
                "source_type": "founder_approved",
                "amount_cents": policy.monthly_price_cents,
                "currency": "USD",
                "unit": "per_month",
                "approval_reference": approval_reference,
                "observed_historical_transaction_price": False,
            },
            "p_acquisition_cost_basis": {
                "state": "UNKNOWN",
                "observed_cost_claim": False,
            },
            "p_fulfilment_cost_basis": {
                "state": "UNKNOWN",
                "observed_cost_claim": False,
            },
            "p_margin_policy": {
                "state": "UNKNOWN",
                "policy_target_margin_bps": TARGET_POLICY_MARGIN_BPS,
                "policy_minimum_margin_bps": MINIMUM_MARGIN_BPS,
                "observed_actual": False,
            },
            "p_provenance": {
                "source": "digital_avatar_approved_price_policy",
                "approval_reference": approval_reference,
                "approval_scope": "PRICE_POLICY_ONLY",
                "pricing_candidate_not_verified_catalog": True,
                "binding_terms_ready": False,
                "runtime_costs_unverified": True,
                "runtime_capacity_unverified": True,
                "actual_revenue": False,
            },
            "p_evidence_refs": [
                approval_reference,
                f"docs:{APPROVAL_DOC}",
                f"docs:{PRICE_PROPOSAL_DOC}",
            ],
            "p_effective_from": None,
            "p_effective_until": None,
            "p_actor": "founder-approved-avatar-catalog-proposer",
        }
        prepared.append({
            "package_key": policy.package_key,
            "product_code": policy.product_code,
            "founder_approved_price_basis": approved["price_basis"],
            "monthly_price_cents": policy.monthly_price_cents,
            "implementation_fee_cents": policy.implementation_fee_cents,
            "included_active_avatars": policy.included_active_avatars,
            "included_verified_meetings_per_month": policy.included_verified_meetings_per_month,
            "proposed_concurrency_entitlement": policy.proposed_concurrency_entitlement,
            "overage_per_verified_meeting_cents": policy.overage_per_verified_meeting_cents,
            "proposed_policy_margin_bps": policy.policy_margin_bps,
            "observed_actual_margin_verified": False,
            "canonical_product_identity_rpc_preview": {
                "method": "POST",
                "path": "/rest/v1/rpc/register_commercial_product_identity",
                "payload": identity_payload,
                "invoked": False,
            },
            "canonical_product_version_rpc_preview": {
                "method": "POST",
                "path": "/rest/v1/rpc/propose_commercial_product_version",
                "payload": version_payload,
                "invoked": False,
            },
            "catalog_state": "NOT_PROPOSED",
            "version_state": "NOT_PROPOSED",
            "binding_terms_ready": False,
            "sellable": False,
            "checkout_authorized": False,
            "execution_authority": "none",
        })

    return {
        "schema_version": SCHEMA,
        "status": "FOUNDER_PRICE_APPROVED_CATALOG_PREVIEW_READY",
        "mode": "DRY_RUN",
        "approval_reference": approval_reference,
        "approval_source": APPROVAL_SOURCE,
        "approval_scope": "PRICE_POLICY_ONLY",
        "generated_at": clock.isoformat(),
        "catalog_observed_at": source_at.isoformat(),
        "catalog_product_count_before": catalog["product_count"],
        "avatar_existing_product_count": 0,
        "candidate_count": len(prepared),
        "products": prepared,
        "enterprise_recurring_floor_cents": ENTERPRISE_RECURRING_FLOOR_CENTS,
        "enterprise_floor_is_quote_led_only": True,
        "target_margin_bps_is_policy_not_verified_actual": TARGET_POLICY_MARGIN_BPS,
        "minimum_margin_bps_is_policy_not_verified_actual": MINIMUM_MARGIN_BPS,
        "costs_verified": False,
        "capacity_verified": False,
        "meeting_duration_verified": False,
        "catalog_product_identity_created": False,
        "catalog_versions_proposed": False,
        "database_mutation": False,
        "binding_terms_ready": False,
        "checkout_authorized": False,
        "outbound_authorized": False,
        "payment_authority": "none",
        "actual_revenue": False,
        "execution_authority": "none",
    }



AVATAR_PRICING_APPROVAL_RECORD_PATH = (
    "runtime/commercial_proposals/digital_avatar_approved_price_v1.json"
)
AVATAR_PRICING_CHECKLIST_SECTION = (
    "Empire Digital Avatar commercial packaging / pricing proposal "
    "— founder decision pending"
)
AVATAR_PRICING_CHECKLIST_ITEM = (
    "FOUNDER APPROVAL REQUIRED: exact Digital Avatar pricing/economics ladder"
)


def has_recorded_price_only_founder_approval(repo_root: str | Path) -> bool:
    """Read a narrowly bounded existing price-only decision snapshot.

    This allows the task monitor to stop asking for a founder price decision
    already made. It NEVER certifies product version, cost, margin or sale.
    """
    path = Path(repo_root) / AVATAR_PRICING_APPROVAL_RECORD_PATH
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000:
            return False
        packet = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(packet, dict):
            return False
        required = {
            "schema_version": SCHEMA,
            "status": "FOUNDER_PRICE_APPROVED_CATALOG_PREVIEW_READY",
            "mode": "DRY_RUN",
            "approval_reference": APPROVAL_REF,
            "approval_source": APPROVAL_SOURCE,
            "approval_scope": "PRICE_POLICY_ONLY",
            "candidate_count": 3,
            "avatar_existing_product_count": 0,
            "enterprise_recurring_floor_cents": ENTERPRISE_RECURRING_FLOOR_CENTS,
            "costs_verified": False,
            "capacity_verified": False,
            "meeting_duration_verified": False,
            "database_mutation": False,
            "catalog_product_identity_created": False,
            "catalog_versions_proposed": False,
            "binding_terms_ready": False,
            "checkout_authorized": False,
            "outbound_authorized": False,
            "payment_authority": "none",
            "actual_revenue": False,
            "execution_authority": "none",
        }
        if any(type(packet.get(k)) is not type(v) or packet.get(k) != v
               for k, v in required.items()):
            return False
        candidates = packet.get("products")
        if not isinstance(candidates, list) or len(candidates) != 3:
            return False
        if [row.get("product_code") if isinstance(row, dict) else None
            for row in candidates] != [
                p.product_code for p in DIGITAL_AVATAR_PRICING_PROPOSALS
            ]:
            return False
        for row, policy in zip(candidates, DIGITAL_AVATAR_PRICING_PROPOSALS):
            price = row.get("founder_approved_price_basis")
            version = row.get("canonical_product_version_rpc_preview")
            identity = row.get("canonical_product_identity_rpc_preview")
            if not isinstance(price, dict) or not isinstance(version, dict) or not isinstance(identity, dict):
                return False
            proposed = version.get("payload")
            registered = identity.get("payload")
            if not isinstance(proposed, dict) or not isinstance(registered, dict):
                return False
            pprice = proposed.get("p_price_basis")
            pcost = proposed.get("p_acquisition_cost_basis")
            fcost = proposed.get("p_fulfilment_cost_basis")
            margin = proposed.get("p_margin_policy")
            if not all(isinstance(v, dict) for v in (pprice, pcost, fcost, margin)):
                return False
            numbers = (
                ("monthly_price_cents", policy.monthly_price_cents),
                ("implementation_fee_cents", policy.implementation_fee_cents),
                ("included_active_avatars", policy.included_active_avatars),
                ("included_verified_meetings_per_month", policy.included_verified_meetings_per_month),
                ("proposed_concurrency_entitlement", policy.proposed_concurrency_entitlement),
                ("overage_per_verified_meeting_cents", policy.overage_per_verified_meeting_cents),
            )
            if (any(type(row.get(field)) is not int or row[field] != value
                    for field, value in numbers)
                    or type(price.get("amount_cents")) is not int
                    or type(pprice.get("amount_cents")) is not int):
                return False
            if (row.get("monthly_price_cents") != policy.monthly_price_cents
                    or row.get("implementation_fee_cents") != policy.implementation_fee_cents
                    or row.get("included_active_avatars") != policy.included_active_avatars
                    or row.get("included_verified_meetings_per_month") != policy.included_verified_meetings_per_month
                    or row.get("proposed_concurrency_entitlement") != policy.proposed_concurrency_entitlement
                    or row.get("overage_per_verified_meeting_cents") != policy.overage_per_verified_meeting_cents
                    or price.get("amount_cents") != policy.monthly_price_cents
                    or price.get("state") != "VERIFIED"
                    or price.get("approval_reference") != APPROVAL_REF
                    or pprice.get("state") != "VERIFIED"
                    or pprice.get("amount_cents") != policy.monthly_price_cents
                    or pprice.get("approval_reference") != APPROVAL_REF
                    or pcost.get("state") != "UNKNOWN"
                    or fcost.get("state") != "UNKNOWN"
                    or margin.get("state") != "UNKNOWN"
                    or identity.get("invoked") is not False
                    or version.get("invoked") is not False
                    or registered.get("p_product_code") != policy.product_code
                    or proposed.get("p_product_code") != policy.product_code
                    or row.get("catalog_state") != "NOT_PROPOSED"
                    or row.get("version_state") != "NOT_PROPOSED"
                    or row.get("binding_terms_ready") is not False
                    or row.get("sellable") is not False
                    or row.get("checkout_authorized") is not False
                    or row.get("execution_authority") != "none"):
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False
