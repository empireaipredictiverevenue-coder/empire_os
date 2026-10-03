import pytest

from empire_os.digital_avatar_meeting_memory import AvatarMeetingMemory
from empire_os.digital_avatar_response_task import build_realtime_response_task
from empire_os.digital_avatar_strategy import AvatarMeetingStrategyPacket


def memory(latest=True):
    buyer = {
        "text": "Can you prove the ROI?",
        "evidence_ref": "meeting:turn:7",
    } if latest else None
    return AvatarMeetingMemory(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        participant_refs=("speaker:buyer",),
        transcript_turns=(),
        buyer_turns=(),
        evidence_refs=("meeting:turn:7",),
        latest_buyer_utterance=buyer,
    )


def strategy():
    return AvatarMeetingStrategyPacket(
        meeting_id="meeting-001",
        avatar_id="avatar-phil-v1",
        account_name="Example Buyer",
        objective="qualify fit and agree next step",
        buyer_signal_summary="Observed buyer utterance",
        proof_refs=("evidence:case:7",),
        commercial_terms_ref="terms:pilot:v1",
        predictive_revenue={"status": "AVAILABLE"},
        next_best_action={"action_key": "present_verified_case_evidence"},
        blockers=(),
    )


def test_response_task_is_private_and_non_speaking():
    task = build_realtime_response_task(
        memory=memory(),
        strategy=strategy(),
    )
    assert task.latest_buyer_utterance == "Can you prove the ROI?"
    assert task.recommended_action_key == "present_verified_case_evidence"
    assert "meeting:turn:7" in task.approved_evidence_refs
    assert "evidence:case:7" in task.approved_evidence_refs
    assert "terms:pilot:v1" in task.approved_evidence_refs
    assert task.requires_human_approval is True
    assert task.speech_execution_allowed is False
    assert task.execution_authority == "none"


def test_response_task_contains_non_fabrication_constraints():
    task = build_realtime_response_task(
        memory=memory(),
        strategy=strategy(),
    )
    joined = " ".join(task.constraints).lower()
    assert "do not invent" in joined
    assert "actual revenue" in joined
    assert "do not speak or send" in joined


def test_response_task_requires_observed_buyer_utterance():
    with pytest.raises(ValueError, match="observed buyer utterance required"):
        build_realtime_response_task(
            memory=memory(latest=False),
            strategy=strategy(),
        )


def test_response_task_rejects_cross_meeting_context():
    other = strategy()
    other = AvatarMeetingStrategyPacket(
        meeting_id="meeting-999",
        avatar_id=other.avatar_id,
        account_name=other.account_name,
        objective=other.objective,
        buyer_signal_summary=other.buyer_signal_summary,
        proof_refs=other.proof_refs,
        commercial_terms_ref=other.commercial_terms_ref,
        predictive_revenue=other.predictive_revenue,
        next_best_action=other.next_best_action,
        blockers=other.blockers,
    )
    with pytest.raises(ValueError, match="meeting memory/strategy identity mismatch"):
        build_realtime_response_task(
            memory=memory(),
            strategy=other,
        )
