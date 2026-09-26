"""Phase 8 evidence-backed close-readiness assessment."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class RevenueCrmCloseReadiness:
    prospect_id: str
    ready_for_operator_close_review: bool
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    execution_authority: str = "none"
    follow_up_execution: bool = False
    payment_execution: bool = False
    crm_mutation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_close_readiness(
    prospect: Mapping[str, Any],
) -> RevenueCrmCloseReadiness:
    prospect_id = str(prospect.get("prospect_id") or "").strip()
    if not prospect_id:
        raise ValueError("canonical prospect_id required")

    blockers: list[str] = []
    evidence: list[str] = []

    conversation_id = str(prospect.get("conversation_id") or "").strip()
    conversation_state = str(
        prospect.get("conversation_state") or ""
    ).strip().lower()
    if conversation_id and conversation_state == "engaged":
        evidence.append(f"conversation:{conversation_id}")
    else:
        blockers.append("engaged_conversation_not_verified")

    closer_id = str(prospect.get("closer_case_id") or "").strip()
    closer_state = str(prospect.get("closer_state") or "").strip().lower()
    if closer_id and closer_state in {"proposal_ready", "awaiting_payment"}:
        evidence.append(f"closer_case:{closer_id}")
    else:
        blockers.append("closer_case_not_commercially_ready")

    price = prospect.get("price_cents")
    if price is not None and int(price) > 0:
        evidence.append(f"commercial_price_cents:{int(price)}")
    else:
        blockers.append("verified_commercial_price_missing")

    buyer_id = str(prospect.get("buyer_id") or "").strip()
    buyer_state = str(
        prospect.get("buyer_activation_state") or ""
    ).strip().lower()
    capacity = prospect.get("buyer_available_capacity")
    capacity_at = str(
        prospect.get("buyer_capacity_verified_at") or ""
    ).strip()

    if (
        buyer_id
        and buyer_state == "activated"
        and capacity is not None
        and int(capacity) > 0
        and capacity_at
    ):
        evidence.append(f"buyer_capacity:{buyer_id}")
    else:
        blockers.append("verified_buyer_capacity_missing")

    fulfilment_id = str(
        prospect.get("fulfilment_order_id") or ""
    ).strip()
    fulfilment_state = str(
        prospect.get("fulfilment_state") or ""
    ).strip().lower()
    if fulfilment_id and fulfilment_state in {
        "accepted",
        "invoiced",
        "delivered",
        "confirmed",
    }:
        evidence.append(f"fulfilment_order:{fulfilment_id}")
    else:
        blockers.append("fulfilment_readiness_not_verified")

    ordered = tuple(sorted(set(blockers)))
    return RevenueCrmCloseReadiness(
        prospect_id=prospect_id,
        ready_for_operator_close_review=not ordered,
        blockers=ordered,
        evidence_refs=tuple(evidence),
    )
