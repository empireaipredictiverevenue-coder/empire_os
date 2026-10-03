"""Private SHADOW session manifests for Recall-backed Digital Avatar meetings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_authority import (
    AvatarCloseProposal,
    AvatarCommercialAuthorityPolicy,
)
from empire_os.meeting_gateway import MeetingSpeakerRole


@dataclass(frozen=True)
class RecallShadowSessionManifest:
    identity: DigitalAvatarIdentity
    session: AvatarMeetingSession
    account_name: str
    objective: str
    recording_consent_evidence_ref: str
    conversation_id: str | None = None
    opportunity_id: str | None = None
    proof_refs: tuple[str, ...] = ()
    commercial_terms_ref: str | None = None
    predictive_inputs: Mapping[str, Any] | None = None
    action_candidates: tuple[Mapping[str, Any], ...] = ()
    commercial_policy: AvatarCommercialAuthorityPolicy | None = None
    close_proposal: AvatarCloseProposal | None = None
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
        for name, value in (
            ("conversation_id", self.conversation_id),
            ("opportunity_id", self.opportunity_id),
        ):
            if value is not None and not str(value).strip():
                raise ValueError(f"{name} must be non-empty when provided")
        if (self.commercial_policy is None) != (self.close_proposal is None):
            raise ValueError("commercial policy and close proposal must be paired")
        if self.commercial_policy is not None:
            self.commercial_policy.validate()
            self.close_proposal.validate()
            if self.commercial_terms_ref != self.close_proposal.terms_ref:
                raise ValueError("manifest commercial terms/proposal mismatch")


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
            "conversation_id": self.conversation_id,
            "opportunity_id": self.opportunity_id,
            "proof_refs": list(self.proof_refs),
            "commercial_terms_ref": self.commercial_terms_ref,
            "predictive_inputs": dict(self.predictive_inputs or {}),
            "action_candidates": [
                dict(row) for row in self.action_candidates
            ],
            "commercial_policy": (
                asdict(self.commercial_policy)
                if self.commercial_policy is not None
                else None
            ),
            "close_proposal": (
                asdict(self.close_proposal)
                if self.close_proposal is not None
                else None
            ),
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
    policy_raw = raw.get("commercial_policy")
    proposal_raw = raw.get("close_proposal")
    policy = None
    proposal = None
    if isinstance(policy_raw, Mapping):
        policy_data = dict(policy_raw)
        policy_data["allowed_product_codes"] = tuple(
            policy_data.get("allowed_product_codes") or ()
        )
        policy_data["approved_terms_refs"] = tuple(
            policy_data.get("approved_terms_refs") or ()
        )
        policy_data["allowed_currencies"] = tuple(
            policy_data.get("allowed_currencies") or ()
        )
        policy = AvatarCommercialAuthorityPolicy(**policy_data)
    if isinstance(proposal_raw, Mapping):
        proposal_data = dict(proposal_raw)
        proposal_data["evidence_refs"] = tuple(
            proposal_data.get("evidence_refs") or ()
        )
        proposal = AvatarCloseProposal(**proposal_data)

    manifest = RecallShadowSessionManifest(
        identity=identity,
        session=session,
        account_name=str(raw["account_name"]),
        objective=str(raw["objective"]),
        recording_consent_evidence_ref=str(
            raw["recording_consent_evidence_ref"]
        ),
        conversation_id=(
            str(raw.get("conversation_id")).strip()
            if raw.get("conversation_id") is not None
            else None
        ),
        opportunity_id=(
            str(raw.get("opportunity_id")).strip()
            if raw.get("opportunity_id") is not None
            else None
        ),
        proof_refs=tuple(raw.get("proof_refs") or ()),
        commercial_terms_ref=raw.get("commercial_terms_ref"),
        predictive_inputs=dict(raw.get("predictive_inputs") or {}),
        action_candidates=tuple(raw.get("action_candidates") or ()),
        commercial_policy=policy,
        close_proposal=proposal,
        participant_roles=roles,
    )
    manifest.validate()
    return manifest
