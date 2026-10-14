"""Gmail metadata snippets are not full verified buyer responses."""
from empire_os.empire_mailbox import normalise_received_email


def test_partial_positive_preview_never_promotes_to_positive_reply():
    observation = normalise_received_email({
        "id": "workspace:inbox:abcdef1234567890",
        "to": ["reply@mail.empire-ai.co.uk"],
        "subject": "Re: Hello", "text": "Yes, interested, send more",
        "body_preview_only": True,
        "message_id": "<untrusted@example.com>",
        "created_at": "2026-10-14T08:22:00+00:00",
    }, provider="google_workspace")
    assert observation["classification"] == "unknown"
    assert observation["message_id"] is None
    assert observation["untrusted_content"] is True
    assert observation["occurred_at"] == "2026-10-14T08:22:00+00:00"
