"""Property Intelligence product/runtime integration foundation.

Architecture delta (2026-10-02): canonical EmpireDB property observations ->
validated evidence -> inferred opportunities -> review-only product readiness.
Owner: Property Intelligence / market intelligence; Control Fabric: OBSERVE.
Astra/Founder consumers may inspect this projection; Needle may route review,
never execution. The existing aggregate runtime cannot identify opportunities.

Contract: callers supply tenant-scoped EmpireDB projections, not raw regional
weather counts or invented identities. Observations require source provenance,
a timezone-aware timestamp and a canonical property_id. Commercial assertions
require VERIFIED evidence bound to the same tenant, product and buyer. Evidence
references are provenance pointers, not independently authenticated here; callers
must obtain them through trusted canonical readers, never public request bodies.
Outputs distinguish OBSERVED inputs, INFERRED priority, FORECAST margin and
verified commercial evidence. No persistence, I/O, retries or background work;
synchronous deterministic deduplication, no shared mutable ownership. Missing or
conflicting evidence fails closed with explicit blockers. No outbound, terms,
fund movement, revenue recognition, production mutation or authority expansion.
Rollback: remove this additive adapter. Focused tests verify failure/recovery and
authority invariants; deployment, canonical/live verification and Founder wiring
remain separate promotion gates. Builder: Codex; verifier: focused tests.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

PRODUCT_CODE = "property_intelligence"
PRODUCT_KEY = "property_intelligence_monitor"
SIGNALS = frozenset({"permit", "physical_condition", "climate_exposure",
                     "transaction", "development", "expansion"})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        return parsed if parsed.utcoffset() is not None else None
    except ValueError:
        return None


def build_property_product_integration(
    *,
    tenant_id: str,
    observations: Iterable[Mapping[str, Any]] = (),
    commercial_evidence: Mapping[str, Any] | None = None,
    buyer_id: str | None = None,
) -> dict[str, Any]:
    """Project trusted evidence; absent evidence is UNKNOWN, never zero revenue.

    Observation schema: tenant_id, property_id, signal_type, evidence_ref,
    source, observed_at, truth_class (OBSERVED), data_backend (empiredb).
    Commercial schema: matching scope plus facts keyed below, each containing
    state=VERIFIED, evidence_ref and value. Money facts additionally require
    identical currency and unit (e.g. USD / per_month); values are integer cents.
    Conflicting duplicate evidence references invalidate every affected record.
    """
    tenant_id = _text(tenant_id)
    if not tenant_id:
        raise ValueError("tenant_id required")
    rejected: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    for index, row in enumerate(observations):
        if not isinstance(row, Mapping):
            rejected.append({"index": index, "reason": "invalid_observation"})
            continue
        reason = None
        if row.get("tenant_id") != tenant_id:
            reason = "tenant_mismatch"
        elif row.get("data_backend") != "empiredb":
            reason = "canonical_evidence_required"
        elif row.get("truth_class") != "OBSERVED":
            reason = "observed_evidence_required"
        elif row.get("signal_type") not in SIGNALS:
            reason = "unsupported_signal"
        elif not all(_text(row.get(key)) for key in
                     ("property_id", "source", "evidence_ref")):
            reason = "identity_or_provenance_missing"
        elif _timestamp(row.get("observed_at")) is None:
            reason = "timezone_aware_observation_required"
        if reason:
            rejected.append({"index": index, "reason": reason})
            continue
        normalized = {key: _text(row.get(key)) for key in
                      ("property_id", "signal_type", "source", "evidence_ref",
                       "observed_at")}
        ref = normalized["evidence_ref"]
        if ref in candidates and candidates[ref] != normalized:
            conflicts.add(ref)
        candidates[ref] = normalized
    for ref in sorted(conflicts):
        candidates.pop(ref)
        rejected.append({"evidence_ref": ref, "reason": "conflicting_evidence"})

    grouped: dict[str, list[dict[str, Any]]] = {}
    for ref in sorted(candidates):
        row = candidates[ref]
        grouped.setdefault(row["property_id"], []).append(row)
    opportunities = []
    for property_id, rows in grouped.items():
        signals = sorted({row["signal_type"] for row in rows})
        opportunities.append({
            "property_id": property_id,
            "truth_class": "INFERRED",
            "signal_types": signals,
            "evidence": rows,
            "evidence_refs": [row["evidence_ref"] for row in rows],
            "latest_observed_at": max(rows, key=lambda r: _timestamp(r["observed_at"]))["observed_at"],
            "priority_basis": "signal_diversity_then_recency",
            "signal_diversity": len(signals),
            "buyer_intent": "UNKNOWN",
            "asset_damage": "UNKNOWN",
        })
    opportunities.sort(key=lambda row: (
        -row["signal_diversity"],
        -_timestamp(row["latest_observed_at"]).timestamp(), row["property_id"],
    ))
    for rank, opportunity in enumerate(opportunities, 1):
        opportunity["priority_rank"] = rank

    commercial = commercial_evidence or {}
    scope_valid = (
        commercial.get("tenant_id") == tenant_id
        and commercial.get("data_backend") == "empiredb"
        and commercial.get("product_code") == PRODUCT_CODE
        and bool(_text(buyer_id)) and commercial.get("buyer_id") == buyer_id
    )

    def fact(name: str) -> Mapping[str, Any]:
        value = commercial.get(name)
        if (scope_valid and isinstance(value, Mapping)
                and value.get("state") == "VERIFIED"
                and _text(value.get("evidence_ref"))):
            return value
        return {}

    money_names = ("price_cents", "acquisition_cost_cents", "fulfilment_cost_cents")
    money = {name: fact(name) for name in money_names}
    economics_blockers = []
    for name, item in money.items():
        value = item.get("value")
        if (type(value) is not int or value < 0
                or (name == "price_cents" and value == 0)
                or not _text(item.get("currency")) or not _text(item.get("unit"))):
            economics_blockers.append(f"{name}_unknown")
    if not economics_blockers and len({(item["currency"], item["unit"])
                                       for item in money.values()}) != 1:
        economics_blockers.append("incompatible_economic_basis")
    margin = None
    if not economics_blockers:
        margin = (money["price_cents"]["value"]
                  - money["acquisition_cost_cents"]["value"]
                  - money["fulfilment_cost_cents"]["value"])
        if margin <= 0:
            economics_blockers.append("positive_expected_margin_required")

    offer_names = ("catalog_approved", "buyer_conversation", "capacity_confirmed",
                   "delivery_confirmed", "terms_approved")
    proof_names = ("terms_accepted", "delivery_accepted", "payment_settled",
                   "revenue_recognized")
    states = {name: ("VERIFIED" if fact(name).get("value") is True else "UNKNOWN")
              for name in (*offer_names, *proof_names)}
    offer_blockers = list(economics_blockers)
    if not opportunities:
        offer_blockers.append("property_opportunity_evidence_missing")
    offer_blockers.extend(f"{name}_unknown" for name in offer_names
                          if states[name] == "UNKNOWN")
    proof_blockers = list(offer_blockers)
    proof_blockers.extend(f"{name}_unknown" for name in proof_names
                          if states[name] == "UNKNOWN")
    return {
        "schema_version": "empire.property-product-integration.v1",
        "tenant_id": tenant_id, "buyer_id": buyer_id,
        "product_key": PRODUCT_KEY, "product_code": PRODUCT_CODE,
        "mode": "OBSERVE", "execution_authority": "none",
        "opportunities": opportunities,
        "opportunity_count": len(opportunities),
        "evidence_state": "EVIDENCE_AVAILABLE" if opportunities else "UNKNOWN",
        "rejected_observations": rejected,
        "economics": {
            "state": "READY_FOR_REVIEW" if not economics_blockers else (
                "BLOCKED" if margin is not None else "UNKNOWN"),
            "truth_class": "FORECAST", "expected_margin_cents": margin,
            "currency": money["price_cents"].get("currency") if margin is not None else None,
            "unit": money["price_cents"].get("unit") if margin is not None else None,
            "evidence_refs": sorted({item["evidence_ref"] for item in money.values() if item}),
            "blockers": economics_blockers,
        },
        "commercial_offer": {
            "state": "READY_FOR_REVIEW" if not offer_blockers else "UNKNOWN",
            "binding": False, "blockers": offer_blockers,
        },
        "commercial_evidence_states": states,
        "commercial_evidence_refs": sorted({fact(name)["evidence_ref"]
                                             for name, state in states.items()
                                             if state == "VERIFIED"}),
        "paid_proof": {
            "state": "VERIFIED_EVIDENCE" if not proof_blockers else "UNKNOWN",
            "blockers": proof_blockers,
        },
        "revenue_recognition_performed": False,
        "outbound_performed": False, "production_mutation_performed": False,
    }
