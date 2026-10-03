import json
import pytest

from empire_os.digital_avatar_runtime_read import (
    read_avatar_activation_state,
    read_avatar_guidance,
    read_avatar_meeting_state,
    read_avatar_meeting_outcome,
    read_avatar_private_draft,
    read_avatar_runtime_state,
    validate_meeting_id,
)


def test_valid_meeting_id():
    assert validate_meeting_id("meeting-001") == "meeting-001"


@pytest.mark.parametrize(
    "value",
    ["", "../secret", "/absolute", "space id", "a" * 129],
)
def test_invalid_meeting_id_is_rejected(value):
    with pytest.raises(ValueError, match="invalid meeting_id"):
        validate_meeting_id(value)


def test_guidance_read_is_identity_bound(tmp_path):
    root = tmp_path / "guidance"
    root.mkdir()
    (root / "meeting-001.json").write_text(
        json.dumps({
            "meeting_id": "meeting-001",
            "private_to_owner": True,
            "speech_execution": False,
            "execution_authority": "none",
        })
    )
    result = read_avatar_guidance(
        root=root,
        meeting_id="meeting-001",
    )
    assert result["private_to_owner"] is True
    assert result["execution_authority"] == "none"


def test_missing_guidance_returns_none(tmp_path):
    assert read_avatar_guidance(
        root=tmp_path,
        meeting_id="meeting-001",
    ) is None


def test_identity_mismatch_fails_closed(tmp_path):
    root = tmp_path / "guidance"
    root.mkdir()
    (root / "meeting-001.json").write_text(
        '{"meeting_id":"meeting-999"}'
    )
    with pytest.raises(ValueError, match="identity mismatch"):
        read_avatar_guidance(
            root=root,
            meeting_id="meeting-001",
        )

def test_unsafe_guidance_invariants_fail_closed(tmp_path):
    root = tmp_path / "guidance"
    root.mkdir()
    path = root / "meeting-001.json"
    unsafe = {
        "meeting_id": "meeting-001",
        "private_to_owner": False,
        "speech_execution": False,
        "execution_authority": "none",
    }
    path.write_text(json.dumps(unsafe))
    with pytest.raises(ValueError, match="privacy invariant"):
        read_avatar_guidance(root=root, meeting_id="meeting-001")

    unsafe["private_to_owner"] = True
    unsafe["speech_execution"] = True
    path.write_text(json.dumps(unsafe))
    with pytest.raises(ValueError, match="speech invariant"):
        read_avatar_guidance(root=root, meeting_id="meeting-001")

    unsafe["speech_execution"] = False
    unsafe["execution_authority"] = "live"
    path.write_text(json.dumps(unsafe))
    with pytest.raises(ValueError, match="authority invariant"):
        read_avatar_guidance(root=root, meeting_id="meeting-001")


def runtime_state_payload():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "status_code": "in_call_recording",
        "sub_code": None,
        "updated_at": "2026-10-02T18:00:00+00:00",
        "event_count": 3,
        "waiting_room": False,
        "joined_meeting": True,
        "recording_active": True,
        "terminal": False,
        "fatal": False,
        "evidence_refs": ["recall-verification:evt:1:abc"],
        "truth_class": "VERIFIED",
        "polling_performed": False,
        "speech_execution": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }


def test_runtime_state_read_is_identity_bound_and_nonexecuting(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "meeting-001.json").write_text(json.dumps(runtime_state_payload()))
    result = read_avatar_runtime_state(root=root, meeting_id="meeting-001")
    assert result["status_code"] == "in_call_recording"
    assert result["recording_active"] is True
    assert result["polling_performed"] is False
    assert result["speech_execution"] is False
    assert result["execution_authority"] == "none"


