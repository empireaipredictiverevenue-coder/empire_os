"""Private SHADOW session manifests for Recall-backed Digital Avatar meetings."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.meeting_gateway import MeetingSpeakerRole


@dataclass(frozen=True)
class RecallShadowSessionManifest:
    identity: DigitalAvatarIdentity
    session: AvatarMeetingSession
    account_name: str
    objective: str
    recording_consent_evidence_ref: str
    proof_refs: tuple[str, ...] = ()
    commercial_terms_ref: str | None = None
    predictive_inputs: Mapping[str, Any] | None = None
    action_candidates: tuple[Mapping[str, Any], ...] = ()
    participant_roles: Mapping[str, MeetingSpeakerRole] | None = None
    mode: str = "OBSERVE"
    canonical_truth_written: bool = False
    execution_authority: str = "none"

    def validate(self) -> None:
        self.identity.validate()
        self.session.validate()
        if self.session.mode != AvatarMeetingMode.SHADOW:
            raise ValueError("Recall session manifest requires SHADOW mode")
        if self.session.avatar_id != self.identity.avatar_id:
            raise ValueError("Recall session/avatar identity mismatch")
        if not self.account_name.strip() or not self.objective.strip():
            raise ValueError("account_name and objective required")
        if not self.recording_consent_evidence_ref.strip():
            raise ValueError("recording consent evidence required")


    def as_dict(self) -> dict[str, Any]:
        roles = self.participant_roles or {}
        return {
            "schema_version": "empire.recall_shadow_session.v1",
            "identity": self.identity.as_dict(),
            "session": {
                "meeting_id": self.session.meeting_id,
                "avatar_id": self.session.avatar_id,
                "provider": self.session.provider,
                "mode": self.session.mode.value,
                "disclosure_announced": self.session.disclosure_announced,
                "participant_refs": list(self.session.participant_refs),
            },
            "account_name": self.account_name,
            "objective": self.objective,
            "recording_consent_evidence_ref": (
                self.recording_consent_evidence_ref
            ),
            "proof_refs": list(self.proof_refs),
            "commercial_terms_ref": self.commercial_terms_ref,
            "predictive_inputs": dict(self.predictive_inputs or {}),
            "action_candidates": [
                dict(row) for row in self.action_candidates
            ],
            "participant_roles": {
                key: value.value
                for key, value in roles.items()
            },
            "mode": self.mode,
            "canonical_truth_written": False,
            "execution_authority": "none",
        }


def save_recall_shadow_session(
    *,
    root: str | Path,
    manifest: RecallShadowSessionManifest,
) -> Path:
    manifest.validate()
    target_root = Path(root)
    target_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target_root, 0o700)
    target = target_root / f"{manifest.session.meeting_id}.json"
    tmp = target_root / f".{target.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(manifest.as_dict(), sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        os.chmod(target, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()
    return target


def load_recall_shadow_session(path: str | Path) -> RecallShadowSessionManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != "empire.recall_shadow_session.v1":
        raise ValueError("unsupported Recall shadow session schema")

    identity = DigitalAvatarIdentity(**raw["identity"])
    session_raw = raw["session"]
    session = AvatarMeetingSession(
        meeting_id=session_raw["meeting_id"],
        avatar_id=session_raw["avatar_id"],
        provider=session_raw["provider"],
        mode=AvatarMeetingMode(session_raw["mode"]),
        disclosure_announced=bool(session_raw.get("disclosure_announced")),
        participant_refs=tuple(session_raw.get("participant_refs") or ()),
    )
    roles = {
        str(key): MeetingSpeakerRole(value)
        for key, value in (raw.get("participant_roles") or {}).items()
    }
    manifest = RecallShadowSessionManifest(
        identity=identity,
        session=session,
        account_name=str(raw["account_name"]),
        objective=str(raw["objective"]),
        recording_consent_evidence_ref=str(
            raw["recording_consent_evidence_ref"]
        ),
        proof_refs=tuple(raw.get("proof_refs") or ()),
        commercial_terms_ref=raw.get("commercial_terms_ref"),
        predictive_inputs=dict(raw.get("predictive_inputs") or {}),
        action_candidates=tuple(raw.get("action_candidates") or ()),
        participant_roles=roles,
    )
    manifest.validate()
    return manifest
