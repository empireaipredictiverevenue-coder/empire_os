"""Recommendation-only Zero-Cash operating policy for EmpireOS.

Determines whether a commercial action requires new cash and whether verified
cash/budget evidence supports it. Forecast revenue is never treated as cash.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ZeroCashCandidate:
    action_key: str
    product_code: str
    binding_terms_ready: bool
    incremental_cash_requirement_cents: int | None
    total_cost_cents: int | None
    requires_paid_acquisition: bool
    uses_owned_or_public_evidence: bool
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if not self.action_key.strip():
            raise ValueError("action_key required")
        if not self.product_code.strip():
            raise ValueError("product_code required")
        if not self.evidence_refs:
            raise ValueError("candidate evidence_refs required")
        for label, value in (
            (
                "incremental_cash_requirement_cents",
                self.incremental_cash_requirement_cents,
            ),
            ("total_cost_cents", self.total_cost_cents),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} must be nonnegative")
        if (
            self.requires_paid_acquisition
            and self.incremental_cash_requirement_cents == 0
        ):
            raise ValueError(
                "paid acquisition cannot have zero incremental cash requirement"
            )


@dataclass(frozen=True)
class ZeroCashDecision:
    action_key: str
    product_code: str
    decision: str
    incremental_cash_requirement_cents: int | None
    total_cost_cents: int | None
    total_cost_known: bool
    verified_spendable_cash_cents: int | None
    budget_authorized: bool
    uses_owned_or_public_evidence: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    mode: str = "OBSERVE"
    recommendation_only: bool = True
    forecast_revenue_used_as_cash: bool = False
    zero_incremental_cash_means_zero_total_cost: bool = False
    spend_execution: bool = False
    budget_mutation: bool = False
    payment_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _spendable_cash(
    available_cash_cents: int | None,
    reserved_cash_cents: int | None,
) -> int | None:
    if available_cash_cents is None:
        return None
    if available_cash_cents < 0:
        raise ValueError("available_cash_cents must be nonnegative")
    if reserved_cash_cents is None:
        return None
    if reserved_cash_cents < 0:
        raise ValueError("reserved_cash_cents must be nonnegative")
    return max(available_cash_cents - reserved_cash_cents, 0)


def evaluate_zero_cash_candidates(
    candidates: Iterable[ZeroCashCandidate],
    *,
    available_cash_cents: int | None,
    reserved_cash_cents: int | None,
    cash_evidence_ref: str | None,
    budget_authorized: bool,
    budget_evidence_ref: str | None,
) -> list[ZeroCashDecision]:
    spendable = _spendable_cash(
        available_cash_cents,
        reserved_cash_cents,
    )
    cash_ref = str(cash_evidence_ref or "").strip()
    budget_ref = str(budget_evidence_ref or "").strip()
    decisions: list[ZeroCashDecision] = []

    for candidate in candidates:
        candidate.validate()
        blockers: list[str] = []

        if not candidate.binding_terms_ready:
            decision = "BLOCKED_PRODUCT_NOT_READY"
            blockers.append("binding_terms_not_ready")
        elif candidate.incremental_cash_requirement_cents is None:
            decision = "UNKNOWN_CASH_REQUIREMENT"
            blockers.append("incremental_cash_requirement_unknown")
        elif candidate.incremental_cash_requirement_cents == 0:
            decision = "ELIGIBLE_ZERO_INCREMENTAL_CASH"
            if not candidate.uses_owned_or_public_evidence:
                blockers.append("owned_or_public_evidence_not_confirmed")
        else:
            requirement = candidate.incremental_cash_requirement_cents
            if spendable is None or not cash_ref:
                decision = "BLOCKED_INSUFFICIENT_CASH"
                blockers.append("verified_available_cash_unknown")
            elif spendable < requirement:
                decision = "BLOCKED_INSUFFICIENT_CASH"
                blockers.append("verified_spendable_cash_below_requirement")
            elif not budget_authorized or not budget_ref:
                decision = "BLOCKED_BUDGET_AUTHORITY"
                blockers.append("budget_authority_missing")
            else:
                decision = "ELIGIBLE_WITH_VERIFIED_CASH"

        refs = tuple(dict.fromkeys(
            [
                *candidate.evidence_refs,
                *([cash_ref] if cash_ref else []),
                *([budget_ref] if budget_ref else []),
            ]
        ))
        decisions.append(ZeroCashDecision(
            action_key=candidate.action_key,
            product_code=candidate.product_code,
            decision=decision,
            incremental_cash_requirement_cents=(
                candidate.incremental_cash_requirement_cents
            ),
            total_cost_cents=candidate.total_cost_cents,
            total_cost_known=candidate.total_cost_cents is not None,
            verified_spendable_cash_cents=spendable,
            budget_authorized=budget_authorized,
            uses_owned_or_public_evidence=(
                candidate.uses_owned_or_public_evidence
            ),
            blockers=tuple(blockers),
            evidence_refs=refs,
        ))

    order = {
        "ELIGIBLE_ZERO_INCREMENTAL_CASH": 0,
        "ELIGIBLE_WITH_VERIFIED_CASH": 1,
        "UNKNOWN_CASH_REQUIREMENT": 2,
        "BLOCKED_BUDGET_AUTHORITY": 3,
        "BLOCKED_INSUFFICIENT_CASH": 4,
        "BLOCKED_PRODUCT_NOT_READY": 5,
    }
    decisions.sort(
        key=lambda row: (order[row.decision], row.action_key)
    )
    return decisions
