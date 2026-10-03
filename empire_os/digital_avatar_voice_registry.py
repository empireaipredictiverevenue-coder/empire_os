"""Private immutable registry for Digital Avatar clone-voice identities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Mapping

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_voice_profile import AvatarVoiceProfile


@dataclass(frozen=True)
class AvatarVoiceRegistration:
    profile_ref: str
    avatar_id: str
    owner_consent_evidence_ref: str
    voice_consent_evidence_ref: str
    preferred_engine: str
    engine_voice_id: str
    reference_audio_ref: str
    reference_transcript_ref: str
    language: str
    profile_sha256: str
    schema_version: str = "empire.avatar_voice_registration.v1"
    raw_reference_media_stored: bool = False
    meeting_transmission_authority: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical(
    *,
    identity: DigitalAvatarIdentity,
    profile: AvatarVoiceProfile,
) -> dict[str, Any]:
    return {
        "profile_ref": profile.profile_ref,
        "avatar_id": identity.avatar_id,
        "owner_consent_evidence_ref": identity.owner_consent_evidence_ref,
        "voice_consent_evidence_ref": profile.owner_consent_evidence_ref,
        "preferred_engine": profile.preferred_engine,
        "engine_voice_id": profile.engine_voice_id,
        "reference_audio_ref": profile.reference_audio_ref,
        "reference_transcript_ref": profile.reference_transcript_ref,
        "language": profile.language,
        "clone_required": profile.clone_required,
    }


def voice_profile_sha256(
    *,
    identity: DigitalAvatarIdentity,
    profile: AvatarVoiceProfile,
) -> str:
    encoded = json.dumps(
        _canonical(identity=identity, profile=profile),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def build_voice_registration(
    *,
    identity: DigitalAvatarIdentity,
    profile: AvatarVoiceProfile,
) -> AvatarVoiceRegistration:
    identity.validate()
    profile.validate()
    if identity.voice_profile_ref != profile.profile_ref:
        raise ValueError("avatar identity/voice profile mismatch")
    if not profile.clone_required:
        raise ValueError("clone voice registration requires clone profile")
    return AvatarVoiceRegistration(
        profile_ref=profile.profile_ref,
        avatar_id=identity.avatar_id,
        owner_consent_evidence_ref=identity.owner_consent_evidence_ref,
        voice_consent_evidence_ref=profile.owner_consent_evidence_ref,
        preferred_engine=profile.preferred_engine,
        engine_voice_id=str(profile.engine_voice_id),
        reference_audio_ref=str(profile.reference_audio_ref),
        reference_transcript_ref=str(profile.reference_transcript_ref),
        language=profile.language,
        profile_sha256=voice_profile_sha256(
            identity=identity,
            profile=profile,
        ),
    )


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.parent / f".{path.name}.{os.getpid()}.tmp"
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
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


def register_avatar_voice_profile(
    *,
    root: str | Path,
    identity: DigitalAvatarIdentity,
    profile: AvatarVoiceProfile,
) -> AvatarVoiceRegistration:
    registration = build_voice_registration(
        identity=identity,
        profile=profile,
    )
    target = Path(root) / f"{registration.profile_ref.replace(':', '__')}.json"
    if target.is_file():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("existing avatar voice registration unreadable") from exc
        if not isinstance(current, Mapping):
            raise ValueError("existing avatar voice registration invalid")
        if current.get("profile_sha256") != registration.profile_sha256:
            raise ValueError("avatar voice registration conflict")
        return registration

    _atomic_json(target, registration.as_dict())
    return registration


def read_avatar_voice_registration(
    *,
    root: str | Path,
    profile_ref: str,
) -> dict[str, Any] | None:
    clean = str(profile_ref or "").strip()
    if not clean or any(ch in clean for ch in ("/", "\\", "\x00")):
        raise ValueError("invalid voice profile ref")
    target = Path(root) / f"{clean.replace(':', '__')}.json"
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("avatar voice registration unreadable") from exc
    if not isinstance(raw, dict):
        raise ValueError("avatar voice registration must be object")
    if raw.get("schema_version") != "empire.avatar_voice_registration.v1":
        raise ValueError("avatar voice registration schema invalid")
    if raw.get("profile_ref") != clean:
        raise ValueError("avatar voice registration identity mismatch")
    if raw.get("raw_reference_media_stored") is not False:
        raise ValueError("avatar voice registration media invariant violated")
    if raw.get("meeting_transmission_authority") is not False:
        raise ValueError("avatar voice registration transmission invariant violated")
    if str(raw.get("execution_authority") or "").lower() != "none":
        raise ValueError("avatar voice registration authority invariant violated")
    return raw
