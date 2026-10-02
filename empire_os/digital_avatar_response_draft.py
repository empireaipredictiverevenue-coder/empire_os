"""Grounded private response drafting for Empire Digital Avatar."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping, Protocol

from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_turn import (
    AvatarClaimTruth,
    AvatarTurnClaim,
    AvatarTurnDraft,
    AvatarTurnPurpose,
)


class AvatarDraftProvider(Protocol):
    provider_key: str

    def generate(self, task: AvatarRealtimeResponseTask) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class AvatarResponseDraft:
    meeting_id: str
    avatar_id: str
    text: str
    claims: tuple[AvatarTurnClaim, ...]
    provider_key: str
    source_ref: str
    blockers: tuple[str, ...]
    ready_for_human_review: bool
    mode: str = "COPILOT_PREVIEW"
    transmission_performed: bool = False
    speech_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["claims"] = [
            {
                "text": claim.text,
                "truth_class": claim.truth_class.value,
                "evidence_refs": list(claim.evidence_refs),
            }
            for claim in self.claims
        ]
        return data


def _clean_refs(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(
        dict.fromkeys(
            str(value or "").strip()
            for value in values
            if str(value or "").strip()
        )
    )


def validate_avatar_response_draft(
    *,
    task: AvatarRealtimeResponseTask,
    payload: Mapping[str, Any],
    provider_key: str,
    source_ref: str,
) -> AvatarResponseDraft:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise ValueError("avatar response draft text required")

    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise ValueError("avatar response draft claims list required")

    approved_refs = set(task.approved_evidence_refs)
    claims: list[AvatarTurnClaim] = []
    blockers: list[str] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            blockers.append("invalid_claim_shape")
            continue
        claim_text = str(raw.get("text") or "").strip()
        truth_raw = str(raw.get("truth_class") or "").strip().upper()
        refs = _clean_refs(raw.get("evidence_refs"))
        if not claim_text:
            blockers.append("claim_text_missing")
            continue
        try:
            truth = AvatarClaimTruth(truth_raw)
        except ValueError:
            blockers.append("claim_truth_class_invalid")
            continue
        if not refs:
            blockers.append("claim_evidence_missing")
        if any(ref not in approved_refs for ref in refs):
            blockers.append("claim_uses_unapproved_evidence")
        claims.append(
            AvatarTurnClaim(
                text=claim_text,
                truth_class=truth,
                evidence_refs=refs,
            )
        )


    if not claims:
        blockers.append("material_claims_missing")

    return AvatarResponseDraft(
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        text=text,
        claims=tuple(claims),
        provider_key=str(provider_key or "unknown").strip() or "unknown",
        source_ref=str(source_ref or "").strip(),
        blockers=tuple(sorted(set(blockers))),
        ready_for_human_review=not blockers,
    )


def response_draft_to_turn(
    *,
    draft: AvatarResponseDraft,
    purpose: AvatarTurnPurpose = AvatarTurnPurpose.ANSWER,
) -> AvatarTurnDraft:
    if not draft.ready_for_human_review:
        raise ValueError("response draft is not ready for human review")
    return AvatarTurnDraft(
        meeting_id=draft.meeting_id,
        avatar_id=draft.avatar_id,
        purpose=purpose,
        text=draft.text,
        claims=draft.claims,
        strategy_evidence_refs=tuple(
            dict.fromkeys(
                ref
                for claim in draft.claims
                for ref in claim.evidence_refs
            )
        ),
    )


@dataclass
class GatewayAvatarDraftProvider:
    gateway: Any
    provider_key: str = "empire_llm_gateway"

    def generate(self, task: AvatarRealtimeResponseTask) -> Mapping[str, Any]:
        if self.gateway is None or not callable(
            getattr(self.gateway, "structured_chat", None)
        ):
            raise RuntimeError("Empire LLM gateway with structured_chat required")

        system = (
            "Draft a private B2B meeting response for human approval only. "
            "Use only supplied evidence. Return JSON with keys text and claims. "
            "Each claim must contain text, truth_class and evidence_refs. "
            "truth_class must be OBSERVED, VERIFIED, INFERRED or FORECAST. "
            "Never invent pricing, outcomes, integrations, capacity or timing. "
            "Do not accept terms, request payment, move funds, or claim execution."
        )
        state = {
            "meeting_id": task.meeting_id,
            "latest_buyer_utterance": task.latest_buyer_utterance,
            "objective": task.objective,
            "recommended_action_key": task.recommended_action_key,
            "approved_evidence_refs": list(task.approved_evidence_refs),
            "commercial_terms_ref": task.commercial_terms_ref,
            "constraints": list(task.constraints),
        }
        result = self.gateway.structured_chat(
            [{"role": "user", "content": json.dumps(state, sort_keys=True)}],
            task="reasoning",
            system=system,
            temperature=0.1,
            stakes="high",
        )
        if not isinstance(result, Mapping) or result.get("error"):
            raise RuntimeError("avatar response draft provider failed")
        return result
