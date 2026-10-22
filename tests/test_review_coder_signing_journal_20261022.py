"""Trust the kernel-assigned journal metadata, never an agent assertion."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta

import pytest

from empire_os import managed_agent_signing_probe as probe
from scripts import review_coder_signing_journal_20261022 as audit


def source_entry(monkeypatch):
    monkeypatch.setattr(
        probe, "preflight_local_managed_binding",
        lambda *_a, **_kw: {
            "local_process_scope_attested": True,
            "trusted_broker_key_registration_still_required": True,
            "signing_mode": "ed25519_private_in_managed_process",
        },
    )
    proof = probe.inspect_actual_coder_signing_process()
    stamp = datetime.fromisoformat(proof["payload"]["timestamp_utc"]) + timedelta(seconds=1)
    item = {
        "MESSAGE": audit.PREFIX + json.dumps(proof, sort_keys=True),
        "_SYSTEMD_UNIT": audit.UNIT,
        "_PID": str(proof["payload"]["pid"]),
        "_UID": "1000",
        "_SYSTEMD_CGROUP": f"/system.slice/{audit.UNIT}",
        "_TRANSPORT": "stdout",
        "_SYSTEMD_INVOCATION_ID": "a" * 32,
        "__REALTIME_TIMESTAMP": str(int(stamp.timestamp() * 1_000_000)),
    }
    return item


def test_genuine_signed_receipt_and_systemd_journal_provenance(monkeypatch):
    entry = source_entry(monkeypatch)
    result = audit.inspect_journal_entry(entry, 1000)
    assert result["status"] == "VERIFIED_HISTORICAL_MANAGED_CODER_EPHEMERAL_SIGNATURE"
    assert result["ed25519_signature_verified"] is True
    assert result["trusted_journal_pid_uid_cgroup_unit_match"] is True
    assert result["self_issued_ephemeral_signing_only"] is True
    assert result["trusted_agent_registration_verified"] is False
    assert result["live_message_transport_verified"] is False
    assert "private" not in str(result).lower()


@pytest.mark.parametrize("key,value", [
    ("_PID", "123456789"),
    ("_UID", "0"),
    ("_SYSTEMD_CGROUP", "/system.slice/other.service"),
    ("_SYSTEMD_UNIT", "empire-department-cycle.service"),
    ("_TRANSPORT", "fake"),
    ("_SYSTEMD_INVOCATION_ID", "bad"),
    ("__REALTIME_TIMESTAMP", "-1"),
])
def test_untrusted_journal_provenance_fails_closed(monkeypatch, key, value):
    entry = source_entry(monkeypatch)
    entry[key] = value
    assert audit.inspect_journal_entry(entry, 1000) is None


def test_other_agent_cannot_forge_body_despite_valid_journal(monkeypatch):
    entry = source_entry(monkeypatch)
    content = json.loads(entry["MESSAGE"][len(audit.PREFIX):])
    content["payload"]["agent_id"] = "other_agent"
    entry["MESSAGE"] = audit.PREFIX + json.dumps(content)
    assert audit.inspect_journal_entry(entry, 1000) is None


def test_no_signature_alone_is_enough_without_original_journal(monkeypatch):
    entry = source_entry(monkeypatch)
    assert audit.inspect_journal_entry(
        {"MESSAGE": entry["MESSAGE"]}, 1000
    ) is None


def test_readonly_summary_does_not_claim_live_agent_registration(monkeypatch):
    entry = source_entry(monkeypatch)
    result = audit.inspect_coder_signing_journal(journal_entries=[entry])
    assert result["verified_process_signing_observation_count"] == 1
    assert result["registered_agents"] == 0
    assert result["execution_authority"] == "none"
    assert result["production_queue_modified"] is False


def test_missing_journal_evidence_fails_closed():
    result = audit.inspect_coder_signing_journal(journal_entries=[])
    assert result["status"] == "NO_VALID_MANAGED_CODER_SIGNING_JOURNAL_PROOF"
    assert result["registered_agents"] == 0


def test_readonly_cli_requires_exact_authority_flag(monkeypatch, capsys):
    monkeypatch.setattr(audit.sys, "argv", ["audit"])
    assert audit.main() == 2
    assert "EXACT_READ_ONLY" in capsys.readouterr().out
