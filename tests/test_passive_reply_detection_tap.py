import json

import empire_os.passive_reply_detection_tap as tap


def test_passive_reply_tap_never_persists_raw_identifiers(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        tap,
        "OUT",
        tmp_path / "tap.json",
    )

    message_id = (
        "realish-message-123456"
    )

    thread_id = (
        "realish-thread-654321"
    )

    identity = (
        "person@example.invalid"
    )

    result = tap.observe_reply(
        message_id=message_id,
        thread_id=thread_id,
        identity=identity,
        classification="positive_reply",
        direction="inbound",
    )

    persisted = (
        tap.OUT.read_text()
    )

    assert message_id not in persisted
    assert thread_id not in persisted
    assert identity not in persisted

    assert (
        result["governance"]
        ["authority"]
        == "OBSERVE"
    )

    assert (
        result["governance"]
        ["action_authority_granted"]
        is False
    )

    assert (
        result["passive_tap"]
        ["provider_invoked"]
        is False
    )

    assert (
        result["passive_tap"]
        ["mailbox_invoked"]
        is False
    )
