"""Isolated consumer runtime assembly: disabled by default and never sends."""
from __future__ import annotations

import json

import pytest

from empire_os.consumer_optin_private_runtime import (
    PrivateConsumerCredentialMaterial, build_private_consumer_backend,
    LiveReadbackConsumerRepository
)
from empire_os.consumer_optin_private_service import PrivateConsumerOptinService


SYNTHETIC_PGPASS=(
    "127.0.0.1:5432:empiredb:empire_consumer_optin_login:"+"a"*64+"\n"
).encode()
SYNTHETIC_KEYS={
    "key_reference":"consumer-key-v1",
    "email_hmac":"b"*64,
    "token_hmac":"c"*64,
    "email_encryption":"d"*64,
}


def material():
    return PrivateConsumerCredentialMaterial.from_delegated_secret_parts(
        pgpass=SYNTHETIC_PGPASS,key_document=json.dumps(SYNTHETIC_KEYS).encode()
    )


def test_no_keys_or_db_password_in_representation():
    m=material()
    assert m.key_reference=="consumer-key-v1"
    assert "a"*64 not in repr(m)
    assert "b"*64 not in repr(m)


@pytest.mark.parametrize("pgpass",[
    SYNTHETIC_PGPASS.replace(b"empiredb:",b"postgres:"),
    SYNTHETIC_PGPASS.replace(b"empire_consumer_optin_login",b"empiredb_app"),
    SYNTHETIC_PGPASS.replace(b"127.0.0.1",b"external.example"),
    SYNTHETIC_PGPASS+b"extra-line\n",
])
def test_no_wrong_login_or_secret_file_scope(pgpass):
    with pytest.raises(ValueError,match="INVALID_DELEGATED"):
        PrivateConsumerCredentialMaterial.from_delegated_secret_parts(
            pgpass=pgpass,key_document=json.dumps(SYNTHETIC_KEYS).encode()
        )


def test_no_implicit_db_queries_or_provider_sends():
    called=[]
    m=material()
    backend=build_private_consumer_backend(
        material=m,
        db_connect=lambda *a,**kw:called.append("db"),
        resend_provider=lambda **kwargs:called.append("send"),
    )
    assert isinstance(backend,PrivateConsumerOptinService)
    assert not backend.independently_ready()
    assert not backend.can_service_confirmations()
    assert not backend.can_service_withdrawals()
    assert backend.request_verification(
        email="mockup@example.test",notice_version="roofing-homeowner-updates-v1",
        consent_receipt={}
    ) is False
    assert called==[]
    assert backend._sender.provider_ready() is False


def test_owner_custody_only_still_blocks_send_and_checks_db_fresh():
    calls=[]
    backend=build_private_consumer_backend(
        material=material(),owner_approved_private_custody=True,
        db_connect=lambda *a,**kw:(_ for _ in ()).throw(
            RuntimeError("synthetic connection unavailable")
        ),
        resend_provider=lambda **kwargs:calls.append(kwargs),
    )
    assert not backend.independently_ready()
    assert not backend.can_service_withdrawals()  # DB unavailable
    assert not backend._sender.provider_ready()
    assert not calls


def test_sender_enabling_requires_multiple_independent_flags():
    m=material()
    for overrides in [
        {"owner_approved_private_custody":True},
        {"owner_approved_confirmation_send":True},
        {"sender_domain_independently_verified":True},
    ]:
        backend=build_private_consumer_backend(
            material=m,resend_scoped_key="re_synthetic_value_not_live",
            resend_provider=lambda **kw:pytest.fail("provider unexpectedly called"),
            **overrides
        )
        assert backend._sender.provider_ready() is False


def test_live_readback_repository_fails_closed_without_connection():
    repo=LiveReadbackConsumerRepository(
        connection_factory=lambda:(_ for _ in ()).throw(
            RuntimeError("db outage")
        ),
        approved_custody=True,
    )
    assert not repo.signup_writable()
    assert not repo.token_processing_writable()
