"""Governed Phase 6 A2A commercial-intent foundation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

ALLOWED_COMMERCE_CAPABILITIES = frozenset({
    "commerce.quote.request",
    "commerce.negotiation.start",
    "commerce.task.create",
})


@dataclass(frozen=True)
class CommercialIntent:
    agent_id: str
    key_id: str
    identity_nonce: str
    identity_issued_at: str
    capability: str
    idempotency_key: str
    request: Mapping[str, Any]
    evidence: Mapping[str, Any]

    def validate(self) -> None:
        for name, value in (
            ("agent_id", self.agent_id),
            ("key_id", self.key_id),
            ("identity_nonce", self.identity_nonce),
            ("identity_issued_at", self.identity_issued_at),
            ("idempotency_key", self.idempotency_key),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} required")
        if self.capability not in ALLOWED_COMMERCE_CAPABILITIES:
            raise ValueError("unsupported commerce capability")
        if not isinstance(self.request, Mapping):
            raise ValueError("request must be an object")
        if not isinstance(self.evidence, Mapping):
            raise ValueError("evidence must be an object")


@dataclass(frozen=True)
class CommercialIntentDecision:
    accepted: bool
    status: str
    intent_id: str | None
    agent_id: str
    capability: str
    reason: str
    human_approval_required: bool = True
    execution_authority: str = "none"
    payment_authority: bool = False
    allocation_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_intent_record(
    row: Mapping[str, Any],
) -> CommercialIntentDecision:
    status = str(row.get("status") or "").strip()
    if status not in {"pending_approval", "existing"}:
        raise ValueError("unexpected commercial intent status")
    return CommercialIntentDecision(
        accepted=True,
        status=status,
        intent_id=str(row.get("intent_id") or "") or None,
        agent_id=str(row.get("agent_id") or ""),
        capability=str(row.get("capability") or ""),
        reason=(
            "authenticated_intent_recorded"
            if status == "pending_approval"
            else "idempotent_existing_intent"
        ),
    )
