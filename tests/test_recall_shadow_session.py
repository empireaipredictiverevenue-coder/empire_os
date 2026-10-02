import json
import pytest

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.meeting_gateway import MeetingSpeakerRole
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    load_recall_shadow_session,
    save_recall_shadow_session,
)


def manifest():
    return RecallShadowSessionManifest(
        identity=DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        session=AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        recording_consent_evidence_ref="consent:meeting:001",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_inputs={"demand": 0.8},
        action_candidates=({"action_key": "ask_deadline"},),
        participant_roles={
            "recall-participant:7": MeetingSpeakerRole.BUYER,
        },
    )


def test_manifest_round_trips_privately(tmp_path):
    path = save_recall_shadow_session(
        root=tmp_path / "sessions",
        manifest=manifest(),
    )
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    assert oct(path.parent.stat().st_mode & 0o777) == "0o700"

    loaded = load_recall_shadow_session(path)
    assert loaded.session.meeting_id == "meeting-001"
    assert loaded.identity.avatar_id == "avatar-phil-v1"
    assert loaded.account_name == "Example Buyer"
    assert loaded.participant_roles["recall-participant:7"] == (
        MeetingSpeakerRole.BUYER
    )
    raw = json.loads(path.read_text())
    assert raw["canonical_truth_written"] is False
    assert raw["execution_authority"] == "none"


def test_manifest_requires_shadow_mode():
    bad = manifest()
    object.__setattr__(
        bad,
        "session",
        AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.COPILOT,
        ),
    )
    with pytest.raises(ValueError, match="requires SHADOW mode"):
        bad.validate()


def test_manifest_rejects_avatar_identity_mismatch():
    bad = manifest()
    object.__setattr__(
        bad,
        "session",
        AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="other-avatar",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
    )
    with pytest.raises(ValueError, match="session/avatar identity mismatch"):
        bad.validate()


def test_manifest_requires_recording_consent():
    bad = manifest()
    object.__setattr__(bad, "recording_consent_evidence_ref", "")
    with pytest.raises(ValueError, match="recording consent evidence"):
        bad.validate()
