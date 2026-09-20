"""Canonical Revenue Pulse V3 read model.

Revenue Pulse summarizes observed commercial movement without mutating
commercial state. Forecasts and modeled opportunity remain explicitly
separate from recognized revenue and realized GP.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


STAGE_KEYS = (
    "acquisitions",
    "qualified",
    "buyer_reviews",
    "delivered_outreach",
    "commercial_replies",
    "commercial_terms",
    "verified_payments",
    "fulfilments",
)


@dataclass(frozen=True)
class RevenuePulseWindow:
    label: str
    hours: int
    acquisitions: int | None = None
    qualified: int | None = None
    buyer_reviews: int | None = None
    delivered_outreach: int | None = None
    commercial_replies: int | None = None
    commercial_terms: int | None = None
    verified_payments: int | None = None
    fulfilments: int | None = None
    recognized_revenue_cents: int | None = None
    realized_gp_cents: int | None = None
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.label.strip():
            raise ValueError("pulse window label required")
        if self.hours <= 0:
            raise ValueError("pulse window hours must be positive")
        for key in STAGE_KEYS:
            value = getattr(self, key)
            if value is not None and value < 0:
                raise ValueError(f"{key} must be nonnegative")
        for key in (
            "recognized_revenue_cents",
            "realized_gp_cents",
        ):
            value = getattr(self, key)
            if value is not None and value < 0:
                raise ValueError(f"{key} must be nonnegative")
        if not self.evidence_refs:
            raise ValueError("pulse window evidence required")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RevenuePulseForecast:
    horizon: str
    forecast_revenue_cents: int | None
    confidence: float | None
    evidence_refs: tuple[str, ...]
    model_key: str | None = None

    def validate(self) -> None:
        if not self.horizon.strip():
            raise ValueError("forecast horizon required")
        if (
            self.forecast_revenue_cents is not None
            and self.forecast_revenue_cents < 0
        ):
            raise ValueError("forecast revenue must be nonnegative")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("forecast confidence must be 0..1")
        if not self.evidence_refs:
            raise ValueError("forecast evidence required")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StormPulse:
    opportunity_count: int
    max_multiplier: float | None
    priority_boost_max: float | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if self.opportunity_count < 0:
            raise ValueError("storm opportunity count must be nonnegative")
        if self.max_multiplier is not None and self.max_multiplier < 1:
            raise ValueError("storm multiplier must be >= 1")
        if (
            self.priority_boost_max is not None
            and self.priority_boost_max < 0
        ):
            raise ValueError("storm priority boost must be nonnegative")
        if not self.evidence_refs:
            raise ValueError("storm pulse evidence required")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rate(entered: int | None, converted: int | None) -> float | None:
    if entered is None or converted is None or entered <= 0:
        return None
    return round(converted / entered, 4)


def _delta(
    current: int | None,
    previous: int | None,
) -> dict[str, Any]:
    if current is None or previous is None:
        return {
            "state": "unknown",
            "absolute_change": None,
            "pct_change": None,
        }
    absolute = current - previous
    if previous == 0:
        return {
            "state": (
                "new_activity"
                if current > 0
                else "stable_zero"
            ),
            "absolute_change": absolute,
            "pct_change": None,
        }
    pct = round(absolute / previous, 4)
    return {
        "state": (
            "up" if absolute > 0
            else "down" if absolute < 0
            else "flat"
        ),
        "absolute_change": absolute,
        "pct_change": pct,
    }


def _conversion_map(
    window: RevenuePulseWindow,
) -> dict[str, float | None]:
    return {
        "acquisition_to_qualified": _rate(
            window.acquisitions,
            window.qualified,
        ),
        "qualified_to_buyer_review": _rate(
            window.qualified,
            window.buyer_reviews,
        ),
        "buyer_review_to_delivered_outreach": _rate(
            window.buyer_reviews,
            window.delivered_outreach,
        ),
        "delivered_outreach_to_commercial_reply": _rate(
            window.delivered_outreach,
            window.commercial_replies,
        ),
        "commercial_reply_to_terms": _rate(
            window.commercial_replies,
            window.commercial_terms,
        ),
        "terms_to_verified_payment": _rate(
            window.commercial_terms,
            window.verified_payments,
        ),
        "verified_payment_to_fulfilment": _rate(
            window.verified_payments,
            window.fulfilments,
        ),
    }


def _pulse_state(
    current: RevenuePulseWindow,
    blocker: str | None,
) -> str:
    if (current.recognized_revenue_cents or 0) > 0:
        return "recognized_revenue_observed"
    if (current.verified_payments or 0) > 0:
        return "verified_payment_observed"
    if (current.commercial_terms or 0) > 0:
        return "terms_active"
    if (current.commercial_replies or 0) > 0:
        return "commercial_conversation_active"
    if (current.delivered_outreach or 0) > 0:
        return "conversation_blocked"
    if (current.buyer_reviews or 0) > 0:
        return "buyer_review_active"
    if (current.acquisitions or 0) > 0:
        return "pipeline_building"
    if blocker:
        return "blocked"
    return "no_observed_activity"


def build_revenue_pulse(
    *,
    current: RevenuePulseWindow,
    previous: RevenuePulseWindow | None = None,
    highest_priority_blocker: str | None = None,
    blocker_state: str | None = None,
    forecasts: Iterable[RevenuePulseForecast] = (),
    storm: StormPulse | None = None,
    node_pulses: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    current.validate()
    if previous is not None:
        previous.validate()
    forecast_rows = tuple(forecasts)
    for row in forecast_rows:
        row.validate()
    if storm is not None:
        storm.validate()

    velocity = {
        key: _delta(
            getattr(current, key),
            getattr(previous, key) if previous else None,
        )
        for key in STAGE_KEYS
    }

    revenue_velocity = _delta(
        current.recognized_revenue_cents,
        (
            previous.recognized_revenue_cents
            if previous
            else None
        ),
    )
    gp_velocity = _delta(
        current.realized_gp_cents,
        previous.realized_gp_cents if previous else None,
    )

    observed_refs = list(current.evidence_refs)
    if previous is not None:
        observed_refs.extend(previous.evidence_refs)
    if storm is not None:
        observed_refs.extend(storm.evidence_refs)

    return {
        "schema_version": "empire.revenue-pulse.v3",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "execution_allowed": False,
        "payment_mutation": False,
        "revenue_mutation": False,
        "accounting_mutation": False,
        "pulse_state": _pulse_state(
            current,
            highest_priority_blocker,
        ),
        "highest_priority_blocker": highest_priority_blocker,
        "blocker_state": blocker_state,
        "current_window": current.as_dict(),
        "previous_window": (
            previous.as_dict()
            if previous is not None
            else None
        ),
        "conversion": _conversion_map(current),
        "velocity": velocity,
        "recognized_revenue_truth": {
            "recognized_revenue_cents": (
                current.recognized_revenue_cents
            ),
            "realized_gp_cents": current.realized_gp_cents,
            "revenue_velocity": revenue_velocity,
            "gp_velocity": gp_velocity,
            "forecast_included_in_truth": False,
        },
        "storm_pulse": (
            storm.as_dict()
            if storm is not None
            else None
        ),
        "node_pulses": dict(node_pulses or {}),
        "forecast": {
            "separate_from_revenue_truth": True,
            "items": [
                row.as_dict()
                for row in forecast_rows
            ],
        },
        "evidence_refs": sorted(set(observed_refs)),
        "unknown_stays_unknown": True,
    }
