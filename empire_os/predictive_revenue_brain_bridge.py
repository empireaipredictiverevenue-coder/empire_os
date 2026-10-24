"""OBSERVE-only composite brain bridge for existing EmpireOS Predictive Cloud.

Reuses canonical storm/permit projections and the Predictive Revenue JEV.
CRM deal rows are caller-provided, non-authoritative read projections.
This module has no network, DB, Redis, model-weight, execution, or financial writes.
It does not attest to the truth of caller-provided sources or probabilities.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
from typing import Any

from empire_os.permit_product_integration import PermitProductIntegration
from empire_os.predictive_revenue_jev import compile_predictive_revenue_jev
from empire_os.predictive_revenue_prime import (
    review_churn_signals,
    simulate_pipeline_scenarios,
)
from empire_os.predictive_revenue_prime_crm import review_authenticated_crm_prospects
from empire_os.predictive_cloud_official_source_bridge import review_official_source_for_prime
from empire_os.prime_original_outcome_calibration import review_prime_outcome_calibration
from empire_os.prime_universal_evidence_fusion import (
    review_prime_universal_evidence, summarize_prime_founder_evidence,
)
from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository

SCHEMA = "empire.predictive_revenue.brain_bridge.v1"
MAX_ITEMS = 100
MAX_CENTS = 9_000_000_000_000_000
STAGES = frozenset({
    "DISCOVERY", "QUALIFICATION", "PROPOSAL", "NEGOTIATION",
    "CLOSED_WON", "CLOSED_LOST",
})
CURRENCIES = frozenset({"GBP", "USD", "EUR", "USDT"})


def _stamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid source timestamp") from None
    else:
        raise ValueError("explicit source timestamp required")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone-aware source timestamp required")
    return parsed.astimezone(timezone.utc)


def _bounded_text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 192:
        raise ValueError(f"{field} required and bounded")
    return value.strip()


def _refs(values: Any) -> list[str]:
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError("source evidence refs required")
    refs = [_bounded_text(v, "evidence ref") for v in values]
    return list(dict.fromkeys(refs))


def _cents(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError("exact nonnegative integer cents required")
    return value


def _basis_points(value: Any) -> int:
    if type(value) is not int or not 0 <= value <= 10_000:
        raise ValueError("win probability must be integer basis points")
    return value


def _half_up(numerator: int, denominator: int) -> int:
    return int((Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP,
    ))


def _jev_research(
    *, tenant_id: str, source_id: str, kind: str, observed_at: str,
    truth_class: str, evidence_refs: list[str], opportunity_key: str,
    now: datetime,
) -> dict[str, Any]:
    # Deliberately withhold Quant probabilities/economics. JEV remains the
    # canonical reason/hold calculator; no fabricated buyer demand or revenue.
    packet = compile_predictive_revenue_jev(
        signal={
            "signal_id": source_id,
            "signal_type": kind,
            "observed_at": observed_at,
            "truth_class": truth_class,
            "evidence_refs": evidence_refs,
        },
        normalized_opportunity={
            "tenant_id": tenant_id,
            "opportunity_key": opportunity_key,
            "opportunity_class": kind,
            "probability_modeled_from_verified_outcomes": False,
        },
        as_of=now,
    )
    return {
        "signal_id": source_id,
        "opportunity_key": opportunity_key,
        "source_type": kind,
        "truth_class": truth_class,
        "evidence_refs": list(packet.evidence_refs),
        "freshness": packet.freshness,
        "recommendation": packet.output_type,
        "blockers": list(packet.blockers),
        "expected_revenue_cents": packet.expected_revenue_cents,
        "actual_revenue": packet.actual_revenue,
        "execution_authority": packet.execution_authority,
    }


def _storm_signals(
    snapshot: Mapping[str, Any] | None, *, tenant_id: str, now: datetime,
) -> list[dict[str, Any]]:
    if snapshot is None:
        return []
    if (not isinstance(snapshot, Mapping)
        or snapshot.get("schema_version") != "empire.storm_opportunity_snapshot.v1"
        or snapshot.get("mode") != "OBSERVE"
        or snapshot.get("execution_authority") != "none"
        or snapshot.get("automatic_external_execution_allowed") is not False):
        raise ValueError("canonical OBSERVE storm snapshot required")
    if _stamp(snapshot.get("generated_at")) > now:
        raise ValueError("future storm snapshot")
    candidates = snapshot.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_ITEMS:
        raise ValueError("bounded storm candidates required")
    reported_count = snapshot.get("candidate_count")
    if reported_count is not None and (type(reported_count) is not int or reported_count != len(candidates)):
        raise ValueError("storm snapshot candidate count mismatch")
    result = []
    keys = set()
    for row in candidates:
        if not isinstance(row, Mapping) or row.get("tenant_id") != tenant_id:
            raise ValueError("storm candidate tenant mismatch")
        for forbidden in ("commercial_ready", "revenue_inferred", "actual_revenue", "buyer_intent_inferred", "demand_inferred"):
            if row.get(forbidden) is True:
                raise ValueError("storm cannot assert commercial or revenue evidence")
        for authority in ("execution_authority", "outreach_authority", "commercial_authority", "payment_authority", "revenue_recognition_authority"):
            if row.get(authority) not in (None, "none"):
                raise ValueError("storm execution authority unsupported")
        key = _bounded_text(row.get("opportunity_key"), "storm key")
        if key in keys:
            raise ValueError("duplicate storm opportunity identity")
        keys.add(key)
        observed = _stamp(row.get("evaluated_at"))
        if observed > now:
            raise ValueError("future storm evaluation")
        truth = row.get("event_truth_class")
        if truth not in {"OBSERVED", "FORECAST"}:
            raise ValueError("storm source truth unknown")
        result.append(_jev_research(
            tenant_id=tenant_id,
            source_id=_bounded_text(row.get("event_id"), "storm event"),
            kind="storm_commercial_signal",
            observed_at=observed.isoformat(), truth_class=truth,
            evidence_refs=_refs(row.get("evidence_refs")),
            opportunity_key=key, now=now,
        ))
    return sorted(result, key=lambda r: r["opportunity_key"])


def _permit_signals(
    integration: PermitProductIntegration | None, *,
    tenant_id: str, now: datetime,
) -> list[dict[str, Any]]:
    if integration is None:
        return []
    if (not isinstance(integration, PermitProductIntegration)
        or integration.tenant_id != tenant_id
        or integration.mode != "OBSERVE"
        or integration.execution_authority != "none"
        or integration.actual_revenue is not False):
        raise ValueError("canonical OBSERVE permit integration required")
    if len(integration.opportunities) > MAX_ITEMS:
        raise ValueError("bounded permit observations required")
    result = []
    keys = set()
    for permit in integration.opportunities:
        source = _bounded_text(permit.source, "permit source")
        record = _bounded_text(permit.source_record_id, "permit record")
        identity = f"{tenant_id}|{source}|{record}"
        key = "permit:" + sha256(identity.encode("utf-8")).hexdigest()[:24]
        if key in keys:
            raise ValueError("duplicate permit identity")
        keys.add(key)
        observed = _stamp(permit.observed_at)
        if observed > now:
            raise ValueError("future permit observation")
        if permit.evidence_class != "OBSERVED":
            raise ValueError("permit source evidence class unsupported")
        result.append(_jev_research(
            tenant_id=tenant_id, source_id=key,
            kind="permit_project", observed_at=observed.isoformat(),
            truth_class="OBSERVED", evidence_refs=_refs(permit.evidence_refs),
            opportunity_key=key, now=now,
        ))
    return sorted(result, key=lambda r: r["opportunity_key"])


def _deal_projection(
    deals: Sequence[Mapping[str, Any]], *,
    tenant_id: str, now: datetime,
) -> dict[str, Any]:
    if not isinstance(deals, (list, tuple)) or len(deals) > MAX_ITEMS:
        raise ValueError("bounded CRM read projections required")
    seen: set[str] = set()
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for deal in deals:
        if not isinstance(deal, Mapping) or deal.get("tenant_id") != tenant_id:
            raise ValueError("CRM deal tenant mismatch")
        deal_id = _bounded_text(deal.get("deal_id"), "deal ID")
        if deal_id in seen:
            raise ValueError("duplicate CRM deal ID")
        seen.add(deal_id)
        if _stamp(deal.get("updated_at")) > now:
            raise ValueError("future CRM deal")
        stage = deal.get("stage")
        currency = deal.get("currency")
        if stage not in STAGES or currency not in CURRENCIES:
            raise ValueError("unsupported CRM stage or currency")
        value = _cents(deal.get("value_cents"))
        _refs(deal.get("evidence_refs"))
        bucket = totals[currency]
        bucket["deal_count"] += 1
        if stage == "CLOSED_WON":
            bucket["closed_won_contract_cents"] += value
            bucket["closed_won_count"] += 1
        elif stage == "CLOSED_LOST":
            bucket["closed_lost_count"] += 1
        else:
            bucket["open_pipeline_cents"] += value
            bucket["open_deal_count"] += 1
            probability = deal.get("win_probability_basis_points")
            refs = deal.get("probability_evidence_refs")
            cycle = deal.get("cycle_days")
            if probability is None:
                bucket["unknown_probability_count"] += 1
            else:
                p = _basis_points(probability)
                _refs(refs)
                expected = _half_up(value * p, 10_000)
                bucket["modeled_pipeline_cents"] += expected
                bucket["modeled_deal_count"] += 1
                if type(cycle) is not int or not 1 <= cycle <= 3650:
                    bucket["unknown_cycle_count"] += 1
                else:
                    bucket["modeled_daily_velocity_cents"] += _half_up(expected, cycle)
    result = []
    for currency in sorted(totals):
        values = totals[currency]
        open_count = values["open_deal_count"]
        complete_probability = values["unknown_probability_count"] == 0
        complete_cycle = complete_probability and values["unknown_cycle_count"] == 0
        result.append({
            "currency": currency,
            "deal_count": values["deal_count"],
            "open_deal_count": open_count,
            "open_pipeline_cents": values["open_pipeline_cents"],
            "closed_won_count": values["closed_won_count"],
            "closed_won_contract_cents": values["closed_won_contract_cents"],
            "closed_lost_count": values["closed_lost_count"],
            "modeled_deal_count": values["modeled_deal_count"],
            "unknown_probability_count": values["unknown_probability_count"],
            "unknown_cycle_count": values["unknown_cycle_count"],
            "modeled_open_pipeline_cents": (
                values["modeled_pipeline_cents"] if complete_probability and open_count else None
            ),
            "modeled_daily_velocity_cents": (
                values["modeled_daily_velocity_cents"] if complete_cycle and open_count else None
            ),
            "model_inputs_independently_verified": False,
            "recognized_revenue_cents": None,
            "paid_cash_cents": None,
            "mrr_cents": None,
            "quarterly_run_rate_cents": None,
            "churn_probability": None,
            "p90_forecast_cents": None,
        })
    return {
        "schema_version": "empire.predictive_revenue.crm_pipeline_projection.v1",
        "currency_groups": result,
        "source_rows": len(seen),
        "CRM_is_not_payment_or_accounting_authority": True,
        "probabilities_are_caller_supplied_projections": True,
        "mode": "OBSERVE", "execution_authority": "none",
    }


def build_predictive_revenue_brain_review(
    *, tenant_id: str, as_of: datetime,
    storm_snapshot: Mapping[str, Any] | None = None,
    permit_integration: PermitProductIntegration | None = None,
    crm_deals: Sequence[Mapping[str, Any]] = (),
    churn_signals: Sequence[Mapping[str, Any]] = (),
    simulate_pipeline: bool = False,
    simulations: int = 10000,
    simulation_seed: int = 101,
    authenticated_crm_repository: PostgresRevenueCrmRepository | None = None,
    official_nws_source_review: Mapping[str, Any] | None = None,
    original_owner_calibration_rows: Sequence[Mapping[str, Any]] | None = None,
    original_owner_evidence_summaries: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compose existing evidence without inventing forecasts, agents or authority.

    The authentic feed readers/owner are responsible for access control and
    source certification; this pure review cannot attest to either.
    """
    tenant = _bounded_text(tenant_id, "tenant ID")
    now = _stamp(as_of)
    official_source = review_official_source_for_prime(
        nws_review=official_nws_source_review, as_of=now,
    )
    original_outcome_calibration = review_prime_outcome_calibration(
        owner_outcome_rows=original_owner_calibration_rows,
        tenant_id=tenant, as_of=now,
    )
    original_universal_evidence = review_prime_universal_evidence(
        tenant_id=tenant, as_of=now,
        original_owner_summaries=original_owner_evidence_summaries,
    )
    storms = _storm_signals(storm_snapshot, tenant_id=tenant, now=now)
    permits = _permit_signals(permit_integration, tenant_id=tenant, now=now)
    if authenticated_crm_repository is not None and crm_deals:
        raise ValueError("do not mix CRM prospect view and hypothetical deal inputs")
    authenticated_crm = (
        review_authenticated_crm_prospects(
            repository=authenticated_crm_repository, tenant_id=tenant,
        ) if authenticated_crm_repository is not None else None
    )
    pipeline = _deal_projection(crm_deals, tenant_id=tenant, now=now)
    if type(simulate_pipeline) is not bool:
        raise ValueError("explicit simulation toggle must be boolean")
    open_deals = [deal for deal in crm_deals if deal["stage"] not in {"CLOSED_WON", "CLOSED_LOST"}]
    scenario = (
        simulate_pipeline_scenarios(
            tenant_id=tenant, as_of=now, open_deals=open_deals,
            simulations=simulations, seed=simulation_seed,
        ) if simulate_pipeline and open_deals else None
    )
    retention = review_churn_signals(
        tenant_id=tenant, as_of=now, signals=churn_signals,
    )
    storm_freshness = "NOT_CONNECTED"
    if storm_snapshot is not None:
        hours_since = (now - _stamp(storm_snapshot["generated_at"])).total_seconds() / 3600
        storm_freshness = "STALE" if hours_since > 24 else "RECENT_SNAPSHOT_UNVERIFIED"
    return {
        "schema_version": SCHEMA,
        "tenant_id": tenant,
        "as_of": now.isoformat(),
        "mode": "OBSERVE",
        "storm_research": storms,
        "permit_research": permits,
        "official_source_observatory": official_source,
        "original_outcome_calibration_shadow": original_outcome_calibration,
        "prime_universal_evidence_shadow": summarize_prime_founder_evidence(
            original_universal_evidence,
        ),
        "crm_pipeline": pipeline,
        "authenticated_crm_prospect_review": authenticated_crm,
        "source_freshness": {
            "storm_snapshot": storm_freshness,
            "official_nws": official_source["freshness"],
            "permit_sources": (
                "PUBLIC_SOURCE_PROJECTIONS_UNVERIFIED_BUYER_DEMAND"
                if permit_integration is not None else "NOT_CONNECTED"
            ),
            "crm_source": (
                "AUTHENTICATED_TENANT_CRM_VIEW_NOT_DEALS"
                if authenticated_crm is not None
                else "CALLER_PROJECTION_NOT_INDEPENDENTLY_CONNECTED"
            ),
        },
        "prime_scenarios": scenario,
        "prime_churn_review": retention,
        "prime_scenarios_are_hypotheses_only": True,
        "prime_calibration_never_promotes_model_weights": True,
        "prime_interventions_executed": False,
        "opportunity_count": len(storms) + len(permits),
        "official_source_records_are_not_opportunities": True,
        "scientist_agent_task": "review_evidence_and_hypotheses",
        "reflector_agent_task": "await_eligible_forecast_actual_calibration",
        "astra_dispatch_executed": False,
        "forecast_model_promoted": False,
        "canonical_store": "EmpireDB (unchanged)",
        "crm_mutation": False,
        "database_writes": False,
        "outbound_sent": False,
        "payment_executed": False,
        "recognized_revenue_cents": None,
        "revenue_verified": False,
        "execution_authority": "none",
        "authority_upgrade_available": False,
        "blockers": [
            "independent_source_custody_and_tenant_access_required",
            "verified_commercial_outcomes_required_for_calibration",
            "independent_payment_and_accounting_evidence_required_for_revenue",
        ],
    }
