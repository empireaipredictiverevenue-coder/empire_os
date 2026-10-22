"""Security gates for inactive root-custodied Coder signing proposal."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from empire_os import agent_root_signing_custody as c

VALID = c.RootCustodyReceipt(
    agent_id="empire_coder", unit="empire-coder-worker.service",
    process_pid=4064398, process_origin_verified=True,
)
TIME = datetime(2026, 10, 22, 17, 38, 55, tzinfo=timezone.utc)
NONCE = "isolated_nonce_20261022_abcdefgh"


def test_disposable_key_signs_only_domain_separated_observation():
    key = Ed25519PrivateKey.generate()
    value = c._create_observe_only_receipt(VALID, nonce=NONCE,
                                            issued_at=TIME, private_key=key)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(value["public_key_hex"]))
    pub.verify(bytes.fromhex(value["signature_hex"]),
               c._canonical_observation_bytes(value["payload"]))
    assert value["payload"]["expires_at"] == "2026-10-22T17:39:55+00:00"
    assert value["payload"]["queue_authority"] is False
    assert value["payload"]["message_transport_activated"] is False
    assert value["payload"]["trusted_collaboration_registration"] is False
    assert value["no_live_a2a_message_signed"] is True
    # A cryptographic root observation can NEVER be replayed as an existing
    # DepartmentCollaboration signed message (domain separation).
    from empire_os.department_collaboration import _canonical
    with pytest.raises(InvalidSignature):
        pub.verify(bytes.fromhex(value["signature_hex"]), _canonical(value["payload"]))


@pytest.mark.parametrize("changes", [
    {"agent_id": "market_research_canary"},
    {"unit": "empire-department-cycle.service"},
    {"process_pid": True},
    {"process_pid": 0},
    {"process_origin_verified": False},
    {"tenant_scope": "tenant-abc"},
])
def test_root_signer_rejects_false_claims(changes):
    invalid=c.RootCustodyReceipt(**{**VALID.__dict__, **changes})
    with pytest.raises(c.RootSigningCustodyDenied,match="untrusted_origin_scope"):
        c._observation(invalid,nonce=NONCE,issued_at=TIME)


@pytest.mark.parametrize("nonce", ["too_short", "x"*97, "", "spaces are invalid", None])
def test_invalid_nonce_never_signed(nonce):
    with pytest.raises(c.RootSigningCustodyDenied):
        c._observation(VALID,nonce=nonce,issued_at=TIME)


@pytest.mark.parametrize("when", [datetime(2026,10,22),None,"2026-10-22"])
def test_non_timezone_aware_or_non_datetime_denied(when):
    with pytest.raises(c.RootSigningCustodyDenied):
        c._observation(VALID,nonce=NONCE,issued_at=when)


def _write_disposable_fixture(tmp_path, *, perms=0o600):
    directory=tmp_path/"root_signing_fixture"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes_raw()
    path=directory/c.PINNED_CODER_KEY
    path.write_bytes(raw)
    path.chmod(perms)
    return directory, path, key


def test_temporary_private_key_can_be_loaded_only_under_strict_custody(tmp_path):
    directory, path, generated=_write_disposable_fixture(tmp_path)
    loaded=c._safe_private_key_read(directory,expected_owner_uid=os.getuid())
    assert loaded.public_key().public_bytes_raw() == generated.public_key().public_bytes_raw()
    assert path.stat().st_mode & 0o777 == 0o600
    # The fixture is disposable. No production key, registration or socket.


@pytest.mark.parametrize("file_mode", [0o644,0o640,0o666,0o777])
def test_exposed_private_key_modes_fail_closed(tmp_path,file_mode):
    directory, _, _=_write_disposable_fixture(tmp_path,perms=file_mode)
    with pytest.raises(c.RootSigningCustodyDenied,match="not_private"):
        c._safe_private_key_read(directory,expected_owner_uid=os.getuid())


def test_world_or_group_accessible_parent_denied(tmp_path):
    directory, _, _=_write_disposable_fixture(tmp_path)
    directory.chmod(0o750)
    with pytest.raises(c.RootSigningCustodyDenied,match="directory_not_private"):
        c._safe_private_key_read(directory,expected_owner_uid=os.getuid())


def test_root_owner_mismatch_denied(tmp_path):
    directory, _, _=_write_disposable_fixture(tmp_path)
    with pytest.raises(c.RootSigningCustodyDenied,match="directory_not_private"):
        c._safe_private_key_read(directory,expected_owner_uid=os.getuid()+1000)


def test_symlinked_secret_denied(tmp_path):
    directory, path, _=_write_disposable_fixture(tmp_path)
    other=directory/"other"
    path.rename(other)
    path.symlink_to(other)
    with pytest.raises(c.RootSigningCustodyDenied,match="key_unavailable"):
        c._safe_private_key_read(directory,expected_owner_uid=os.getuid())


def test_symlinked_directory_denied(tmp_path):
    directory, _, _=_write_disposable_fixture(tmp_path)
    alias=tmp_path/"alias"
    alias.symlink_to(directory,target_is_directory=True)
    with pytest.raises(c.RootSigningCustodyDenied,match="directory_unavailable"):
        c._safe_private_key_read(alias,expected_owner_uid=os.getuid())


def test_truncated_key_and_extra_bytes_denied(tmp_path):
    directory, path, _=_write_disposable_fixture(tmp_path)
    for malformed in (b"x"*31,b"x"*33):
        path.write_bytes(malformed)
        with pytest.raises(c.RootSigningCustodyDenied,match="key_not_private"):
            c._safe_private_key_read(directory,expected_owner_uid=os.getuid())


def test_nonroot_production_entry_refuses_before_secret_or_key_access(monkeypatch):
    monkeypatch.setattr(c.os,"geteuid",lambda: 1000)
    def fail(*args,**kw):
        raise AssertionError("must not read keys")
    monkeypatch.setattr(c,"_safe_private_key_read",fail)
    with pytest.raises(c.RootSigningCustodyDenied,match="root_helper_custody_required"):
        c.create_root_origin_observation(VALID,nonce=NONCE,issued_at=TIME)


def test_root_only_loader_directory_cannot_be_client_selected(tmp_path):
    directory, path, _=_write_disposable_fixture(tmp_path)
    with pytest.raises(c.RootSigningCustodyDenied,match="unapproved_root_key_directory"):
        c._safe_private_key_read(directory,expected_owner_uid=0)


def test_key_directory_or_secret_not_created_just_by_import():
    assert c.ROOT_SIGNING_DIRECTORY == Path("/var/lib/empire-ai/agent-os-signing")
    # Not probing for private key presence; no secret material is returned.
    assert c.PINNED_CODER_KEY=="empire_coder.ed25519"


def test_pinned_public_verifier_accepts_valid_observation_only():
    key=Ed25519PrivateKey.generate()
    signed=c._create_observe_only_receipt(
        VALID, nonce=NONCE, issued_at=TIME, private_key=key,
    )
    result=c.verify_pinned_root_origin_observation(
        signed, trusted_public_key=key.public_key(),
        now=TIME.replace(second=56),
    )
    assert result["root_origin_signature_verified"] is True
    assert result["registered_agent"] is False
    assert result["nonce_replay_ledger_active"] is False
    assert result["message_transport_activated"] is False


def test_pinned_verifier_rejects_self_issued_public_key_not_in_trust_registry():
    signer=Ed25519PrivateKey.generate()
    someone_else=Ed25519PrivateKey.generate()
    signed=c._create_observe_only_receipt(
        VALID, nonce=NONCE, issued_at=TIME, private_key=signer,
    )
    with pytest.raises(c.RootSigningCustodyDenied):
        c.verify_pinned_root_origin_observation(
            signed, trusted_public_key=someone_else.public_key(),
            now=TIME.replace(second=56),
        )


@pytest.mark.parametrize("payload_patch", [
    {"agent_id": "research"},
    {"unit": "empire-department-cycle.service"},
    {"pid": 0},
    {"queue_authority": True},
    {"trusted_collaboration_registration": True},
    {"message_transport_activated": True},
    {"execution_authority": "send"},
    {"tenant_scope": "different_tenant"},
    {"schema_version": "empire.agent-os.collaboration.v1"},
])
def test_root_public_verifier_denies_modified_root_origin_scope(payload_patch):
    key=Ed25519PrivateKey.generate()
    signed=c._create_observe_only_receipt(
        VALID, nonce=NONCE, issued_at=TIME, private_key=key,
    )
    signed["payload"].update(payload_patch)
    with pytest.raises(c.RootSigningCustodyDenied):
        c.verify_pinned_root_origin_observation(
            signed, trusted_public_key=key.public_key(),
            now=TIME.replace(second=56),
        )


def test_expired_or_future_root_origin_proof_cannot_authorise():
    key=Ed25519PrivateKey.generate()
    signed=c._create_observe_only_receipt(
        VALID, nonce=NONCE, issued_at=TIME, private_key=key,
    )
    from datetime import timedelta
    for when in (TIME-timedelta(seconds=1), TIME+timedelta(seconds=60)):
        with pytest.raises(c.RootSigningCustodyDenied,match="expired_or_future"):
            c.verify_pinned_root_origin_observation(
                signed, trusted_public_key=key.public_key(), now=when,
            )


def test_unpinned_or_unspecified_root_public_key_denied():
    key=Ed25519PrivateKey.generate()
    signed=c._create_observe_only_receipt(
        VALID, nonce=NONCE, issued_at=TIME, private_key=key,
    )
    for not_pinned in (None,bytes.fromhex(signed["public_key_hex"]), "self-asserted"):
        with pytest.raises(c.RootSigningCustodyDenied, match="trusted_public_origin"):
            c.verify_pinned_root_origin_observation(
                signed, trusted_public_key=not_pinned,
                now=TIME.replace(second=56),
            )
