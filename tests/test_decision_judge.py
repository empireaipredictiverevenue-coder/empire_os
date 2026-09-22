from empire_os.decision_judge import (
    ACTION_CLARIFY,
    ACTION_CONTINUE,
    ACTION_HUMAN_HANDOFF,
    ACTION_STOP,
    INTENT_FOLLOW_UP,
    INTENT_OPT_OUT,
    INTENT_PAYMENT,
    EmpireDecisionJudge,
    TranscriptCandidate,
)


def test_explicit_opt_out_fails_closed_and_requests_suppression():
    result = EmpireDecisionJudge().judge_text(
        "Please do not call me again.",
        source="whisper",
    )

    assert result.action == ACTION_STOP
    assert result.intent == INTENT_OPT_OUT
    assert result.suppression_requested is True
    assert result.commercial_authority is False
    assert "contact_suppression_required" in result.risk_flags


def test_observed_no_now_asr_flip_requires_clarification():
    result = EmpireDecisionJudge().judge_text(
        "Empire Voice Lab local speech readiness test. "
        "Now external voice vendor is being used.",
        source="whisper",
    )

    assert result.action == ACTION_CLARIFY
    assert result.requires_clarification is True
    assert "possible_negation_flip" in result.risk_flags


def test_conflicting_asr_numbers_require_clarification():
    result = EmpireDecisionJudge().judge_candidates([
        TranscriptCandidate(
            source="zipformer",
            text="The pilot is 1500 pounds.",
        ),
        TranscriptCandidate(
            source="whisper",
            text="The pilot is 500 pounds.",
        ),
    ])

    assert result.action == ACTION_CLARIFY
    assert result.requires_clarification is True
    assert "asr_disagreement:numbers" in result.risk_flags
    assert "asr_disagreement:money" in result.risk_flags


def test_follow_up_permission_can_continue_to_closer():
    result = EmpireDecisionJudge().judge_text(
        "Yes, send me the brief by email.",
        source="zipformer",
    )

    assert result.action == ACTION_CONTINUE
    assert result.intent == INTENT_FOLLOW_UP
    assert result.route == "closer"
    assert result.commercial_authority is False


def test_binding_payment_language_requires_human_handoff():
    result = EmpireDecisionJudge().judge_text(
        "I accept the terms and I'll pay now.",
        source="whisper",
    )

    assert result.action == ACTION_HUMAN_HANDOFF
    assert result.intent == INTENT_PAYMENT
    assert result.route == "commercial_handoff"
    assert "commercial_authority_required" in result.risk_flags


def test_judge_returns_typed_fast_decision_envelope():
    result = EmpireDecisionJudge().judge_text(
        "Tell me more about the opportunity.",
        source="zipformer",
    )
    payload = result.to_dict()

    assert result.action == ACTION_CONTINUE
    assert payload["schema_version"] == "empire.decision_judge.v1"
    assert payload["candidate_count"] == 1
    assert payload["latency_ms"] >= 0
    assert payload["signals"]["sources"] == ["zipformer"]
