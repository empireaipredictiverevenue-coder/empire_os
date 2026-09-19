"""OBSERVE-only closer work projection and deterministic recommendations."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.closer_role_transport import PostgresCloserRpc


class CloserObserverError(RuntimeError):
    pass


@dataclass(frozen=True)
class CloserRecommendation:
    reply_id: str
    case_id: str | None
    case_state: str | None
    classification: str
    confidence: float | None
    recommendation_type: str
    rationale: tuple[str, ...]
    execution_allowed: bool = False
    proposed_message: None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rationale"] = list(self.rationale)
        return data


def bounded_closer_limit(value: Any, *, default: int = 50) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, 500))


def recommend_closer_work(row: Mapping[str, Any]) -> CloserRecommendation:
    classification = str(row.get("classification") or "").strip().lower()
    case_id = (
        str(row.get("case_id")).strip()
        if row.get("case_id") is not None
        else None
    )
    case_state = (
        str(row.get("case_state")).strip().lower()
        if row.get("case_state") is not None
        else None
    )
    reply_id = str(row.get("reply_id") or "").strip()
    if not reply_id:
        raise CloserObserverError("closer work row missing reply_id")

    raw_confidence = row.get("confidence")
    try:
        confidence = (
            None if raw_confidence is None else float(raw_confidence)
        )
    except (TypeError, ValueError):
        confidence = None

    if case_id is None:
        recommendation = "open_case"
        rationale = (
            "classified commercial reply has no canonical closer case",
        )
    elif case_state == "engaged":
        recommendation = {
            "positive": "qualify",
            "question": "answer_question",
            "objection": "handle_objection",
        }.get(classification, "escalate_human")
        rationale = (
            f"canonical closer case is engaged from {classification or 'unknown'} reply",
        )
    elif case_state == "qualified":
        recommendation = "prepare_proposal"
        rationale = ("qualified case is ready for governed proposal review",)
    elif case_state == "proposal_ready":
        recommendation = "escalate_human"
        rationale = ("proposal requires governed approval before advancement",)
    elif case_state == "proposal_approved":
        recommendation = "await_payment"
        rationale = ("approved proposal must await canonical accepted/invoiced order",)
    elif case_state == "awaiting_payment":
        recommendation = "await_payment"
        rationale = ("payment/outcome gate remains authoritative",)
    elif case_state == "paused":
        recommendation = "pause"
        rationale = ("canonical closer case is paused",)
    else:
        recommendation = "escalate_human"
        rationale = ("closer state requires human/governed review",)

    return CloserRecommendation(
        reply_id=reply_id,
        case_id=case_id,
        case_state=case_state,
        classification=classification,
        confidence=confidence,
        recommendation_type=recommendation,
        rationale=rationale,
    )


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def run_closer_observer_cycle(
    *,
    dsn: str,
    mode: str = "OBSERVE",
    limit: int = 50,
    output_path: str | Path = "runtime/closer/latest.json",
    rpc_factory: Callable[..., Any] = PostgresCloserRpc,
) -> dict[str, Any]:
    normalized_mode = str(mode or "OBSERVE").strip().upper()
    if normalized_mode != "OBSERVE":
        raise CloserObserverError(
            "closer observer supports OBSERVE only"
        )

    clean_dsn = str(dsn or "").strip()
    if not clean_dsn:
        raise CloserObserverError(
            "EMPIRE_CLOSER_OBSERVER_DSN is required"
        )

    bounded = bounded_closer_limit(limit)
    rpc = rpc_factory(clean_dsn, "empire_closer_observer")
    rows = rpc("list_closer_work", {"p_limit": bounded})
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise CloserObserverError(
            "closer work projection must return a list"
        )

    recommendations = [
        recommend_closer_work(row).as_dict()
        for row in rows
    ]
    payload = {
        "ok": True,
        "mode": "OBSERVE",
        "work_rows": len(rows),
        "recommendations": recommendations,
        "mutations_performed": 0,
        "outbound_sent": 0,
        "actual_revenue_declared": False,
    }
    atomic_write_json(Path(output_path), payload)
    return payload
