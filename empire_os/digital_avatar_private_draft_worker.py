"""Materialize grounded private Digital Avatar drafts without transmission."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.digital_avatar_evidence_pack import (
    AvatarEvidenceResolver,
    build_avatar_evidence_pack,
)
from empire_os.digital_avatar_response_draft import (
    AvatarResponseDraft,
    GroundedAvatarDraftProvider,
    generate_validated_grounded_avatar_response_draft,
)
from empire_os.digital_avatar_response_task import AvatarRealtimeResponseTask


@dataclass(frozen=True)
class AvatarPrivateDraftMaterialization:
    meeting_id: str
    avatar_id: str
    task_sha256: str
    status: str
    unresolved_refs: tuple[str, ...]
    draft: AvatarResponseDraft | None
    provider_call_performed: bool
    duplicate: bool
    specialist_context_blockers: tuple[str, ...] = ()
    private_to_owner: bool = True
    human_approval_required: bool = True
    transmission_performed: bool = False
    speech_execution_allowed: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["draft"] = self.draft.as_dict() if self.draft else None
        return data


def _specialist_context(raw: Any) -> tuple[Mapping[str, Any], ...]:
    if raw in (None, ()):
        return ()
    if not isinstance(raw, (list, tuple)):
        raise ValueError("Digital Avatar specialist context invalid")
    items: list[Mapping[str, Any]] = []
    for value in raw:
        if not isinstance(value, Mapping):
            raise ValueError("Digital Avatar specialist context item invalid")
        domain = str(value.get("domain") or "").strip()
        source = str(value.get("source_component") or "").strip()
        truth = str(value.get("truth_class") or "").strip().upper()
        if not domain or not source:
            raise ValueError("Digital Avatar specialist context identity invalid")
        if truth not in {"OBSERVED", "VERIFIED", "INFERRED", "FORECAST"}:
            raise ValueError("Digital Avatar specialist context truth invalid")
        items.append({
            "domain": domain,
            "source_component": source,
            "summary": str(value.get("summary") or "").strip(),
            "truth_class": truth,
            "evidence_refs": [
                str(ref).strip()
                for ref in (value.get("evidence_refs") or ())
                if str(ref).strip()
            ],
            "available": value.get("available") is True,
            "blockers": [
                str(blocker).strip()
                for blocker in (value.get("blockers") or ())
                if str(blocker).strip()
            ],
        })
    return tuple(items)


def _response_task(raw: Mapping[str, Any]) -> AvatarRealtimeResponseTask:
    return AvatarRealtimeResponseTask(
        meeting_id=str(raw.get("meeting_id") or "").strip(),
        avatar_id=str(raw.get("avatar_id") or "").strip(),
        latest_buyer_utterance=str(
            raw.get("latest_buyer_utterance") or ""
        ).strip(),
        objective=str(raw.get("objective") or "").strip(),
        recommended_action_key=(
            str(raw.get("recommended_action_key") or "").strip() or None
        ),
        approved_evidence_refs=tuple(
            str(value).strip()
            for value in (raw.get("approved_evidence_refs") or ())
            if str(value).strip()
        ),
        commercial_terms_ref=(
            str(raw.get("commercial_terms_ref") or "").strip() or None
        ),
        constraints=tuple(
            str(value).strip()
            for value in (raw.get("constraints") or ())
            if str(value).strip()
        ),
        specialist_context=_specialist_context(
            raw.get("specialist_context")
        ),
        specialist_context_ready=bool(
            raw.get("specialist_context_ready", True)
        ),
        specialist_context_blockers=tuple(
            str(value).strip()
            for value in (raw.get("specialist_context_blockers") or ())
            if str(value).strip()
        ),
        mode=str(raw.get("mode") or "COPILOT_PREVIEW"),
        output_channel=str(raw.get("output_channel") or "private_draft"),
        requires_human_approval=bool(
            raw.get("requires_human_approval", True)
        ),
        speech_execution_allowed=bool(
            raw.get("speech_execution_allowed", False)
        ),
        execution_authority=str(
            raw.get("execution_authority") or "none"
        ),
    )


def _load_task_from_guidance(path: str | Path) -> AvatarRealtimeResponseTask:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Digital Avatar guidance snapshot unreadable") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("Digital Avatar guidance snapshot must be an object")
    if raw.get("private_to_owner") is not True:
        raise ValueError("Digital Avatar guidance privacy invariant violated")
    if raw.get("speech_execution") is not False:
        raise ValueError("Digital Avatar guidance speech invariant violated")
    if str(raw.get("execution_authority") or "").lower() != "none":
        raise ValueError("Digital Avatar guidance authority invariant violated")

    response_task = raw.get("response_task")
    if not isinstance(response_task, Mapping):
        raise ValueError("Digital Avatar response task not available")
    task = _response_task(response_task)
    if not task.meeting_id or not task.avatar_id:
        raise ValueError("Digital Avatar response task identity incomplete")
    if task.requires_human_approval is not True:
        raise ValueError("Digital Avatar response task approval invariant violated")
    if task.speech_execution_allowed is not False:
        raise ValueError("Digital Avatar response task speech invariant violated")
    if task.execution_authority.lower() != "none":
        raise ValueError("Digital Avatar response task authority invariant violated")
    return task


def _digest(task: AvatarRealtimeResponseTask, pack: Any) -> str:
    payload = {
        "task": task.as_dict(),
        "evidence_pack": pack.as_dict(),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def materialize_private_avatar_draft(
    *,
    guidance_path: str | Path,
    evidence_resolver: AvatarEvidenceResolver,
    provider: GroundedAvatarDraftProvider,
    output_root: str | Path,
) -> AvatarPrivateDraftMaterialization:
    task = _load_task_from_guidance(guidance_path)
    pack = build_avatar_evidence_pack(
        task=task,
        resolver=evidence_resolver,
    )
    digest = _digest(task, pack)

    meeting_root = Path(output_root) / task.meeting_id
    target = meeting_root / f"{digest}.json"
    latest = meeting_root / "latest.json"
    if target.is_file():
        return AvatarPrivateDraftMaterialization(
            meeting_id=task.meeting_id,
            avatar_id=task.avatar_id,
            task_sha256=digest,
            status="existing",
            unresolved_refs=pack.unresolved_refs,
            draft=None,
            provider_call_performed=False,
            duplicate=True,
        )

    if not task.specialist_context_ready:
        result = AvatarPrivateDraftMaterialization(
            meeting_id=task.meeting_id,
            avatar_id=task.avatar_id,
            task_sha256=digest,
            status="blocked_specialist_context",
            unresolved_refs=pack.unresolved_refs,
            draft=None,
            provider_call_performed=False,
            duplicate=False,
            specialist_context_blockers=(
                task.specialist_context_blockers
            ),
        )
        _atomic_json(target, result.as_dict())
        _atomic_json(latest, result.as_dict())
        return result

    if not pack.ready_for_drafting:
        result = AvatarPrivateDraftMaterialization(
            meeting_id=task.meeting_id,
            avatar_id=task.avatar_id,
            task_sha256=digest,
            status="blocked_evidence",
            unresolved_refs=pack.unresolved_refs,
            draft=None,
            provider_call_performed=False,
            duplicate=False,
        )
        _atomic_json(target, result.as_dict())
        _atomic_json(latest, result.as_dict())
        return result

    draft = generate_validated_grounded_avatar_response_draft(
        task=task,
        evidence_pack=pack,
        provider=provider,
        source_ref=f"avatar-private-draft:{task.meeting_id}:{digest[:24]}",
    )
    status = (
        "ready_for_human_review"
        if draft.ready_for_human_review
        else "blocked_validation"
    )
    result = AvatarPrivateDraftMaterialization(
        meeting_id=task.meeting_id,
        avatar_id=task.avatar_id,
        task_sha256=digest,
        status=status,
        unresolved_refs=(),
        draft=draft,
        provider_call_performed=True,
        duplicate=False,
    )
    _atomic_json(target, result.as_dict())
    _atomic_json(latest, result.as_dict())
    return result
