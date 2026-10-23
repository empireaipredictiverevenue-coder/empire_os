"""PRIME: deterministic, unpromoted scenario and churn REVIEW for Predictive Cloud.

No payments, outbound, ledger reads, database writes or model training.
Inputs are bounded caller-provided projections, not authenticated finance evidence.
P10/P50/P90 are empirical *scenario percentiles*, not calibrated confidence
intervals, cash-flow forecasts or accuracy guarantees.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from random import Random
from typing import Any

MAX_DEALS = 100
MIN_SIMULATIONS = 1000
MAX_SIMULATIONS = 20000
MAX_CENTS = 9_000_000_000_000_000
_ALLOWED_CURRENCIES = frozenset({"GBP", "USD", "EUR", "USDT"})
_ALLOWED_CHURN_SIGNALS = frozenset({
    "usage_decline", "renewal_due", "support_escalation",
    "cancel_intent_explicit", "invoice_status_change",
})


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 192:
        raise ValueError(f"{name} required, bounded string")
    return value.strip()


def _time(value: Any) -> datetime:
    if type(value) is str:
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("timestamp format invalid") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _refs(value: Any) -> tuple[str, ...]:
    if type(value) not in (tuple, list) or not value:
        raise ValueError("nonempty evidence refs required")
    return tuple(dict.fromkeys(_text(ref, "evidence ref") for ref in value))


def _validate_deals(
    deals: Sequence[Mapping[str, Any]], *, tenant_id: str, as_of: datetime,
) -> dict[str, list[tuple[int, int]]]:
    if type(deals) not in (tuple, list) or not 1 <= len(deals) <= MAX_DEALS:
        raise ValueError("bounded, nonempty, live CRM deal projection required")
    seen = set()
    groups: dict[str, list[tuple[int, int]]] = {}
    for deal in deals:
        if not isinstance(deal, Mapping) or deal.get("tenant_id") != tenant_id:
            raise ValueError("simulation tenant mismatch")
        deal_id = _text(deal.get("deal_id"), "deal ID")
        if deal_id in seen:
            raise ValueError("duplicate deal ID")
        seen.add(deal_id)
        if _time(deal.get("updated_at")) > as_of:
            raise ValueError("future deal evidence")
        if deal.get("stage") not in {
            "DISCOVERY", "QUALIFICATION", "PROPOSAL", "NEGOTIATION"
        }:
            raise ValueError("scenario input must contain only open deals")
        currency = deal.get("currency")
        if currency not in _ALLOWED_CURRENCIES:
            raise ValueError("unsupported currency")
        value = deal.get("value_cents")
        probability = deal.get("win_probability_basis_points")
        if type(value) is not int or not 0 <= value <= MAX_CENTS:
            raise ValueError("exact nonnegative integer accounting cents required")
        if type(probability) is not int or not 0 <= probability <= 10000:
            raise ValueError("explicit integer probability basis points required")
        _refs(deal.get("evidence_refs"))
        _refs(deal.get("probability_evidence_refs"))
        groups.setdefault(currency, []).append((value, probability))
    # Be independent of caller order for repeatable seeded simulations.
    return {currency: sorted(group) for currency, group in sorted(groups.items())}


def _percentile(sorted_numbers: list[int], percent: int) -> int:
    """Nearest-rank empirical percentile, never interpolates invented cents."""
    n = len(sorted_numbers)
    rank = (n * percent + 99) // 100
    return sorted_numbers[max(0, min(n - 1, rank - 1))]


def simulate_pipeline_scenarios(
    *, tenant_id: str, as_of: datetime,
    open_deals: Sequence[Mapping[str, Any]],
    simulations: int = 10000, seed: int = 101,
) -> dict[str, Any]:
    """Simulate independently won/not-won contract values in integer cents.

    This is NOT predicted receipts, recognized revenue, confidence coverage,
    verified demand, churn, client outcomes or a scientifically calibrated model.
    """
    tenant = _text(tenant_id, "tenant")
    now = _time(as_of)
    if type(simulations) is not int or not MIN_SIMULATIONS <= simulations <= MAX_SIMULATIONS:
        raise ValueError("simulations outside bounded range")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("fixed nonnegative random seed required")
    groups = _validate_deals(open_deals, tenant_id=tenant, as_of=now)
    output = []
    for currency, group in groups.items():
        # Separate deterministic stream per currency prevents a newly added
        # currency from altering existing projections for another currency.
        stream_seed = (seed ^ sum((i + 1) * ord(char) for i, char in enumerate(currency)))
        rng = Random(stream_seed)
        samples = []
        for _ in range(simulations):
            won = 0
            for value, probability in group:
                if rng.randrange(10000) < probability:
                    won += value
            samples.append(won)
        samples.sort()
        mean_numerator = sum(samples)
        # Prevent outputting unbounded projections when many deals are large.
        output.append({
            "currency": currency,
            "open_deal_count": len(group),
            "p10_contract_cents": _percentile(samples, 10),
            "p50_contract_cents": _percentile(samples, 50),
            "p90_contract_cents": _percentile(samples, 90),
            "mean_simulated_contract_cents": int(
                (Decimal(mean_numerator) / Decimal(simulations)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP,
                )
            ),
            "simulations_run": simulations,
            "inputs_independently_calibrated": False,
            "distribution_assumes_independent_deal_wins": True,
            "deal_value_variance_assumed": False,
            "sampling_uncertainty_quantified": False,
            "cash_receipts_forecast": False,
            "recognized_revenue_forecast": False,
            "commercial_use_approved": False,
        })
    return {
        "schema_version": "empire.predictive_revenue.prime_scenario.v1",
        "scenario_type": "HYPOTHETICAL_CONTRACT_VALUE_DISTRIBUTION",
        "mode": "OBSERVE",
        "tenant_id": tenant,
        "generated_as_of": now.isoformat(),
        "seed": seed,
        "currency_scenarios": output,
        "execution_authority": "none",
        "model_promoted": False,
        "revenue_verified": False,
    }


def review_churn_signals(
    *, tenant_id: str, as_of: datetime,
    signals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Create privacy-minimised retention review tasks, never send contact.

    An alert type or AI-generated 'score' is not a measured churn probability.
    """
    tenant = _text(tenant_id, "tenant")
    now = _time(as_of)
    if type(signals) not in (list, tuple) or len(signals) > MAX_DEALS:
        raise ValueError("bounded churn signals required")
    seen: set[str] = set()
    rows = []
    for signal in signals:
        if not isinstance(signal, Mapping) or signal.get("tenant_id") != tenant:
            raise ValueError("churn signal tenant mismatch")
        ref = _text(signal.get("signal_id"), "signal")
        account = _text(signal.get("account_id"), "account")
        signal_type = signal.get("signal_type")
        if signal_type not in _ALLOWED_CHURN_SIGNALS:
            raise ValueError("unsupported churn signal type")
        stamp = _time(signal.get("observed_at"))
        if stamp > now:
            raise ValueError("future churn signal")
        _refs(signal.get("evidence_refs"))
        if ref in seen:
            raise ValueError("duplicate churn signal ID")
        seen.add(ref)
        rows.append({
            "signal_id": ref,
            "account_ref": account,
            "signal_type": signal_type,
            "observed_at": stamp.isoformat(),
            "review_action": "FOUNDER_RETENTION_REVIEW",
            "churn_probability": None,
            "consent_verified": False,
            "suppression_checked": False,
            "outbound_allowed": False,
            "intervention_sent": False,
            "execution_authority": "none",
        })
    return {
        "schema_version": "empire.predictive_revenue.prime_churn_review.v1",
        "tenant_id": tenant,
        "mode": "OBSERVE",
        "review_count": len(rows),
        "reviews": sorted(rows, key=lambda row: row["signal_id"]),
        "estimated_churn_probability": None,
        "automatic_winback_disabled": True,
        "execution_authority": "none",
    }
