import pytest

from empire_os.closer_reply_draft import (
    POSTAL_ADDRESS,
    build_closer_reply,
)


def context(classification, body=""):
    return {
        "classification": classification,
        "reply_body_text": body,
        "root_subject": "Roofing opportunities in Austin",
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "metro": "Austin",
        "contact_name": "Jane Smith",
    }


def test_positive_reply_asks_for_capacity_without_commitment():
    draft = build_closer_reply(context("positive", "Yes, interested"))
    body = draft["body_text"]
    assert draft["subject"].startswith("Re:")
    assert "how many qualified opportunities per day" in body
    assert "email, webhook or phone" in body
    assert "price is" not in body.lower()
    assert POSTAL_ADDRESS in body
    assert "opt out" in body.lower()


def test_price_question_does_not_invent_price():
    draft = build_closer_reply(context("question", "What does it cost?"))
    body = draft["body_text"]
    assert "I don't want to invent a number" in body
    assert "territory" in body


def test_objection_keeps_pilot_bounded():
    draft = build_closer_reply(context("objection", "I'm not sure on quality"))
    assert "small bounded pilot" in draft["body_text"]
    assert "no invented volume promises" in draft["body_text"]


def test_noncommercial_classification_is_rejected():
    with pytest.raises(ValueError, match="classification"):
        build_closer_reply(context("negative"))
