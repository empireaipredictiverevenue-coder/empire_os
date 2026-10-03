"""Bounded evidence content for grounded Digital Avatar response drafting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask
from empire_os.digital_avatar_turn import AvatarClaimTruth


class AvatarEvidenceResolver(Protocol):
    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        ...


@dataclass(frozen=True)
class AvatarEvidenceItem:
    evidence_ref: str
    content: str
    truth_class: AvatarClaimTruth
    source_kind: str
    provenance: str
    verified: bool

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["truth_class"] = self.truth_class.value
        return data


@dataclass(frozen=True)
class AvatarEvidencePack:
    meeting_id: str
    avatar_id: str
    items: tuple[AvatarEvidenceItem, ...]
    unresolved_refs: tuple[str, ...]
    ready_for_drafting: bool
    mode: str = "COPILOT_PREVIEW"
    private_to_owner: bool = True
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "items": [item.as_dict() for item in self.items],
        }


def _truth(value: Any) -> AvatarClaimTruth:
    raw = str(value or "").strip().upper()
    try:
        return AvatarClaimTruth(raw)
    except ValueError as exc:
        raise ValueError("evidence truth_class invalid") from exc


def _normalized_item(
    *,
    requested_ref: str,
    payload: Mapping[str, Any],
) -> AvatarEvidenceItem:
    resolved_ref = str(payload.get("evidence_ref") or "").strip()
    if resolved_ref != requested_ref:
        raise ValueError("resolved evidence ref mismatch")
    content = " ".join(str(payload.get("content") or "").split())
    if not content:
        raise ValueError("resolved evidence content required")
    source_kind = str(payload.get("source_kind") or "").strip()
    provenance = str(payload.get("provenance") or "").strip()
    if not source_kind or not provenance:
        raise ValueError("resolved evidence provenance required")
    truth = _truth(payload.get("truth_class"))
    verified = payload.get("verified") is True
    if truth in {AvatarClaimTruth.OBSERVED, AvatarClaimTruth.VERIFIED} and not verified:
        raise ValueError("observed/verified evidence requires verified provenance")
    return AvatarEvidenceItem(
        evidence_ref=resolved_ref,
        content=content,
        truth_class=truth,
        source_kind=source_kind,
        provenance=provenance,
        verified=verified,
    )


def build_avatar_evidence_pack(
    *,
    task: AvatarRealtimeResponseTask,
    resolver: AvatarEvidenceResolver,
) -> AvatarEvidencePack:
    items: list[AvatarEvidenceItem] = []
    unresolved: list[str] = []
    for ref in task.approved_evidence_refs:
        try:
            payload = resolver.resolve(ref)
            if payload is None:
                unresolved.append(ref)
                continue
            items.append(
                _normalized_item(
                    requested_ref=ref,
                    payload=payload,
                )
            )
        except (ValueError, TypeError, KeyError):
            unresolved.append(ref)

    unique_unresolved = tuple(dict.fromkeys(unresolved))
    return AvatarEvidencePack(
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        items=tuple(items),
        unresolved_refs=unique_unresolved,
        ready_for_drafting=bool(items) and not unique_unresolved,
    )
