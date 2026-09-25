from empire_os.empire_mailbox import build_mailbox, mailbox_thread


def test_intent_alias_groups_sent_and_received_into_one_thread():
    sent = [{
        "id": "sent-1",
        "from": "Phil <phil@mail.empire-ai.co.uk>",
        "to": ["buyer@example.com"],
        "reply_to": ["reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk"],
        "subject": "Pilot",
        "created_at": "2026-09-25T10:00:00+00:00",
        "last_event": "delivered",
    }]
    received = [{
        "id": "in-1",
        "from": "buyer@example.com",
        "to": ["reply+11111111-2222-3333-4444-555555555555@mail.empire-ai.co.uk"],
        "subject": "Re: Pilot",
        "received_at": "2026-09-25T11:00:00+00:00",
        "text": "Interested - send it",
    }]

    mailbox = build_mailbox(sent, received)
    assert mailbox["thread_count"] == 1
    row = mailbox["threads"][0]
    assert row["intent_id"] == "11111111-2222-3333-4444-555555555555"
    assert row["classification"] == "positive"
    assert row["commercial_status"] == "replied"
    assert row["next_action"] == "prepare_reply"
    assert row["event_count"] == 2


def test_unknown_thread_identity_fails_closed_to_provider_email_id():
    mailbox = build_mailbox([{
        "id": "legacy-1",
        "to": ["buyer@example.com"],
        "subject": "Legacy",
        "last_event": "delivered",
    }], [])
    row = mailbox["threads"][0]
    assert row["intent_id"] is None
    assert row["thread_id"] == "email:legacy-1"


def test_unsubscribe_is_visibly_suppressed_and_not_actionable():
    mailbox = build_mailbox([], [{
        "id": "in-2",
        "from": "buyer@example.com",
        "to": ["reply+aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee@mail.empire-ai.co.uk"],
        "subject": "Re: hello",
        "text": "Please opt out",
    }])
    row = mailbox["threads"][0]
    assert row["classification"] == "unsubscribe"
    assert row["suppressed"] is True
    assert row["next_action"] == "suppress_and_close"
    assert mailbox_thread(mailbox, row["thread_id"]) is not None
