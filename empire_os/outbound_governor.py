"""Fail-closed policy engine for Phase 3E outbound automation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

POSTAL_ADDRESS = "31 St Thomas St, Bolton, BL1 2QR, UK"
ALLOWED_CHANNELS = {"email"}
ALLOWED_EVIDENCE_SOURCES = {
    "official_site", "official_site_current", "public_record", "press_release"
}
MODES = {"OBSERVE", "ASSIST", "GUARDED_EXECUTE"}


@dataclass(frozen=True)
class OutboundGovernorPolicy:
    mode: str = "OBSERVE"
    min_contact_confidence: float = 0.70
    min_company_score: int = 70
    allow_auto_approval: bool = False
    allow_auto_send: bool = False

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"unsupported outbound governor mode: {self.mode}")
        if self.mode != "GUARDED_EXECUTE" and (
            self.allow_auto_approval or self.allow_auto_send
        ):
            raise ValueError(
                "auto approval/send requires GUARDED_EXECUTE mode"
            )


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _valid_email(value: Any) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value or "").strip()))


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _body_checks(body: str) -> list[str]:
    failures = []
    lower = body.lower()
    if not body.strip():
        return ["missing_plain_text_body"]
    if not any(token in lower for token in ("unsubscribe", "opt out", "opt-out")):
        failures.append("missing_visible_opt_out")
    if _normalize(POSTAL_ADDRESS) not in _normalize(body):
        failures.append("missing_approved_postal_footer")
    return failures


def evaluate_outbound(
    review: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
    *,
    policy: OutboundGovernorPolicy | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    policy = policy or OutboundGovernorPolicy()
    context = dict(context or {})
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    hard, repairable, evidence = [], [], []

    if review.get("actual_revenue") is not False:
        hard.append("actual_revenue_flag_must_be_false")
    if str(review.get("channel") or "") not in ALLOWED_CHANNELS:
        hard.append("unsupported_channel")
    if not _valid_email(review.get("recipient")):
        hard.append("invalid_recipient")
    if not str(review.get("subject") or "").strip():
        repairable.append("missing_subject")
    repairable.extend(_body_checks(str(review.get("body_text") or "")))

    expires_at = _parse_time(review.get("expires_at"))
    if expires_at is None:
        hard.append("invalid_expiry")
    elif expires_at <= now:
        hard.append("expired_intent")

    status = str(review.get("status") or "")
    if status not in {"pending_approval", "approved"}:
        hard.append("intent_not_actionable")


    if context.get("suppressed") is True:
        hard.append("recipient_suppressed")
    elif context.get("suppressed") is not False:
        evidence.append("suppression_status_unverified")
    if context.get("review_ready") is not True:
        evidence.append("review_readiness_unverified")
    if context.get("outreach_ready") is not True:
        evidence.append("outreach_readiness_unverified")
    if context.get("bound_to_decision_maker") is not True:
        evidence.append("decision_maker_binding_unverified")
    if str(context.get("contact_source") or "") not in ALLOWED_EVIDENCE_SOURCES:
        evidence.append("contact_source_not_approved")
    try:
        confidence = float(context.get("contact_confidence"))
    except (TypeError, ValueError):
        confidence = -1
    if confidence < policy.min_contact_confidence:
        evidence.append("contact_confidence_below_policy")
    try:
        company_score = int(context.get("company_score"))
    except (TypeError, ValueError):
        company_score = -1
    if company_score < policy.min_company_score:
        evidence.append("company_score_below_policy")

    provider_ready = context.get("provider_ready") is True
    if hard:
        action = "HOLD"
    elif repairable:
        action = "AUTO_REPAIR" if policy.mode != "OBSERVE" else "REPAIR_REQUIRED"
    elif evidence:
        action = "ESCALATE"

    elif status == "approved":
        action = (
            "AUTO_SEND_ELIGIBLE"
            if policy.mode == "GUARDED_EXECUTE" and policy.allow_auto_send and provider_ready
            else "READY_FOR_SEND_GATE"
        )
    elif policy.mode == "GUARDED_EXECUTE" and policy.allow_auto_approval:
        action = "AUTO_APPROVE_ELIGIBLE"
    else:
        action = "READY_FOR_HUMAN_APPROVAL"

    mutation_authorized = policy.mode != "OBSERVE" and action in {
        "AUTO_REPAIR", "AUTO_APPROVE_ELIGIBLE", "AUTO_SEND_ELIGIBLE"
    }
    return {
        "decision": action,
        "mode": policy.mode,
        "mutation_authorized": mutation_authorized,
        "intent_id": str(review.get("intent_id") or ""),
        "status": status,
        "checks": {
            "hard_holds": hard,
            "repairable": repairable,
            "evidence_holds": evidence,
            "provider_ready": provider_ready,
        },
    }
