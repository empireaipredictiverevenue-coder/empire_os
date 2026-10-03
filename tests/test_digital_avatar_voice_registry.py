import json

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_voice_profile import AvatarVoiceProfile
from empire_os.digital_avatar_voice_registry import (
    read_avatar_voice_registration,
    register_avatar_voice_profile,
)


def identity():
    return DigitalAvatarIdentity(
        avatar_id="avatar-phil-v1",
        owner_name="Phil Livesley",
        display_name="Phil — Empire AI Digital Avatar",
        organisation_name="Empire AI",
        disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
        owner_consent_evidence_ref="consent:phil:avatar:v1",
        voice_profile_ref="voice:phil:v1",
    )


def profile(*, engine_voice_id="phil-v1"):
    return AvatarVoiceProfile(
        profile_ref="voice:phil:v1",
        owner_consent_evidence_ref="consent:phil:voice-clone:v1",
        reference_audio_ref="voice-media:phil:clean-ref:v1",
        reference_transcript_ref="voice-transcript:phil:clean-ref:v1",
        engine_voice_id=engine_voice_id,
        clone_required=True,
        preferred_engine="cosyvoice3",
        language="en",
    )


def test_registration_persists_only_refs_and_no_raw_media(tmp_path):
    registration = register_avatar_voice_profile(
        root=tmp_path / "voices",
        identity=identity(),
        profile=profile(),
    )
    assert registration.engine_voice_id == "phil-v1"
    assert registration.raw_reference_media_stored is False
    assert registration.meeting_transmission_authority is False
    path = tmp_path / "voices" / "voice__phil__v1.json"
    assert path.is_file()
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    raw = path.read_text()
    assert "raw_reference_audio" not in raw
    assert "execution_authority" in raw


def test_registration_is_idempotent_but_profile_change_conflicts(tmp_path):
    root = tmp_path / "voices"
    first = register_avatar_voice_profile(
        root=root,
        identity=identity(),
        profile=profile(),
    )
    second = register_avatar_voice_profile(
        root=root,
        identity=identity(),
        profile=profile(),
    )
    assert first.profile_sha256 == second.profile_sha256

    with pytest.raises(ValueError, match="registration conflict"):
        register_avatar_voice_profile(
            root=root,
            identity=identity(),
            profile=profile(engine_voice_id="phil-v2"),
        )


def test_registration_reader_fails_closed_on_authority_drift(tmp_path):
    root = tmp_path / "voices"
    register_avatar_voice_profile(
        root=root,
        identity=identity(),
        profile=profile(),
    )
    path = root / "voice__phil__v1.json"
    payload = json.loads(path.read_text())
    payload["meeting_transmission_authority"] = True
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="transmission invariant"):
        read_avatar_voice_registration(
            root=root,
            profile_ref="voice:phil:v1",
        )


def test_registration_reader_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="invalid voice profile ref"):
        read_avatar_voice_registration(
            root=tmp_path,
            profile_ref="../../secret",
        )
