"""Bounded no-reply follow-up proposal worker.

This worker never sends email. It only asks the database for follow-ups that are
already due under the governed sequence contract and proposes deterministic
copy. Approval and send remain separate outbound-governor steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"


@dataclass(frozen=True)
class FollowupWorkerResult:
    due_seen: int
    proposed: int
    deferred_outside_window: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "due_seen": self.due_seen,
            "proposed": self.proposed,
            "deferred_outside_window": self.deferred_outside_window,
            "errors": list(self.errors),
            "actual_revenue": False,
            "send_executed": False,
            "payment_mutation": False,
        }


Request = Callable[..., Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _business_name(row: Mapping[str, Any]) -> str:
    evidence = row.get("candidate_evidence")
    if isinstance(evidence, Mapping):
        name = _text(evidence.get("business_name"))
        if name:
            return name
    return "your team"


def _market_context(row: Mapping[str, Any]) -> str:
    evidence = row.get("candidate_evidence")
    if not isinstance(evidence, Mapping):
        return "the opportunity data"
    metro = _text(evidence.get("metro"))
    niche = _text(evidence.get("niche"))
    if metro and niche:
        return f"the {metro} {niche} opportunity data"
    if metro:
        return f"the {metro} opportunity data"
    if niche:
        return f"the {niche} opportunity data"
    return "the opportunity data"


def build_followup_copy(row: Mapping[str, Any]) -> tuple[str, str]:
    step = int(row.get("followup_step") or 0)
    root_subject = _text(row.get("root_subject"))
    business = _business_name(row)
    context = _market_context(row)
    subject = f"Re: {root_subject}" if root_subject else "Quick follow-up"

    if step == 1:
        message = (
            "Hi,\n\n"
            "Just bringing this back to the top of your inbox. "
            f"The evidence behind {context} is real, and I can send a short "
            f"breakdown of what we found for {business}.\n\n"
            "Worth a quick look?\n\n"
        )
    elif step == 2:
        message = (
            "Hi,\n\n"
            "Last note from me on this. "
            f"If this is relevant for {business}, I can send the short "
            "opportunity breakdown and pilot outline. If not, no problem at all.\n\n"
        )
    else:
        raise ValueError("follow-up step must be 1 or 2")

    body = (
        message
        + "Best,\nPhil\nFounder, Empire AI\nempire-ai.co.uk\n\n"
        + POSTAL_ADDRESS
        + "\nIf you’d rather not hear from me, reply “opt out”."
    )
    return subject, body


def within_send_window(
    now: datetime,
    *,
    start_hour_utc: int = 14,
    end_hour_utc: int = 21,
) -> bool:
    current = now.astimezone(timezone.utc)
    if current.weekday() >= 5:
        return False
    return start_hour_utc <= current.hour <= end_hour_utc


def run_followup_worker(
    request: Request,
    *,
    limit: int = 25,
    now: datetime | None = None,
    start_hour_utc: int = 14,
    end_hour_utc: int = 21,
) -> FollowupWorkerResult:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if not within_send_window(
        current,
        start_hour_utc=start_hour_utc,
        end_hour_utc=end_hour_utc,
    ):
        return FollowupWorkerResult(
            due_seen=0,
            proposed=0,
            deferred_outside_window=True,
            errors=(),
        )

    bounded = max(1, min(int(limit), 100))
    rows = request(
        "POST",
        "/rest/v1/rpc/list_due_outbound_followups",
        payload={"p_limit": bounded},
    ) or []
    if not isinstance(rows, list):
        raise ValueError("due follow-up projection must be a list")

    proposed = 0
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        root_id = _text(row.get("root_intent_id"))
        try:
            step = int(row.get("followup_step") or 0)
            subject, body = build_followup_copy(row)
            result = request(
                "POST",
                "/rest/v1/rpc/propose_outbound_followup",
                payload={
                    "p_root_intent_id": root_id,
                    "p_step": step,
                    "p_subject": subject,
                    "p_body_text": body,
                    "p_idempotency_key": f"followup:{root_id}:step:{step}:v1",
                    "p_proposed_by": "empire_followup_worker_v1",
                    "p_expires_at": (
                        current + timedelta(hours=18)
                    ).isoformat(),
                },
            )
            if isinstance(result, Mapping) and result.get("intent_id"):
                proposed += 1
            else:
                errors.append(f"{root_id}:proposal_returned_no_intent")
        except Exception as exc:
            errors.append(
                f"{root_id or 'unknown'}:{type(exc).__name__}:{str(exc)[:180]}"
            )

    return FollowupWorkerResult(
        due_seen=len(rows),
        proposed=proposed,
        deferred_outside_window=False,
        errors=tuple(errors),
    )
