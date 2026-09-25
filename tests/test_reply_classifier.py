from empire_os.reply_classifier import classify_reply_text


def test_unsubscribe_is_high_confidence_and_auto_applied():
    result = classify_reply_text("Please remove me from your list.")
    assert result == {
        "classification": "unsubscribe",
        "confidence": 0.99,
        "auto_apply": True,
    }


def test_positive_and_question_are_distinguished():
    positive = classify_reply_text("Interested, send the outline.")
    assert positive["classification"] == "positive"
    assert positive["auto_apply"] is True

    question = classify_reply_text("How does this work?")
    assert question["classification"] == "question"
    assert question["auto_apply"] is True


def test_ambiguous_text_stays_other_and_is_not_auto_applied():
    result = classify_reply_text("Received.")
    assert result["classification"] == "other"
    assert result["auto_apply"] is False


def test_standalone_stop_is_unsubscribe():
    result = classify_reply_text("Stop")
    assert result == {
        "classification": "unsubscribe",
        "confidence": 0.99,
        "auto_apply": True,
    }

