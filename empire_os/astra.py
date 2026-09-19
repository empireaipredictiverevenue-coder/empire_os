"""Astra Bootstrap V1 — deterministic Empire operating coordinator.

Astra is the plan-only executive layer above EmpireOS specialist agents.
It chooses the next business workstream and the cheapest appropriate
intelligence route. It never performs external side effects itself.

Production actions remain governed by the underlying EmpireOS gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

ASTRA_VERSION = "bootstrap-v1"
PREMIUM_MIN_ROI_MULTIPLE = 5
IntelligenceRoute = Literal["rules", "local", "premium"]


@dataclass(frozen=True)
class AstraSnapshot:
    execution_mode: str = "observe"
    actual_revenue_cents: int = 0
    premium_ai_budget_cents: int = 0
    replies_waiting: int = 0
    failed_jobs: int = 0
    owned_inventory_count: int = 0
    qualified_unallocated_count: int = 0
    active_buyer_capacity: int = 0
    buyer_candidates_due: int = 0
    outbound_domain_verified: bool = False
    source_health_ok: bool = True


@dataclass(frozen=True)
class AstraDecision:
    version: str
    workstream: str
    recommended_job_type: str
    owner: str
    priority: int
    side_effect_approval_required: bool
    intelligence_route: IntelligenceRoute
    rationale: tuple[str, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AstraOperatingBoard:
    version: str
    mode: str
    primary: AstraDecision
    items: tuple[AstraDecision, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "mode": self.mode,
            "primary": self.primary.as_dict(),
            "items": [item.as_dict() for item in self.items],
            "side_effects": "none",
        }


def route_intelligence(
    snapshot: AstraSnapshot,
    *,
    task_kind: str = "routine",
    expected_value_cents: int = 0,
    premium_cost_cents: int = 0,
) -> IntelligenceRoute:
    kind = (task_kind or "routine").strip().lower()
    if kind in {"routine", "structured", "scoring", "matching"}:
        return "rules"
    if kind in {"language", "classification", "summary", "copy"}:
        return "local"
    if snapshot.actual_revenue_cents <= 0:
        return "local"
    if snapshot.premium_ai_budget_cents <= 0:
        return "local"
    if premium_cost_cents <= 0:
        return "local"
    if premium_cost_cents > snapshot.premium_ai_budget_cents:
        return "local"
    if expected_value_cents < premium_cost_cents * PREMIUM_MIN_ROI_MULTIPLE:
        return "local"
    return "premium"


def _decision_candidates(
    snapshot: AstraSnapshot,
    *,
    negative_margin_orders: int = 0,
    calibration_ready: bool = False,
    gross_margin_rate: float | None = None,
) -> list[AstraDecision]:
    mode = (snapshot.execution_mode or "observe").strip().lower()
    if mode not in {"observe", "dry_run"}:
        return [AstraDecision(
            ASTRA_VERSION, "governance", "review_execution_mode", "human", 100,
            True, "rules",
            ("bootstrap Astra expects observe or dry-run execution",),
            ("unexpected_execution_mode",),
        )]

    decisions: list[AstraDecision] = []

    if int(negative_margin_orders or 0) > 0:
        rationale = [
            "verified outcome feedback contains negative-margin orders",
            "unit economics require review before additional scaling",
        ]
        if gross_margin_rate is not None:
            rationale.append(
                f"observed feedback gross margin rate={float(gross_margin_rate):.4f}"
            )
        if not calibration_ready:
            rationale.append(
                "sample is below calibration threshold; review evidence without retuning models"
            )
        decisions.append(AstraDecision(
            ASTRA_VERSION,
            "unit_economics",
            "review_negative_margin",
            "revenue_intelligence",
            99,
            False,
            "rules",
            tuple(rationale),
            (),
        ))

    if snapshot.failed_jobs > 0:
        decisions.append(AstraDecision(
            ASTRA_VERSION, "operations", "recover_failed_jobs", "execution_bus",
            98, False, "rules",
            ("failed governed work must be understood before new work",), (),
        ))

    if snapshot.replies_waiting > 0:
        decisions.append(AstraDecision(
            ASTRA_VERSION, "buyer_relationships", "triage_buyer_replies",
            "nurture_agent", 97, False,
            route_intelligence(snapshot, task_kind="classification"),
            ("live buyer replies are the closest signal to revenue",), (),
        ))

    if snapshot.active_buyer_capacity <= 0:
        if not snapshot.outbound_domain_verified:
            decisions.append(AstraDecision(
                ASTRA_VERSION, "buyer_acquisition", "repair_outbound_channel",
                "sales_ops", 96, False, "rules",
                (
                    "buyer capacity is the current commercial bottleneck",
                    "outbound must be authenticated before buyer outreach",
                ),
                ("outbound_domain_unverified",),
            ))
        elif snapshot.buyer_candidates_due > 0:
            decisions.append(AstraDecision(
                ASTRA_VERSION, "buyer_acquisition", "prepare_buyer_outreach",
                "nurture_agent", 95, True,
                route_intelligence(snapshot, task_kind="copy"),
                (
                    "no commercially activated buyer capacity exists",
                    "qualified buyer candidates are ready for outreach",
                ),
                (),
            ))
        elif snapshot.source_health_ok:
            decisions.append(AstraDecision(
                ASTRA_VERSION, "buyer_acquisition", "source_buyer_candidates",
                "buyer_agent", 94, False, "rules",
                ("no commercially activated buyer capacity exists",), (),
            ))
    elif snapshot.qualified_unallocated_count > 0:
        decisions.append(AstraDecision(
            ASTRA_VERSION, "buyer_allocation", "plan_controlled_allocation",
            "buyer_agent", 93, True, "rules",
            ("qualified owned inventory and verified buyer capacity exist",), (),
        ))

    unqualified_inventory = max(
        int(snapshot.owned_inventory_count or 0)
        - int(snapshot.qualified_unallocated_count or 0),
        0,
    )
    if unqualified_inventory > 0:
        decisions.append(AstraDecision(
            ASTRA_VERSION, "qualification", "qualify_owned_inventory",
            "qualification_agent", 90, False, "rules",
            ("owned inventory exists that is not yet allocation-ready",), (),
        ))

    if not snapshot.source_health_ok:
        source_priority = (
            94
            if (
                snapshot.active_buyer_capacity <= 0
                and snapshot.buyer_candidates_due <= 0
                and snapshot.outbound_domain_verified
            )
            else 89
        )
        rationale = [
            "canonical acquisition must fail closed when sources are unhealthy",
        ]
        if source_priority == 94:
            rationale.append(
                "buyer acquisition cannot proceed without a healthy real-data source"
            )
        decisions.append(AstraDecision(
            ASTRA_VERSION, "source_health", "repair_real_data_sources",
            "acquisition_agent", source_priority, False, "rules",
            tuple(rationale),
            ("real_source_unavailable",),
        ))

    if (
        snapshot.active_buyer_capacity > 0
        and snapshot.owned_inventory_count <= 0
    ):
        decisions.append(AstraDecision(
            ASTRA_VERSION, "acquisition", "acquire_real_prospects",
            "acquisition_agent", 88, False, "rules",
            ("buyer capacity exists but there is no owned inventory to match",), (),
        ))

    if not decisions:
        decisions.append(AstraDecision(
            ASTRA_VERSION, "acquisition", "acquire_real_prospects",
            "acquisition_agent", 88, False, "rules",
            ("no higher-priority governed workstream is currently observed",), (),
        ))

    decisions.sort(
        key=lambda item: (
            -item.priority,
            item.workstream,
            item.recommended_job_type,
        )
    )
    return decisions


def build_operating_board(
    snapshot: AstraSnapshot,
    *,
    negative_margin_orders: int = 0,
    calibration_ready: bool = False,
    gross_margin_rate: float | None = None,
    limit: int = 5,
) -> AstraOperatingBoard:
    """Build a deterministic OBSERVE-only ranked executive work queue."""
    decisions = _decision_candidates(
        snapshot,
        negative_margin_orders=negative_margin_orders,
        calibration_ready=calibration_ready,
        gross_margin_rate=gross_margin_rate,
    )
    bounded_limit = max(1, min(int(limit), 20))
    items = tuple(decisions[:bounded_limit])
    return AstraOperatingBoard(
        version=ASTRA_VERSION,
        mode=(snapshot.execution_mode or "observe").strip().lower(),
        primary=items[0],
        items=items,
    )


def decide(snapshot: AstraSnapshot) -> AstraDecision:
    return build_operating_board(snapshot, limit=1).primary


def decide_with_outcomes(
    snapshot: AstraSnapshot,
    *,
    negative_margin_orders: int = 0,
    calibration_ready: bool = False,
    gross_margin_rate: float | None = None,
) -> AstraDecision:
    """Return the highest-priority evidence-backed Astra recommendation."""
    return build_operating_board(
        snapshot,
        negative_margin_orders=negative_margin_orders,
        calibration_ready=calibration_ready,
        gross_margin_rate=gross_margin_rate,
        limit=1,
    ).primary