def test_missing_runtime_state_returns_none(tmp_path):
    assert read_avatar_runtime_state(
        root=tmp_path,
        meeting_id="meeting-001",
    ) is None


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("truth_class", "INFERRED", "truth invariant"),
        ("polling_performed", True, "polling invariant"),
        ("speech_execution", True, "speech invariant"),
        ("commercial_execution", True, "commercial invariant"),
        ("execution_authority", "live", "authority invariant"),
    ],
)
def test_unsafe_runtime_state_fails_closed(tmp_path, key, value, message):
    root = tmp_path / "runtime"
    root.mkdir()
    payload = runtime_state_payload()
    payload[key] = value
    (root / "meeting-001.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        read_avatar_runtime_state(root=root, meeting_id="meeting-001")


def meeting_state_payload():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "lifecycle_status": "in_call_recording",
        "lifecycle_sub_code": None,
        "joined_meeting": True,
        "waiting_room": False,
        "recording_active": True,
        "terminal": False,
        "fatal": False,
        "observation_count": 3,
        "latest_buyer_utterance": {
            "text": "Can you show me proof?",
            "evidence_ref": "recall:evidence:1",
        },
        "recommended_action": {
            "action_key": "present_verified_case_evidence",
        },
        "response_task": {
            "requires_human_approval": True,
            "speech_execution_allowed": False,
        },
        "human_takeover_required": False,
        "blockers": [],
        "mode": "OBSERVE",
        "private_to_owner": True,
        "speech_execution": False,
        "chat_execution": False,
        "commercial_execution": False,
        "execution_authority": "none",
    }


def test_meeting_state_read_is_private_and_nonexecuting(tmp_path):
    root = tmp_path / "meeting_state"
    root.mkdir()
    (root / "meeting-001.json").write_text(json.dumps(meeting_state_payload()))
    result = read_avatar_meeting_state(root=root, meeting_id="meeting-001")
    assert result["recording_active"] is True
    assert result["private_to_owner"] is True
    assert result["speech_execution"] is False
    assert result["chat_execution"] is False
    assert result["commercial_execution"] is False
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("private_to_owner", False, "privacy invariant"),
        ("speech_execution", True, "invariant"),
        ("chat_execution", True, "invariant"),
        ("commercial_execution", True, "invariant"),
        ("execution_authority", "live", "authority invariant"),
    ],
)
def test_unsafe_meeting_state_fails_closed(tmp_path, key, value, message):
    root = tmp_path / "meeting_state"
    root.mkdir()
    payload = meeting_state_payload()
    payload[key] = value
    (root / "meeting-001.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        read_avatar_meeting_state(root=root, meeting_id="meeting-001")


def activation_state_payload():
    return {
        "schema_version": "empire.recall_shadow_activation.v1",
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "region": "eu-central-1",
        "plan_sha256": "abc123",
        "approval_evidence_ref": "approval:shadow:meeting-001:v1",
        "approved_by": "Phil Livesley",
        "approved_at": "2026-10-02T18:00:00+00:00",
        "expires_at": "2026-10-02T20:00:00+00:00",
        "session_filename": "meeting-001.json",
        "mode": "SHADOW",
        "live_join_prepared": True,
        "live_join_performed": False,
        "provider_api_call_started": False,
        "provider_api_call_performed": False,
        "execution_state": "prepared",
        "provider_bot_id": None,
        "provider_status": None,
        "speech_execution": False,
        "chat_send_execution": False,
        "commercial_execution": False,
        "join_execution_authority": "shadow_join_only",
        "execution_authority": "none",
    }


def test_activation_state_read_is_private_nonexecuting(tmp_path):
    root = tmp_path / "activation"
    root.mkdir()
    (root / "meeting-001.json").write_text(
        json.dumps(activation_state_payload())
    )
    result = read_avatar_activation_state(
        root=root,
        meeting_id="meeting-001",
    )
    assert result["execution_state"] == "prepared"
    assert result["provider_api_call_started"] is False
    assert result["live_join_performed"] is False
    assert result["speech_execution"] is False
    assert result["execution_authority"] == "none"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("speech_execution", True, "invariant"),
        ("chat_send_execution", True, "invariant"),
        ("commercial_execution", True, "invariant"),
        ("execution_authority", "live", "authority invariant"),
    ],
)
def test_unsafe_activation_state_fails_closed(tmp_path, key, value, message):
    root = tmp_path / "activation"
    root.mkdir()
    payload = activation_state_payload()
    payload[key] = value
    (root / "meeting-001.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        read_avatar_activation_state(
            root=root,
            meeting_id="meeting-001",
        )


