from empire_os.typed_decision_observations import (
    reply_record_to_observation,
    reviewed_reply_to_real_eval_case,
)


def reply():
    return {
        "reply_id":"00000000-0000-0000-0000-000000000099",
        "provider_message_id":"em_1",
        "subject":"Re: proposal",
        "body_text":"Interested, tell me more.",
        "received_at":"2026-09-17T18:00:00Z",
    }


def test_reply_record_becomes_inert_eval_observation():
    r=reply_record_to_observation(reply())
    assert r["ready"] is True
    assert r["task_key"]=="reply_classification"
    assert r["untrusted_content"] is True
    assert r["executable"] is False
    assert r["crm_mutation"] is False
    assert r["outbound_send"] is False


def test_missing_reply_evidence_fails_closed():
    r=reply_record_to_observation({})
    assert r["ready"] is False
    assert "reply_id_required" in r["blockers"]
    assert r["execution_authority"]=="none"


def test_reviewed_reply_case_is_real_not_synthetic():
    r=reviewed_reply_to_real_eval_case(
        reply(),
        consensus_label="positive",
        consensus_source_ref="label-consensus:1",
    )
    assert r["ready"] is True
    assert r["case"]["synthetic_test_fixture"] is False
    assert r["case"]["ground_truth"]=="positive"
    assert r["commercial_evidence"] is False
