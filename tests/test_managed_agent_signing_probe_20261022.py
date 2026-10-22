"""Read-only Coder oneshot signer: synthetic process and key tests."""
from __future__ import annotations

import copy
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from empire_os import managed_agent_signing_probe as probe
from scripts import run_graphify_coder_worker_20261020 as coder


def _real_signed_receipt(monkeypatch):
    from empire_os import agent_runtime_identity_evidence as identity
    def fake_preflight(credential, *, agent_id):
        assert isinstance(credential, identity.ManagedWorkerSigningIdentity)
        assert agent_id == "empire_coder"
        return {
            "local_process_scope_attested": True,
            "trusted_broker_key_registration_still_required": True,
            "signing_mode": "ed25519_private_in_managed_process",
        }
    monkeypatch.setattr(probe, "preflight_local_managed_binding", fake_preflight)
    return probe.inspect_actual_coder_signing_process()


def test_ephemeral_signer_receipt_is_valid_but_not_trusted_registration(monkeypatch):
    receipt = _real_signed_receipt(monkeypatch)
    assert probe.verify_untrusted_signing_receipt(receipt)
    assert receipt["trusted_broker_registration"] is False
    assert receipt["persistent_agent_credential"] is False
    assert receipt["production_collaboration_activated"] is False
    assert receipt["external_outbound"] is False
    assert not any("private" in str(k).lower() for k in receipt)


@pytest.mark.parametrize("tamper", [
    ("payload", "agent_id", "fake_worker"),
    ("payload", "unit", "fake.service"),
    ("payload", "scope", "PERSISTENT_TRUSTED_KEY"),
    ("payload", "privileged_action", True),
    ("root", "trusted_broker_registration", True),
    ("root", "production_collaboration_activated", True),
    ("root", "external_outbound", True),
])
def test_tampered_or_authority_claiming_receipts_fail(monkeypatch, tamper):
    receipt = _real_signed_receipt(monkeypatch)
    changed = copy.deepcopy(receipt)
    kind, key, value = tamper
    if kind == "payload":
        changed["payload"][key] = value
    else:
        changed[key] = value
    assert probe.verify_untrusted_signing_receipt(changed) is False


def test_signature_from_other_key_is_rejected(monkeypatch):
    receipt = _real_signed_receipt(monkeypatch)
    fake = Ed25519PrivateKey.generate()
    payload = receipt["payload"]
    receipt["signature_hex"] = fake.sign(
        json.dumps(payload, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode()
    ).hex()
    assert probe.verify_untrusted_signing_receipt(receipt) is False


def test_probe_must_have_genuine_main_process_preflight(monkeypatch):
    monkeypatch.setattr(
        probe, "preflight_local_managed_binding",
        lambda *_args, **_kw: {
            "local_process_scope_attested": False,
            "trusted_broker_key_registration_still_required": True,
            "signing_mode": "ed25519_private_in_managed_process",
        },
    )
    with pytest.raises(ValueError, match="not_attested"):
        probe.inspect_actual_coder_signing_process()


def test_hook_disabled_by_default_does_not_load_probe(monkeypatch):
    monkeypatch.delenv("EMPIRE_CODER_AGENT_SIGNING_OBSERVE", raising=False)
    monkeypatch.setattr(
        probe, "inspect_actual_coder_signing_process",
        lambda: (_ for _ in ()).throw(AssertionError("must not probe")),
    )
    coder._observe_existing_worker_signing_identity()


def test_opt_in_hook_logs_only_public_evidence(monkeypatch, capsys):
    monkeypatch.setenv("EMPIRE_CODER_AGENT_SIGNING_OBSERVE", "1")
    public = _real_signed_receipt(monkeypatch)
    monkeypatch.setattr(probe, "inspect_actual_coder_signing_process", lambda: public)
    coder._observe_existing_worker_signing_identity()
    log = capsys.readouterr().err
    assert log.startswith("CODER_AGENT_SIGNATURE_OBSERVE ")
    report = json.loads(log.split(" ", 1)[1])
    assert probe.verify_untrusted_signing_receipt(report)
    assert "private_key" not in log
    assert "public_key_hex" in log


def test_hook_failure_cannot_block_existing_coder(monkeypatch, capsys):
    monkeypatch.setenv("EMPIRE_CODER_AGENT_SIGNING_OBSERVE", "1")
    monkeypatch.setattr(
        probe, "inspect_actual_coder_signing_process",
        lambda: (_ for _ in ()).throw(ValueError("private-bad-token")),
    )
    coder._observe_existing_worker_signing_identity()
    log = capsys.readouterr().err
    assert log.strip() == "CODER_AGENT_SIGNATURE_OBSERVE_HELD_ValueError"
    assert "private-bad-token" not in log


def test_exact_one_shot_private_marker_consumes_once(tmp_path):
    marker = tmp_path / "coder_probe.flag"
    marker.write_bytes(
        b"EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1" + bytes((10,))
    )
    marker.chmod(0o600)
    assert coder._consume_once_identity_probe_marker(marker) is True
    assert not marker.exists()
    assert coder._consume_once_identity_probe_marker(marker) is False


@pytest.mark.parametrize("invalid", ["mode", "body", "symlink"])
def test_untrusted_one_shot_probe_marker_is_rejected(tmp_path, invalid):
    marker = tmp_path / "coder_probe.flag"
    value = b"EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1" + bytes((10,))
    if invalid == "symlink":
        target = tmp_path / "real_file"
        target.write_bytes(value)
        target.chmod(0o600)
        marker.symlink_to(target)
    else:
        marker.write_bytes(b"incorrect" if invalid == "body" else value)
        marker.chmod(0o644 if invalid == "mode" else 0o600)
    assert coder._consume_once_identity_probe_marker(marker) is False
    assert marker.exists()


def test_opt_in_one_shot_file_can_run_without_env(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("EMPIRE_CODER_AGENT_SIGNING_OBSERVE", raising=False)
    marker = tmp_path / "coder_probe.flag"
    marker.write_bytes(
        b"EMPIRE_CODER_PROCESS_SIGNING_OBSERVE_ONLY_V1" + bytes((10,))
    )
    marker.chmod(0o600)
    original_consume = coder._consume_once_identity_probe_marker
    monkeypatch.setattr(coder, "_consume_once_identity_probe_marker",
                        lambda: original_consume(marker))
    receipt = _real_signed_receipt(monkeypatch)
    monkeypatch.setattr(probe, "inspect_actual_coder_signing_process",
                        lambda: receipt)
    coder._observe_existing_worker_signing_identity()
    logged = capsys.readouterr().err
    assert "CODER_AGENT_SIGNATURE_OBSERVE " in logged
    assert not marker.exists()
    assert "private_key" not in logged
