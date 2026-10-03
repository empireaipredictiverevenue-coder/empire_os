from datetime import datetime, timedelta, timezone

import pytest

from empire_os.digital_avatar_presence_token import (
    issue_avatar_presence_token,
    verify_avatar_presence_token,
)


NOW = datetime(2026, 10, 2, 19, 30, tzinfo=timezone.utc)
SECRET = "presence-secret-" + ("x" * 32)


def issue(**overrides):
    values = {
        "secret": SECRET,
        "meeting_id": "meeting-001",
        "avatar_id": "avatar-phil-v1",
        "bot_id": "bot-123",
        "now": NOW,
        "ttl_seconds": 300,
        "nonce": "nonce-test-1",
    }
    values.update(overrides)
    return issue_avatar_presence_token(**values)


def test_presence_token_is_short_lived_and_identity_bound():
    issued = issue()
    assert issued.raw_secret_persisted is False
    assert issued.execution_authority == "none"
    claims = verify_avatar_presence_token(
        secret=SECRET,
        token=issued.token,
        now=NOW + timedelta(seconds=10),
        expected_meeting_id="meeting-001",
        expected_avatar_id="avatar-phil-v1",
        expected_bot_id="bot-123",
    )
    assert claims.mode == "copilot"
    assert claims.expires_at - claims.issued_at == 300


def test_presence_token_tampering_is_rejected():
    issued = issue()
    token = issued.token[:-1] + ("A" if issued.token[-1] != "A" else "B")
    with pytest.raises(ValueError, match="signature invalid"):
        verify_avatar_presence_token(
            secret=SECRET,
            token=token,
            now=NOW,
        )


def test_presence_token_expiry_is_enforced():
    issued = issue(ttl_seconds=30)
    with pytest.raises(ValueError, match="expired"):
        verify_avatar_presence_token(
            secret=SECRET,
            token=issued.token,
            now=NOW + timedelta(seconds=30),
        )


def test_presence_token_identity_mismatch_fails_closed():
    issued = issue()
    with pytest.raises(ValueError, match="bot mismatch"):
        verify_avatar_presence_token(
            secret=SECRET,
            token=issued.token,
            now=NOW,
            expected_bot_id="bot-other",
        )


@pytest.mark.parametrize("ttl", [1, 29, 3601])
def test_presence_token_ttl_is_bounded(ttl):
    with pytest.raises(ValueError, match="ttl must be between"):
        issue(ttl_seconds=ttl)


def test_presence_signing_secret_has_minimum_strength():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        issue(secret="too-short")