def private_draft_payload():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "task_sha256": "a" * 64,
        "status": "ready_for_human_review",
        "unresolved_refs": [],
        "draft": {
            "meeting_id": "meeting-001",
            "avatar_id": "avatar-phil-v1",
            "text": "Yes. I can show you the verified case evidence.",
            "claims": [],
            "provider_key": "test",
            "source_ref": "draft:test",
            "blockers": [],
            "ready_for_human_review": True,
            "mode": "COPILOT_PREVIEW",
            "transmission_performed": False,
            "speech_execution_allowed": False,
            "execution_authority": "none",
        },
        "provider_call_performed": True,
        "duplicate": False,
        "private_to_owner": True,
        "human_approval_required": True,
        "transmission_performed": False,
        "speech_execution_allowed": False,
        "execution_authority": "none",
    }


def test_private_draft_read_is_owner_private_and_nontransmitting(tmp_path):
    root = tmp_path / "private_drafts"
    target = root / "meeting-001"
    target.mkdir(parents=True)
    (target / "latest.json").write_text(
        json.dumps(private_draft_payload())
    )

    value = read_avatar_private_draft(
        root=root,
        meeting_id="meeting-001",
    )
    assert value["status"] == "ready_for_human_review"
    assert value["private_to_owner"] is True
    assert value["human_approval_required"] is True
    assert value["transmission_performed"] is False
    assert value["speech_execution_allowed"] is False
    assert value["execution_authority"] == "none"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("private_to_owner", False, "privacy invariant"),
        ("human_approval_required", False, "approval invariant"),
        ("transmission_performed", True, "transmission invariant"),
        ("speech_execution_allowed", True, "speech invariant"),
        ("execution_authority", "live", "authority invariant"),
    ],
)
def test_unsafe_private_draft_fails_closed(
    tmp_path,
    key,
    value,
    message,
):
    root = tmp_path / "private_drafts"
    target = root / "meeting-001"
    target.mkdir(parents=True)
    payload = private_draft_payload()
    payload[key] = value
    (target / "latest.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        read_avatar_private_draft(
            root=root,
            meeting_id="meeting-001",
        )


def meeting_outcome_payload():
    return {
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "account_name": "Example Buyer",
        "conversation_id": "conversation-001",
        "opportunity_id": "opportunity-001",
        "lifecycle_status": "done",
        "terminal": True,
        "fatal": False,
        "buyer_utterance_count": 1,
        "buyer_evidence_refs": ["recall:buyer:1"],
        "verification_refs": ["recall-verification:1"],
        "close_ready_at_end": True,
        "human_takeover_required": False,
        "follow_up_review_recommended": True,
        "conversation_bridge_recommended": True,
        "predictive_revenue_refresh_recommended": True,
        "verified_commercial_outcome": False,
        "revenue_recognized": False,
        "cortex_customer_label_eligible": False,
        "automatic_follow_up_send_allowed": False,
        "private_to_owner": True,
        "speech_execution": False,
        "commercial_execution": False,
        "payment_execution": False,
        "execution_authority": "none",
    }


def test_meeting_outcome_read_preserves_nonrevenue_invariants(tmp_path):
    root = tmp_path / "outcomes"
    root.mkdir()
    (root / "meeting-001.json").write_text(
        json.dumps(meeting_outcome_payload())
    )
    value = read_avatar_meeting_outcome(
        root=root,
        meeting_id="meeting-001",
    )
    assert value["predictive_revenue_refresh_recommended"] is True
    assert value["verified_commercial_outcome"] is False
    assert value["revenue_recognized"] is False
    assert value["cortex_customer_label_eligible"] is False
    assert value["automatic_follow_up_send_allowed"] is False
    assert value["execution_authority"] == "none"


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        (
            "verified_commercial_outcome",
            True,
            "verified_commercial_outcome invariant",
        ),
        ("revenue_recognized", True, "revenue_recognized invariant"),
        (
            "cortex_customer_label_eligible",
            True,
            "cortex_customer_label_eligible invariant",
        ),
        (
            "automatic_follow_up_send_allowed",
            True,
            "automatic_follow_up_send_allowed invariant",
        ),
        ("commercial_execution", True, "commercial_execution invariant"),
        ("payment_execution", True, "payment_execution invariant"),
    ],
)
def test_meeting_outcome_read_fails_closed_on_false_revenue_or_execution(
    tmp_path,
    key,
    value,
    message,
):
    root = tmp_path / "outcomes"
    root.mkdir()
    payload = meeting_outcome_payload()
    payload[key] = value
    (root / "meeting-001.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match=message):
        read_avatar_meeting_outcome(
            root=root,
            meeting_id="meeting-001",
        )
