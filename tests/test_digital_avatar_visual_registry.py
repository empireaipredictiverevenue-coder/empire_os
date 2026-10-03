import json

import pytest

from empire_os.digital_avatar import DigitalAvatarIdentity
from empire_os.digital_avatar_visual_profile import AvatarVisualProfile
from empire_os.digital_avatar_visual_registry import (
    read_avatar_visual_registration,
    register_avatar_visual_profile,
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
        visual_profile_ref="visual:phil:v1",
    )


def profile(**overrides):
    values = {
        "profile_ref": "visual:phil:v1",
        "owner_consent_evidence_ref": "consent:phil:visual-clone:v1",
        "source_image_ref": "visual-media:phil:portrait:v1",
        "engine_avatar_id": "phil-visual-v1",
        "preferred_engine": "ditto",
        "fallback_engines": ("musetalk15",),
        "target_fps": 30,
    }
    values.update(overrides)
    return AvatarVisualProfile(**values)


def test_visual_registration_is_private_and_immutable(tmp_path):
    record = register_avatar_visual_profile(
        root=tmp_path / "visual",
        identity=identity(),
        profile=profile(),
    )
    assert record.avatar_id == "avatar-phil-v1"
    assert record.preferred_engine == "ditto"
    assert record.raw_reference_media_stored is False
    assert record.meeting_transmission_authority is False
    assert record.execution_authority == "none"

    path = tmp_path / "visual" / "visual__phil__v1.json"
    assert path.is_file()
    assert oct(path.stat().st_mode & 0o777) == "0o600"

    loaded = read_avatar_visual_registration(
        root=tmp_path / "visual",
        profile_ref="visual:phil:v1",
    )
    assert loaded["engine_avatar_id"] == "phil-visual-v1"
    assert loaded["raw_reference_media_stored"] is False


def test_same_visual_registration_is_idempotent(tmp_path):
    first = register_avatar_visual_profile(
        root=tmp_path / "visual",
        identity=identity(),
        profile=profile(),
    )
    second = register_avatar_visual_profile(
        root=tmp_path / "visual",
        identity=identity(),
        profile=profile(),
    )
    assert first.profile_sha256 == second.profile_sha256
    assert len(list((tmp_path / "visual").glob("*.json"))) == 1


def test_visual_registration_conflict_fails_closed(tmp_path):
    register_avatar_visual_profile(
        root=tmp_path / "visual",
        identity=identity(),
        profile=profile(),
    )
    with pytest.raises(ValueError, match="registration conflict"):
        register_avatar_visual_profile(
            root=tmp_path / "visual",
            identity=identity(),
            profile=profile(source_image_ref="visual-media:phil:other"),
        )


def test_tampered_visual_registration_fails_closed(tmp_path):
    register_avatar_visual_profile(
        root=tmp_path / "visual",
        identity=identity(),
        profile=profile(),
    )
    path = tmp_path / "visual" / "visual__phil__v1.json"
    payload = json.loads(path.read_text())
    payload["meeting_transmission_authority"] = True
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="transmission invariant"):
        read_avatar_visual_registration(
            root=tmp_path / "visual",
            profile_ref="visual:phil:v1",
        )


def test_visual_profile_ref_path_traversal_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="invalid visual profile ref"):
        read_avatar_visual_registration(
            root=tmp_path,
            profile_ref="../../etc/passwd",
        )
