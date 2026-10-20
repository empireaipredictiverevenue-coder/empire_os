"""Pure 256-bit token and privacy tests. No database or mail providers."""
from datetime import datetime, timedelta, timezone
import secrets
import pytest

from empire_os.consumer_optin_token_security import (
    canonical_email, email_lookup_hmac, issue_token, token_fingerprint,
    review_token_use,
)

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
KEY_CONFIRM = bytes.fromhex("12" * 32)
KEY_LOOKUP = bytes.fromhex("34" * 32)
OTHER_KEY = bytes.fromhex("56" * 32)


def test_email_lookup_keyed_not_plain_sha_256():
    one=email_lookup_hmac("homeowner@EXAMPLE.TEST", key=KEY_LOOKUP)
    two=email_lookup_hmac("homeowner@example.test", key=KEY_LOOKUP)
    other=email_lookup_hmac("homeowner@example.test", key=OTHER_KEY)
    assert one == two
    assert one != other
    assert len(one) == 64
    assert "homeowner" not in one


def test_email_local_part_not_provider_canonicalized_away():
    assert canonical_email("H+offers@example.TEST") == "H+offers@example.test"
    assert email_lookup_hmac("H+offers@example.TEST",key=KEY_LOOKUP) != (
        email_lookup_hmac("H@example.test",key=KEY_LOOKUP)
    )
    for invalid in (" person@example.test","two@@example.test",
                    "abc example@test.com","a@example.test\n"):
        with pytest.raises(ValueError):
            canonical_email(invalid)


@pytest.mark.parametrize("action,ttl", [
    ("confirm",timedelta(minutes=45)),
    ("unsubscribe",timedelta(days=14)),
])
def test_issued_tokens_are_purpose_scoped_high_entropy_and_not_replayable(action,ttl):
    receipt=issue_token(action=action,key=KEY_CONFIRM,now=NOW,ttl=ttl)
    assert len(receipt.token)==43
    assert len(receipt.token_hmac)==64
    assert receipt.token not in receipt.token_hmac
    assert receipt.expires_at==NOW+ttl
    result=review_token_use(
        action=action,presented_token=receipt.token,
        expected_hmac=receipt.token_hmac,key=KEY_CONFIRM,
        expires_at=receipt.expires_at,now=NOW+timedelta(seconds=2),
        already_consumed=False,currently_suppressed=False,
        subscription_state=("pending_verification" if action=="confirm" else "verified")
    )
    assert result == (
        "ALLOW_ATOMIC_CONFIRMATION" if action == "confirm"
        else "ALLOW_ATOMIC_UNSUBSCRIBE"
    )
    same=dict(action=action,presented_token=receipt.token,
        expected_hmac=receipt.token_hmac,key=KEY_CONFIRM,
        expires_at=receipt.expires_at,now=NOW+timedelta(seconds=2),
        subscription_state="verified" if action=="unsubscribe" else "pending_verification")
    assert review_token_use(**same,already_consumed=True,currently_suppressed=False) == "DENIED_REPLAY_OR_SUPPRESSION"
    assert review_token_use(**same,already_consumed=False,currently_suppressed=True) == "DENIED_REPLAY_OR_SUPPRESSION"
    assert review_token_use(**{**same,"now":receipt.expires_at},
        already_consumed=False,currently_suppressed=False) == "DENIED_EXPIRED"
    assert review_token_use(**{**same,"presented_token":secrets.token_urlsafe(32)},
        already_consumed=False,currently_suppressed=False) == "DENIED_INVALID_TOKEN"
    assert review_token_use(**{**same,"key":OTHER_KEY},
        already_consumed=False,currently_suppressed=False) == "DENIED_INVALID_TOKEN"


def test_confirmation_cannot_reuse_unsubscribe_token():
    token=issue_token(action="confirm",key=KEY_CONFIRM,now=NOW,ttl=timedelta(minutes=30))
    assert token_fingerprint(token.token,action="unsubscribe",key=KEY_CONFIRM) != token.token_hmac
    assert review_token_use(
        action="unsubscribe",presented_token=token.token,
        expected_hmac=token.token_hmac,key=KEY_CONFIRM,expires_at=token.expires_at,
        now=NOW,already_consumed=False,currently_suppressed=False,
        subscription_state="pending_verification"
    )=="DENIED_INVALID_TOKEN"


def test_confirm_does_not_create_buyer_referral_permission():
    token=issue_token(action="confirm",key=KEY_CONFIRM,now=NOW,ttl=timedelta(minutes=30))
    result=review_token_use(
        action="confirm",presented_token=token.token,
        expected_hmac=token.token_hmac,key=KEY_CONFIRM,expires_at=token.expires_at,
        now=NOW,already_consumed=False,currently_suppressed=False,
        subscription_state="pending_verification"
    )
    assert result=="ALLOW_ATOMIC_CONFIRMATION"
    assert "BUYER" not in result
    assert "REFERRAL" not in result


def test_invalid_key_clock_ttl_and_unknown_purpose_are_denied():
    for kw in (
        {"key":b"a"*12},
        {"now":NOW.replace(tzinfo=None)},
        {"ttl":timedelta(days=60)},
        {"ttl":timedelta(seconds=0)},
        {"action":"buyer_share"},
    ):
        opts=dict(action="confirm",key=KEY_CONFIRM,now=NOW,ttl=timedelta(hours=1))
        opts.update(kw)
        with pytest.raises(ValueError):
            issue_token(**opts)
