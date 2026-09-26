from empire_os.buyer_reply_operations_agent import (
    analyze_buyer_reply,
    buyer_reply_ops_status,
)


def test_unsubscribe_requires_suppression_but_never_sends():
    row = analyze_buyer_reply("Please unsubscribe me.")
    assert row.classification == "unsubscribe"
    assert row.suppression_required is True
    assert row.draft_eligible is False
    assert row.outbound_send_authority is False
    assert row.actual_revenue is False


def test_question_escalates_to_reasoning_and_draft_candidate():
    row = analyze_buyer_reply("Can you send pricing?")
    assert row.classification == "question"
    assert row.reasoning_required is True
    assert row.draft_eligible is True
    assert row.review_required is True
    assert row.outbound_send_authority is False


def test_laya_shadow_never_overrides_deterministic_decision():
    row = analyze_buyer_reply(
        "Can you explain the offer?",
        laya_shadow={
            "label": "unsubscribe",
            "confidence": 0.99,
            "accepted_for_shadow_analysis": True,
            "reason": "accepted_specialist_shadow_candidate",
        },
    )
    assert row.classification == "question"
    assert row.specialist_shadow["label"] == "unsubscribe"
    assert row.specialist_shadow["authority"] == "shadow_only"
    assert row.suppression_required is False


def test_quoted_history_is_not_used_for_classification():
    row = analyze_buyer_reply(
        "Sounds interesting.\n\nOn Thu someone wrote:\n> unsubscribe"
    )
    assert row.classification == "positive"


def test_status_declares_zero_consequential_authority():
    row = buyer_reply_ops_status()
    assert row["outbound_send_authority"] is False
    assert row["payment_authority"] is False
    assert row["revenue_recognition_authority"] is False
    assert row["execution_authority"] == "none"
