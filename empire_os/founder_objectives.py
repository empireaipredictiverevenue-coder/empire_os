"""Evidence-backed Founder Objectives / OKR layer.

Recovers the useful intent from legacy okf_tracker.py without its retired
SQLite/container assumptions or hardcoded proxy metrics. Objective progress is
computed only from observed evidence and always reports evidence coverage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class KeyResultDefinition:
    key: str
    label: str
    metric: str
    target: float
    weight: float
    target_origin: str
    target_confirmed: bool = False
    direction: str = "at_least"

    def validate(self) -> None:
        if not self.key.strip() or not self.label.strip() or not self.metric.strip():
            raise ValueError("key result identity fields required")
        if self.target < 0:
            raise ValueError("key result target must be nonnegative")
        if self.weight <= 0:
            raise ValueError("key result weight must be positive")
        if self.direction not in {"at_least", "at_most"}:
            raise ValueError("unsupported key result direction")
        if not self.target_origin.strip():
            raise ValueError("key result target origin required")


@dataclass(frozen=True)
class ObjectiveDefinition:
    key: str
    label: str
    owner: str
    key_results: tuple[KeyResultDefinition, ...]
    source: str = "founder_objectives_v1"

    def validate(self) -> None:
        if not self.key.strip() or not self.label.strip() or not self.owner.strip():
            raise ValueError("objective identity fields required")
        if not self.key_results:
            raise ValueError("objective requires key results")
        for item in self.key_results:
            item.validate()


@dataclass(frozen=True)
class MetricEvidence:
    metric: str
    value: float | int | None
    observed_at: str | None
    evidence_refs: tuple[str, ...]
    source: str
    state: str = "observed"

    def validate(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric evidence key required")
        if self.state not in {"observed", "unknown", "unavailable"}:
            raise ValueError("unsupported metric evidence state")
        if self.state == "observed":
            if self.value is None:
                raise ValueError("observed metric requires value")
            if not self.evidence_refs:
                raise ValueError("observed metric requires evidence refs")
            if not str(self.observed_at or "").strip():
                raise ValueError("observed metric requires observed_at")
        if not self.source.strip():
            raise ValueError("metric evidence source required")


LEGACY_RECOVERED_OBJECTIVES: tuple[ObjectiveDefinition, ...] = (
    ObjectiveDefinition(
        key="O1",
        label=(
            "Trigger detection at scale — catch real-time buy signals, "
            "not generic funnel leads"
        ),
        owner="Business Manager",
        key_results=(
            KeyResultDefinition(
                key="O1-KR1",
                label="Detect 50k+ trigger events",
                metric="total_triggers",
                target=50_000,
                weight=0.4,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O1-KR2",
                label="Sustain 13k+ new triggers per month",
                metric="monthly_new_triggers",
                target=13_000,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O1-KR3",
                label="Expand to 100+ trigger verticals/sectors",
                metric="vertical_count",
                target=100,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
        ),
        source="legacy:okf_tracker.py",
    ),
    ObjectiveDefinition(
        key="O2",
        label="Reputation + discovery through relationships and referrals",
        owner="Chief of Staff",
        key_results=(
            KeyResultDefinition(
                key="O2-KR1",
                label="Build a 5k+ connected-entity discovery graph",
                metric="graph_nodes",
                target=5_000,
                weight=0.4,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O2-KR2",
                label="Interaction quality score >= 0.8",
                metric="interaction_quality",
                target=0.8,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O2-KR3",
                label="First 10 recurring discovery loops",
                metric="retained_buyers",
                target=10,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
        ),
        source="legacy:okf_tracker.py",
    ),
    ObjectiveDefinition(
        key="O3",
        label="Machine-earning A2A / MCP supply layer live and paid",
        owner="CEO",
        key_results=(
            KeyResultDefinition(
                key="O3-KR1",
                label="MCP service uptime >= 99%",
                metric="mcp_uptime_pct",
                target=99,
                weight=0.4,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O3-KR2",
                label="First 1k monthly recurring revenue from agent buyers",
                metric="agent_mrr",
                target=1_000,
                weight=0.4,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O3-KR3",
                label="3+ external AI-agent buyers",
                metric="agent_buyers",
                target=3,
                weight=0.2,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
        ),
        source="legacy:okf_tracker.py",
    ),
    ObjectiveDefinition(
        key="O4",
        label="Organic self-influence and machine discovery",
        owner="Deep Research",
        key_results=(
            KeyResultDefinition(
                key="O4-KR1",
                label="Publish 20+ genuinely citeable AEO assets",
                metric="aeo_assets",
                target=20,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O4-KR2",
                label="Empire graph centrality >= 0.5",
                metric="graph_centrality",
                target=0.5,
                weight=0.4,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
            KeyResultDefinition(
                key="O4-KR3",
                label="100+ monthly MCP self-influence pulls",
                metric="agent_pull",
                target=100,
                weight=0.3,
                target_origin="legacy:okf_tracker.py:2026-Q3",
            ),
        ),
        source="legacy:okf_tracker.py",
    ),
)


CURRENT_FOUNDER_OBJECTIVES: tuple[ObjectiveDefinition, ...] = (
    ObjectiveDefinition(
        key="F1",
        label="Prove the genuine commercial revenue loop",
        owner="Founder / Revenue",
        key_results=(
            KeyResultDefinition(
                key="F1-KR1",
                label="At least one genuine commercial buyer conversation",
                metric="commercial_buyer_conversations",
                target=1,
                weight=0.25,
                target_origin="blueprint:founder_execution_lock",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F1-KR2",
                label="At least one agreed commercial terms package",
                metric="commercial_terms",
                target=1,
                weight=0.25,
                target_origin="blueprint:founder_execution_lock",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F1-KR3",
                label="At least one verified payment",
                metric="verified_payments",
                target=1,
                weight=0.25,
                target_origin="blueprint:founder_execution_lock",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F1-KR4",
                label="Positive recognized revenue evidence exists",
                metric="recognized_revenue_cents",
                target=1,
                weight=0.25,
                target_origin="blueprint:founder_execution_lock",
                target_confirmed=True,
            ),
        ),
        source="blueprint:founder_execution_lock",
    ),
    ObjectiveDefinition(
        key="F2",
        label="Turn Intelligence Fabric into sellable products",
        owner="Founder / Product",
        key_results=(
            KeyResultDefinition(
                key="F2-KR1",
                label="Ten first-class Intelligence Nodes defined",
                metric="intelligence_nodes_defined",
                target=10,
                weight=0.3,
                target_origin="blueprint:intelligence_nodes",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F2-KR2",
                label="At least one sellable Search/SERP product contract live",
                metric="sellable_search_products",
                target=1,
                weight=0.35,
                target_origin="blueprint:search_product_suite",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F2-KR3",
                label="Revenue Pulse V3 read model operational",
                metric="revenue_pulse_operational",
                target=1,
                weight=0.35,
                target_origin="blueprint:revenue_pulse",
                target_confirmed=True,
            ),
        ),
        source="blueprint:founder_execution_lock",
    ),
    ObjectiveDefinition(
        key="F3",
        label="Give the Founder reliable operating visibility",
        owner="Founder / Chief of Staff",
        key_results=(
            KeyResultDefinition(
                key="F3-KR1",
                label="Founder Console private read API operational",
                metric="founder_console_read_api",
                target=1,
                weight=0.35,
                target_origin="blueprint:founder_console",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F3-KR2",
                label="Commercial blocker visible from canonical evidence",
                metric="commercial_blocker_visible",
                target=1,
                weight=0.35,
                target_origin="blueprint:founder_console",
                target_confirmed=True,
            ),
            KeyResultDefinition(
                key="F3-KR3",
                label="Revenue Pulse visible to Founder Console",
                metric="revenue_pulse_visible",
                target=1,
                weight=0.3,
                target_origin="blueprint:founder_console",
                target_confirmed=True,
            ),
        ),
        source="blueprint:founder_execution_lock",
    ),
)


def _progress(
    definition: KeyResultDefinition,
    evidence: MetricEvidence | None,
) -> dict[str, Any]:
    if evidence is None:
        return {
            "key": definition.key,
            "label": definition.label,
            "metric": definition.metric,
            "target": definition.target,
            "weight": definition.weight,
            "target_origin": definition.target_origin,
            "target_confirmed": definition.target_confirmed,
            "state": "unknown",
            "current": None,
            "progress": None,
            "evidence_refs": [],
            "observed_at": None,
            "source": None,
        }
    evidence.validate()
    if evidence.state != "observed":
        return {
            "key": definition.key,
            "label": definition.label,
            "metric": definition.metric,
            "target": definition.target,
            "weight": definition.weight,
            "target_origin": definition.target_origin,
            "target_confirmed": definition.target_confirmed,
            "state": evidence.state,
            "current": None,
            "progress": None,
            "evidence_refs": list(evidence.evidence_refs),
            "observed_at": evidence.observed_at,
            "source": evidence.source,
        }

    current = float(evidence.value)
    if definition.target == 0:
        progress = 1.0 if current == 0 else 0.0
    elif definition.direction == "at_least":
        progress = max(0.0, min(1.0, current / definition.target))
    else:
        progress = (
            1.0
            if current <= definition.target
            else max(0.0, min(1.0, definition.target / current))
        )
    return {
        "key": definition.key,
        "label": definition.label,
        "metric": definition.metric,
        "target": definition.target,
        "weight": definition.weight,
        "target_origin": definition.target_origin,
        "target_confirmed": definition.target_confirmed,
        "state": "observed",
        "current": current,
        "progress": round(progress, 4),
        "evidence_refs": list(evidence.evidence_refs),
        "observed_at": evidence.observed_at,
        "source": evidence.source,
    }


def evaluate_objectives(
    objectives: Iterable[ObjectiveDefinition],
    evidence: Mapping[str, MetricEvidence],
    *,
    cycle: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_weight = 0.0
    weighted_progress = 0.0
    known_weight = 0.0
    confirmed_weight = 0.0

    for objective in objectives:
        objective.validate()
        kr_rows = [
            _progress(kr, evidence.get(kr.metric))
            for kr in objective.key_results
        ]
        objective_weight = sum(kr.weight for kr in objective.key_results)
        objective_known = sum(
            row["weight"]
            for row in kr_rows
            if row["progress"] is not None
        )
        objective_score = sum(
            row["progress"] * row["weight"]
            for row in kr_rows
            if row["progress"] is not None
        )
        objective_confirmed = sum(
            row["weight"]
            for row in kr_rows
            if row["target_confirmed"] is True
        )
        rows.append({
            "key": objective.key,
            "label": objective.label,
            "owner": objective.owner,
            "source": objective.source,
            "evidence_weighted_progress": round(
                objective_score / objective_weight, 4
            ) if objective_weight else None,
            "evidence_coverage": round(
                objective_known / objective_weight, 4
            ) if objective_weight else 0.0,
            "target_confirmation_coverage": round(
                objective_confirmed / objective_weight, 4
            ) if objective_weight else 0.0,
            "key_results": kr_rows,
        })
        total_weight += objective_weight
        weighted_progress += objective_score
        known_weight += objective_known
        confirmed_weight += objective_confirmed

    return {
        "schema_version": "empire.founder-objectives.v1",
        "cycle": cycle,
        "mode": "OBSERVE",
        "execution_allowed": False,
        "progress_kind": "evidence_weighted",
        "unknown_metrics_are_not_zero": True,
        "overall_evidence_weighted_progress": round(
            weighted_progress / total_weight, 4
        ) if total_weight else None,
        "overall_evidence_coverage": round(
            known_weight / total_weight, 4
        ) if total_weight else 0.0,
        "overall_target_confirmation_coverage": round(
            confirmed_weight / total_weight, 4
        ) if total_weight else 0.0,
        "objectives": rows,
    }
