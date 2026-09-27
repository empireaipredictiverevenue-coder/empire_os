"""Company operating primitives for Marketing, R&D and Chief of Staff.

Pure planning/review only. No publishing, outreach, spend, production changes,
staffing actions, commercial mutations or deployment authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


DEPARTMENTS = {
    "marketing",
    "rd",
    "product",
    "engineering",
    "data",
    "sales",
    "customer_success",
    "finance",
    "legal_security",
    "operations",
    "agi_quant",
}

INITIATIVE_STATES = {
    "idea",
    "triage",
    "planned",
    "in_progress",
    "blocked",
    "review",
    "validated",
    "transfer_ready",
    "completed",
    "stopped",
}

DECISION_TIERS = {
    "interrupt",
    "same_day",
    "weekly",
    "delegated",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class StrategicInitiative:
    initiative_id: str
    title: str
    department: str
    owner: str
    state: str
    objective: str
    expected_gross_profit_cents: float | None
    strategic_impact: float | None
    urgency: float | None
    confidence: float | None
    risk: float | None
    reversibility: float | None
    effort: float | None
    value_of_information_cents: float | None
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]

    def validate(self) -> None:
        if not _text(self.initiative_id):
            raise ValueError("initiative_id required")
        if not _text(self.title):
            raise ValueError("title required")
        if self.department not in DEPARTMENTS:
            raise ValueError("unsupported department")
        if not _text(self.owner):
            raise ValueError("owner required")
        if self.state not in INITIATIVE_STATES:
            raise ValueError("unsupported initiative state")
        if not _text(self.objective):
            raise ValueError("objective required")
        if not self.evidence_refs:
            raise ValueError("initiative requires evidence_refs")
        for name, value in (
            ("strategic_impact", self.strategic_impact),
            ("urgency", self.urgency),
            ("confidence", self.confidence),
            ("risk", self.risk),
            ("reversibility", self.reversibility),
            ("effort", self.effort),
        ):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "evidence_refs": list(self.evidence_refs),
            "blockers": list(self.blockers),
        }


def initiative_from_mapping(raw: Mapping[str, Any]) -> StrategicInitiative:
    return StrategicInitiative(
        initiative_id=_text(raw.get("initiative_id")),
        title=_text(raw.get("title")),
        department=_text(raw.get("department")).lower(),
        owner=_text(raw.get("owner")),
        state=_text(raw.get("state")).lower() or "idea",
        objective=_text(raw.get("objective")),
        expected_gross_profit_cents=_number(raw.get("expected_gross_profit_cents")),
        strategic_impact=_number(raw.get("strategic_impact")),
        urgency=_number(raw.get("urgency")),
        confidence=_number(raw.get("confidence")),
        risk=_number(raw.get("risk")),
        reversibility=_number(raw.get("reversibility")),
        effort=_number(raw.get("effort")),
        value_of_information_cents=_number(raw.get("value_of_information_cents")),
        evidence_refs=tuple(
            _text(x) for x in raw.get("evidence_refs", ()) if _text(x)
        ),
        blockers=tuple(
            _text(x) for x in raw.get("blockers", ()) if _text(x)
        ),
    )


def priority_score(initiative: StrategicInitiative) -> dict[str, Any]:
    """Score only supplied evidence; unknown inputs remain explicit."""
    initiative.validate()
    required = {
        "strategic_impact": initiative.strategic_impact,
        "urgency": initiative.urgency,
        "confidence": initiative.confidence,
        "risk": initiative.risk,
        "reversibility": initiative.reversibility,
        "effort": initiative.effort,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        return {
            "initiative_id": initiative.initiative_id,
            "available": False,
            "score": None,
            "missing": missing,
            "execution_authority": "none",
        }

    gp_term = 0.0
    if initiative.expected_gross_profit_cents is not None:
        # Bounded monotonic contribution without pretending currency scale is universal.
        gp_term = min(max(initiative.expected_gross_profit_cents, 0) / 1_000_000, 1)

    voi_term = 0.0
    if initiative.value_of_information_cents is not None:
        voi_term = min(max(initiative.value_of_information_cents, 0) / 250_000, 1)

    score = (
        0.24 * initiative.strategic_impact
        + 0.18 * initiative.urgency
        + 0.16 * initiative.confidence
        + 0.12 * initiative.reversibility
        + 0.10 * (1 - initiative.risk)
        + 0.08 * (1 - initiative.effort)
        + 0.08 * gp_term
        + 0.04 * voi_term
    )
    if initiative.blockers:
        score *= 0.75

    return {
        "initiative_id": initiative.initiative_id,
        "available": True,
        "score": round(score, 6),
        "missing": [],
        "has_blockers": bool(initiative.blockers),
        "execution_authority": "none",
    }


def rank_initiatives(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    ranked: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in rows:
        initiative = initiative_from_mapping(raw)
        initiative.validate()
        if initiative.initiative_id in seen:
            raise ValueError("duplicate initiative_id")
        seen.add(initiative.initiative_id)

        score = priority_score(initiative)
        item = {
            **initiative.as_dict(),
            "priority": score,
        }
        if score["available"]:
            ranked.append(item)
        else:
            unavailable.append(item)

    ranked.sort(
        key=lambda item: (
            item["priority"]["score"],
            item["initiative_id"],
        ),
        reverse=True,
    )
    for idx, item in enumerate(ranked, 1):
        item["rank"] = idx

    return {
        "schema_version": "company_initiative_portfolio.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "ranked": ranked,
        "unscored": unavailable,
        "portfolio_mutation": False,
    }


def build_founder_brief(
    *,
    date: str,
    verified_outcomes: Sequence[Mapping[str, Any]],
    initiatives: Sequence[Mapping[str, Any]],
    decisions_needed: Sequence[Mapping[str, Any]],
    risks: Sequence[Mapping[str, Any]],
    max_priorities: int = 3,
) -> dict[str, Any]:
    if not _text(date):
        raise ValueError("date required")
    if max_priorities < 1 or max_priorities > 5:
        raise ValueError("max_priorities must be between 1 and 5")

    portfolio = rank_initiatives(initiatives)
    priorities = portfolio["ranked"][:max_priorities]

    outcomes = []
    for raw in verified_outcomes:
        outcome_ref = _text(raw.get("outcome_ref"))
        if not outcome_ref or raw.get("verified") is not True:
            continue
        outcomes.append({
            "outcome_ref": outcome_ref,
            "summary": _text(raw.get("summary")) or None,
            "recognized_revenue_cents": _number(raw.get("recognized_revenue_cents")),
            "gross_profit_cents": _number(raw.get("gross_profit_cents")),
        })

    decisions = []
    for raw in decisions_needed:
        tier = _text(raw.get("tier")).lower()
        if tier not in DECISION_TIERS:
            continue
        decision_id = _text(raw.get("decision_id"))
        if not decision_id:
            continue
        decisions.append({
            "decision_id": decision_id,
            "tier": tier,
            "summary": _text(raw.get("summary")) or None,
            "owner": _text(raw.get("owner")) or None,
            "deadline": _text(raw.get("deadline")) or None,
            "evidence_refs": [
                _text(x) for x in raw.get("evidence_refs", ()) if _text(x)
            ],
        })

    valid_risks = []
    for raw in risks:
        risk_id = _text(raw.get("risk_id"))
        if not risk_id:
            continue
        valid_risks.append({
            "risk_id": risk_id,
            "summary": _text(raw.get("summary")) or None,
            "severity": _text(raw.get("severity")) or None,
            "evidence_refs": [
                _text(x) for x in raw.get("evidence_refs", ()) if _text(x)
            ],
        })

    return {
        "schema_version": "founder_brief.v1",
        "date": date,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "verified_outcomes": outcomes,
        "top_priorities": priorities,
        "decisions_needed": decisions,
        "risks": valid_risks,
        "brief_generation_only": True,
    }


def review_rd_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Govern research promotion without confusing prototype with product."""
    stage = _text(candidate.get("stage")).lower()
    allowed_stages = {
        "idea", "triage", "research", "hypothesis", "prototype",
        "evaluation", "shadow", "validated", "transfer_ready",
    }
    blockers: list[str] = []

    if stage not in allowed_stages:
        blockers.append("unsupported_stage")
    if not _text(candidate.get("research_id")):
        blockers.append("research_id_required")
    if not _text(candidate.get("hypothesis")):
        blockers.append("hypothesis_required")
    if not candidate.get("evidence_refs"):
        blockers.append("evidence_refs_required")
    if stage in {"evaluation", "shadow", "validated", "transfer_ready"}:
        if not _text(candidate.get("baseline_ref")):
            blockers.append("baseline_ref_required")
        if not _text(candidate.get("evaluation_ref")):
            blockers.append("evaluation_ref_required")
    if stage in {"validated", "transfer_ready"} and candidate.get("independent_review_passed") is not True:
        blockers.append("independent_review_required")
    if stage == "transfer_ready":
        if not _text(candidate.get("transfer_target")):
            blockers.append("transfer_target_required")
        if not _text(candidate.get("productization_brief_ref")):
            blockers.append("productization_brief_required")
    if candidate.get("synthetic_only") is True and stage in {"validated", "transfer_ready"}:
        blockers.append("synthetic_only_cannot_validate_commercial_research")

    return {
        "schema_version": "rd_candidate_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "research_id": _text(candidate.get("research_id")) or None,
        "stage": stage or None,
        "review_ready": not blockers,
        "blockers": blockers,
        "production_deployment": False,
        "product_launch": False,
        "model_promotion": False,
    }


def review_marketing_brief(brief: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    required = (
        "campaign_id",
        "objective",
        "audience",
        "product",
        "offer",
        "success_metric",
    )
    for field in required:
        if not _text(brief.get(field)):
            blockers.append(f"{field}_required")
    if not brief.get("evidence_refs"):
        blockers.append("evidence_refs_required")
    if not brief.get("attribution_plan"):
        blockers.append("attribution_plan_required")
    if brief.get("public_publish") is True:
        blockers.append("public_publish_requires_separate_approval")
    if brief.get("outbound_send") is True:
        blockers.append("outbound_send_requires_separate_approval")
    if _number(brief.get("paid_spend_cents")) not in (None, 0):
        blockers.append("paid_spend_requires_separate_approval")

    return {
        "schema_version": "marketing_brief_review.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "review_ready": not blockers,
        "blockers": blockers,
        "publishing_enabled": False,
        "outbound_enabled": False,
        "paid_spend_enabled": False,
    }
