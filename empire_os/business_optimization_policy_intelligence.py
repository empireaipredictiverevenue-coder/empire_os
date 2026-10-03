"""Evidence-driven policy intelligence for Empire Business Optimization.

This layer continuously evaluates whether each optimization domain has enough
real governance, source, objective and constraint evidence to become active.
It never invents limits or economics. It writes proposals/readiness evidence,
and may preserve an already-approved policy, but it cannot grant business
execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from empire_os.business_optimization_product import WORKLOAD_SPECS


SCHEMA_VERSION = "empire.business_optimization.policy-intelligence.v1"
OUTPUT = Path(
    "runtime/business_optimization/policy_intelligence_latest.json"
)
PROPOSALS = Path("runtime/business_optimization/policy_proposals")
POLICIES = Path("runtime/business_optimization/policies")
SOURCE_INPUTS = Path("runtime/business_optimization/source_inputs")

PRICING = Path(
    "runtime/commercial_catalog/pricing_verification_latest.json"
)
EXCHANGE = Path("runtime/commercial_exchange/latest.json")
BUDGET = Path("runtime/departments/budget/latest.json")
VALUE = Path("runtime/opportunity_factory/value_latest.json")
RADAR = Path("runtime/opportunity_radar/latest.json")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _ref(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return f"{path.as_posix()}#sha256={sha256(data).hexdigest()}"


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _active_policy(root: Path, workload: str) -> dict[str, Any] | None:
    packet = _read_json(root / POLICIES / f"{workload}.json")
    if not packet:
        return None
    if _text(packet.get("status")).upper() not in {"APPROVED", "ACTIVE"}:
        return None
    if not packet.get("evidence_refs"):
        return None
    if packet.get("time_budget_ms") is None:
        return None
    return packet


def _source_input(root: Path, workload: str) -> dict[str, Any] | None:
    packet = _read_json(root / SOURCE_INPUTS / f"{workload}.json")
    if not packet:
        return None
    if _text(packet.get("status")).upper() != "AVAILABLE":
        return None
    options = [
        row for row in (packet.get("options") or ())
        if isinstance(row, Mapping)
    ]
    if not options:
        return None
    return packet


def _opportunity_economics(root: Path) -> dict[str, Any]:
    value_path = root / VALUE
    radar_path = root / RADAR
    value = _read_json(value_path) or {}
    radar = _read_json(radar_path) or {}
    available = [
        row for row in (value.get("items") or ())
        if isinstance(row, Mapping)
        and _text(row.get("status")).upper() == "AVAILABLE"
        and row.get("expected_gross_profit_cents") is not None
        and isinstance(row.get("quant_input_evidence"), Mapping)
        and bool(row.get("quant_input_evidence", {}).get("evidence_refs"))
    ]
    factory_ready = [
        row for row in (radar.get("candidates") or ())
        if isinstance(row, Mapping)
        and row.get("opportunity_factory_ready") is True
    ]
    refs = [
        ref for ref in (_ref(value_path), _ref(radar_path)) if ref
    ]
    return {
        "economic_candidate_count": len(available),
        "factory_ready_count": len(factory_ready),
        "evidence_refs": refs,
    }


def _classify(
    root: Path,
    workload: str,
    *,
    pricing: Mapping[str, Any],
    exchange: Mapping[str, Any],
    budget: Mapping[str, Any],
    opportunity: Mapping[str, Any],
) -> dict[str, Any]:
    spec = WORKLOAD_SPECS[workload]
    active = _active_policy(root, workload)
    source = _source_input(root, workload)
    blockers: list[str] = []
    evidence_refs: set[str] = set()
    observations: dict[str, Any] = {}

    if active is not None:
        evidence_refs.update(
            _text(value)
            for value in (active.get("evidence_refs") or ())
            if _text(value)
        )
        return {
            "workload_type": workload,
            "title": spec["title"],
            "state": "ACTIVE_POLICY",
            "policy_active": True,
            "auto_activation_safe": False,
            "blockers": [],
            "observations": {
                "active_policy_status": active.get("status"),
            },
            "evidence_refs": sorted(evidence_refs),
            "execution_authority": "none",
        }

    if source is not None:
        source_path = root / SOURCE_INPUTS / f"{workload}.json"
        source_ref = _ref(source_path)
        if source_ref:
            evidence_refs.add(source_ref)
        evidence_refs.update(
            _text(value)
            for value in (source.get("evidence_refs") or ())
            if _text(value)
        )
        observations["canonical_source_option_count"] = len(
            source.get("options") or ()
        )

    if workload == "pricing":
        pricing_path = root / PRICING
        pricing_ref = _ref(pricing_path)
        if pricing_ref:
            evidence_refs.add(pricing_ref)
        approved = bool(
            pricing.get("pricing_matches_approved_policy") is True
            and _text(pricing.get("approval_reference"))
        )
        observations.update({
            "approved_price_ladder_verified": approved,
            "approval_reference": pricing.get("approval_reference"),
            "verified_price_row_count": len(pricing.get("checks") or ()),
        })
        if not approved:
            blockers.append("approved_pricing_policy_evidence_required")
        blockers.append(
            "alternative_price_scenario_demand_and_conversion_economics_required"
        )

    elif workload in {"buyer_allocation", "lead_allocation"}:
        exchange_path = root / EXCHANGE
        exchange_ref = _ref(exchange_path)
        if exchange_ref:
            evidence_refs.add(exchange_ref)
        market_prices = int(
            exchange.get("verified_market_price_count") or 0
        )
        candidates = int(exchange.get("allocation_candidate_count") or 0)
        observations.update({
            "buyer_seat_count": int(exchange.get("buyer_seat_count") or 0),
            "verified_market_price_count": market_prices,
            "allocation_candidate_count": candidates,
        })
        if market_prices <= 0:
            blockers.append("verified_market_price_evidence_required")
        if candidates <= 0:
            blockers.append("eligible_allocation_candidates_required")
        if source is None:
            blockers.append("canonical_assignment_source_required")

    elif workload in {"capital_allocation", "marketing_budgets"}:
        budget_path = root / BUDGET
        budget_ref = _ref(budget_path)
        if budget_ref:
            evidence_refs.add(budget_ref)
        configured = budget.get("policy_configured") is True
        observations.update({
            "department_budget_policy_configured": configured,
            "cash_spend_authority": budget.get("cash_spend_authority"),
            "budget_override_authority": budget.get(
                "budget_override_authority"
            ),
        })
        if not configured:
            blockers.append("explicit_budget_limit_policy_required")
        if source is None:
            blockers.append("evidence_backed_choice_source_required")

    elif workload in {"portfolio_strategy", "market_expansion"}:
        evidence_refs.update(opportunity.get("evidence_refs") or ())
        economics = int(
            opportunity.get("economic_candidate_count") or 0
        )
        factory_ready = int(
            opportunity.get("factory_ready_count") or 0
        )
        observations.update({
            "economic_candidate_count": economics,
            "opportunity_factory_ready_count": factory_ready,
        })
        if economics <= 0:
            blockers.append(
                "normalized_opportunity_economics_required"
            )
        if workload == "market_expansion" and factory_ready <= 0:
            blockers.append("market_identity_and_factory_readiness_required")
        blockers.append("explicit_portfolio_resource_limits_required")

    else:
        if source is None:
            blockers.append("canonical_domain_source_required")
        observations["primary_resources"] = list(
            spec.get("primary_resources") or ()
        )
        if spec.get("primary_resources"):
            blockers.append("explicit_resource_capacity_limits_required")

    blockers = sorted(set(blockers))
    if not blockers:
        state = "READY_FOR_POLICY_MATERIALIZATION"
        auto_safe = True
    elif evidence_refs or observations:
        state = "EVIDENCE_PARTIAL"
        auto_safe = False
    else:
        state = "BLOCKED_NO_EVIDENCE"
        auto_safe = False

    return {
        "workload_type": workload,
        "title": spec["title"],
        "state": state,
        "policy_active": False,
        "auto_activation_safe": auto_safe,
        "blockers": blockers,
        "observations": observations,
        "evidence_refs": sorted(
            value for value in evidence_refs if value
        ),
        "unknown_is_zero": False,
        "automatic_business_action_allowed": False,
        "execution_authority": "none",
    }


def refresh_business_optimization_policy_intelligence(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Refresh all 12 domains in one bounded local pass."""
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    pricing = _read_json(root / PRICING) or {}
    exchange = _read_json(root / EXCHANGE) or {}
    budget = _read_json(root / BUDGET) or {}
    opportunity = _opportunity_economics(root)

    rows: dict[str, dict[str, Any]] = {}
    for workload in sorted(WORKLOAD_SPECS):
        row = _classify(
            root,
            workload,
            pricing=pricing,
            exchange=exchange,
            budget=budget,
            opportunity=opportunity,
        )
        proposal = {
            "schema_version": (
                "empire.business_optimization.policy-proposal.v1"
            ),
            "generated_at": current.isoformat(),
            **row,
            "proposal_only": True,
            "policy_written_active": False,
            "third_party_service_called": False,
        }
        _atomic_write(
            root / PROPOSALS / f"{workload}.json",
            proposal,
        )
        rows[workload] = row

    active_count = sum(
        row["state"] == "ACTIVE_POLICY" for row in rows.values()
    )
    ready_count = sum(
        row["state"] == "READY_FOR_POLICY_MATERIALIZATION"
        for row in rows.values()
    )
    partial_count = sum(
        row["state"] == "EVIDENCE_PARTIAL"
        for row in rows.values()
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "workload_count": len(rows),
        "active_policy_count": active_count,
        "ready_for_policy_materialization_count": ready_count,
        "partial_evidence_count": partial_count,
        "blocked_count": len(rows) - active_count - ready_count,
        "workloads": rows,
        "batch_refresh": True,
        "manual_domain_by_domain_scan_required": False,
        "synthetic_constraints_generated": False,
        "synthetic_economics_generated": False,
        "automatic_business_action_allowed": False,
        "third_party_service_called": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload


def run_business_optimization_policy_intelligence(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compatibility/runtime entrypoint used by the department heartbeat."""
    payload = refresh_business_optimization_policy_intelligence(
        repo_root,
        now=now,
    )
    return {
        **payload,
        "auto_activated_policy_count": int(
            payload.get("active_policy_count") or 0
        ),
        "held_workload_count": int(
            payload.get("blocked_count") or 0
        ),
    }
