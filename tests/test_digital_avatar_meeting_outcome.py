import json

from empire_os.digital_avatar import (
    AvatarMeetingMode,
    AvatarMeetingSession,
    DigitalAvatarIdentity,
)
from empire_os.digital_avatar_meeting_outcome import (
    build_avatar_meeting_outcome,
    process_meeting_outcomes_once,
)
from empire_os.recall_shadow_session import (
    RecallShadowSessionManifest,
    save_recall_shadow_session,
)


def manifest(**overrides):
    values = {
        "identity": DigitalAvatarIdentity(
            avatar_id="avatar-phil-v1",
            owner_name="Phil Livesley",
            display_name="Phil — Empire AI Digital Avatar",
            organisation_name="Empire AI",
            disclosure_text="I am Phil's authorised Empire AI Digital Avatar.",
            owner_consent_evidence_ref="consent:phil:avatar:v1",
        ),
        "session": AvatarMeetingSession(
            meeting_id="meeting-001",
            avatar_id="avatar-phil-v1",
            provider="recall",
            mode=AvatarMeetingMode.SHADOW,
        ),
        "account_name": "Example Buyer",
        "objective": "qualify fit and agree next step",
        "recording_consent_evidence_ref": "consent:meeting:001",
        "conversation_id": "conversation-001",
        "opportunity_id": "opportunity-001",
    }
    values.update(overrides)
    return RecallShadowSessionManifest(**values)


def meeting_state(**overrides):
    values = {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "lifecycle_status": "done",
        "terminal": True,
        "fatal": False,
        "conversational_close_ready": True,
        "binding_execution_allowed": False,
        "human_takeover_required": False,
        "private_to_owner": True,
        "speech_execution": False,
        "chat_execution": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }
    values.update(overrides)
    return values


def test_terminal_meeting_recommends_revenue_refresh_not_fake_revenue():
    packet = build_avatar_meeting_outcome(
        manifest=manifest(),
        meeting_state=meeting_state(),
        buyer_evidence_refs=(
            "recall:bot-1:transcript-1:abc",
            "recall:bot-1:transcript-2:def",
        ),
        verification_refs=(
            "recall-verification:1",
            "recall-verification:2",
        ),
    )
    assert packet.terminal is True
    assert packet.buyer_utterance_count == 2
    assert packet.follow_up_review_recommended is True
    assert packet.conversation_bridge_recommended is True
    assert packet.predictive_revenue_refresh_recommended is True
    assert packet.close_ready_at_end is True
    assert packet.verified_commercial_outcome is False
    assert packet.revenue_recognized is False
    assert packet.cortex_customer_label_eligible is False
    assert packet.automatic_follow_up_send_allowed is False
    assert packet.commercial_execution is False
    assert packet.execution_authority == "none"


def test_fatal_meeting_never_recommends_followup_or_predictive_refresh():
    packet = build_avatar_meeting_outcome(
        manifest=manifest(),
        meeting_state=meeting_state(
            lifecycle_status="fatal",
            fatal=True,
            conversational_close_ready=False,
            human_takeover_required=True,
        ),
        buyer_evidence_refs=("recall:buyer:1",),
        verification_refs=("recall-verification:1",),
    )
    assert packet.fatal is True
    assert packet.follow_up_review_recommended is False
    assert packet.conversation_bridge_recommended is False
    assert packet.predictive_revenue_refresh_recommended is False
    assert packet.human_takeover_required is True


def write_observation(path, *, role, final=True, verified=True, text="Hello"):
    payload = {
        "meeting_id": "meeting-001",
        "verification_ref": (
            f"recall-verification:{path.stem}" if verified else ""
        ),
        "observation": {
            "meeting_id": "meeting-001",
            "external_meeting_id": "external-1",
            "platform": "zoom",
            "provider_event_id": path.stem,
            "kind": "transcript",
            "occurred_at": "2026-10-02T20:00:00+00:00",
            "evidence_ref": f"recall:meeting-001:{path.stem}",
            "speaker_ref": f"speaker:{role}",
            "speaker_name": role.title(),
            "speaker_role": role,
            "text": text,
            "is_final": final,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_outcome_worker_uses_only_final_verified_buyer_utterances(tmp_path):
    sessions = tmp_path / "sessions"
    observations = tmp_path / "observations"
    states = tmp_path / "states"
    outcomes = tmp_path / "outcomes"

    save_recall_shadow_session(
        root=sessions,
        manifest=manifest(),
    )
    states.mkdir()
    (states / "meeting-001.json").write_text(
        json.dumps(meeting_state())
    )
    write_observation(
        observations / "buyer-final.json",
        role="buyer",
        final=True,
        verified=True,
        text="Send me the proposal.",
    )
    write_observation(
        observations / "buyer-partial.json",
        role="buyer",
        final=False,
        verified=True,
    )
    write_observation(
        observations / "owner-final.json",
        role="avatar_owner",
        final=True,
        verified=True,
    )
    write_observation(
        observations / "buyer-unverified.json",
        role="buyer",
        final=True,
        verified=False,
    )

    result = process_meeting_outcomes_once(
        session_root=sessions,
        observation_root=observations,
        meeting_state_root=states,
        output_root=outcomes,
    )
    assert result["scanned"] == 1
    assert result["terminal"] == 1
    assert result["follow_up_review"] == 1
    assert result["conversation_bridge"] == 1
    assert result["predictive_refresh"] == 1
    assert result["verified_commercial_outcomes_written"] == 0
    assert result["cortex_customer_labels_written"] == 0
    assert result["automatic_follow_up_send"] is False
    assert result["failed"] == 0

    packet = json.loads(
        (outcomes / "meeting-001.json").read_text()
    )
    assert packet["buyer_utterance_count"] == 1
    assert packet["buyer_evidence_refs"] == [
        "recall:meeting-001:buyer-final"
    ]
    assert packet["verification_refs"] == [
        "recall-verification:buyer-final"
    ]
    assert packet["verified_commercial_outcome"] is False


def test_missing_canonical_links_keeps_review_private_only():
    packet = build_avatar_meeting_outcome(
        manifest=manifest(
            conversation_id=None,
            opportunity_id=None,
        ),
        meeting_state=meeting_state(),
        buyer_evidence_refs=("recall:buyer:1",),
        verification_refs=("recall-verification:1",),
    )
    assert packet.follow_up_review_recommended is True
    assert packet.conversation_bridge_recommended is False
    assert packet.predictive_revenue_refresh_recommended is False
