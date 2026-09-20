"""Deterministic handoff from classified buyer replies into closer cases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

COMMERCIAL_CLASSES = {
    "positive": "qualify",
    "question": "answer_question",
    "objection": "handle_objection",
}


@dataclass(frozen=True)
class CloserReplyWorkerResult:
    rows_seen: int
    cases_opened: int
    recommendations_recorded: int
    skipped_existing: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows_seen": self.rows_seen,
            "cases_opened": self.cases_opened,
            "recommendations_recorded": self.recommendations_recorded,
            "skipped_existing": self.skipped_existing,
            "errors": list(self.errors),
            "actual_revenue": False,
            "outbound_sent": False,
            "payment_mutation": False,
        }


Rpc = Callable[[str, dict[str, Any]], Any]


def _confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 0.70
    return max(0.0, min(parsed, 1.0))


def run_closer_reply_worker(
    rpc: Rpc,
    *,
    limit: int = 50,
) -> CloserReplyWorkerResult:
    bounded = max(1, min(int(limit), 500))
    rows = rpc("list_closer_work", {"p_limit": bounded}) or []
    if not isinstance(rows, list):
        raise ValueError("closer work projection must be a list")

    opened = recorded = existing = 0
    errors: list[str] = []

    for row in rows:
        if not isinstance(row, Mapping):
            continue
        reply_id = str(row.get("reply_id") or "").strip()
        classification = str(row.get("classification") or "").strip().lower()
        case_id = str(row.get("case_id") or "").strip() or None
        if not reply_id or classification not in COMMERCIAL_CLASSES:
            continue
        if case_id:
            existing += 1
            continue

        try:
            opened_result = rpc(
                "open_closer_case",
                {"p_reply_id": reply_id},
            )
            case_id = str((opened_result or {}).get("case_id") or "").strip()
            if not case_id:
                raise ValueError("open_closer_case returned no case_id")
            if str((opened_result or {}).get("decision") or "") == "opened":
                opened += 1

            rpc(
                "record_closer_recommendation",
                {
                    "p_case_id": case_id,
                    "p_type": COMMERCIAL_CLASSES[classification],
                    "p_confidence": _confidence(row.get("confidence")),
                    "p_rationale": {
                        "source": "deterministic_reply_handoff",
                        "reply_id": reply_id,
                        "classification": classification,
                    },
                    "p_message": None,
                    "p_model_key": "deterministic_closer_router_v1",
                },
            )
            recorded += 1
        except Exception as exc:
            errors.append(
                f"{reply_id}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return CloserReplyWorkerResult(
        rows_seen=len(rows),
        cases_opened=opened,
        recommendations_recorded=recorded,
        skipped_existing=existing,
        errors=tuple(errors),
    )
