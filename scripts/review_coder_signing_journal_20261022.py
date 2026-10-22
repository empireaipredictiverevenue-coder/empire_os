#!/usr/bin/env python3
"""Verify actual managed Coder *historical* signed observation.

Read-only systemd journal inspection. Journal kernel metadata + valid
ephemeral Ed25519 signature do NOT establish an ongoing enrolled agent.
No token, account, queue, LLM, broker, email, network or database access.
"""
from __future__ import annotations

import json
import pwd
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

from empire_os.managed_agent_signing_probe import verify_untrusted_signing_receipt

UNIT = "empire-coder-worker.service"
PREFIX = "CODER_AGENT_SIGNATURE_OBSERVE "
MAX_JOURNAL_LINES = 50


def inspect_journal_entry(entry: Mapping[str, Any], expected_uid: int) -> dict[str, Any] | None:
    message = entry.get("MESSAGE")
    if not isinstance(message, str) or not message.startswith(PREFIX):
        return None
    try:
        receipt = json.loads(message[len(PREFIX):])
    except (ValueError, TypeError):
        return None
    if not verify_untrusted_signing_receipt(receipt):
        return None
    payload = receipt["payload"]
    try:
        observed_us = int(entry["__REALTIME_TIMESTAMP"])
        signed_at = datetime.fromisoformat(payload["timestamp_utc"])
        if signed_at.tzinfo is None:
            return None
        signed_us = int(signed_at.timestamp() * 1_000_000)
    except (ValueError, KeyError, TypeError, OverflowError):
        return None
    if not 0 <= observed_us - signed_us <= 120 * 1_000_000:
        return None
    journal_pid = entry.get("_PID")
    if str(journal_pid) != str(payload["pid"]):
        return None
    if (
        entry.get("_SYSTEMD_UNIT") != UNIT
        or str(entry.get("_UID")) != str(expected_uid)
        or entry.get("_SYSTEMD_CGROUP") != f"/system.slice/{UNIT}"
        or entry.get("_TRANSPORT") != "stdout"
        or not isinstance(entry.get("_SYSTEMD_INVOCATION_ID"), str)
        or len(entry["_SYSTEMD_INVOCATION_ID"]) != 32
        or any(char not in "0123456789abcdef" for char in entry["_SYSTEMD_INVOCATION_ID"])
    ):
        return None
    return {
        "status": "VERIFIED_HISTORICAL_MANAGED_CODER_EPHEMERAL_SIGNATURE",
        "observed_at_utc": datetime.fromtimestamp(
            observed_us / 1_000_000, timezone.utc
        ).isoformat(),
        "ed25519_signature_verified": True,
        "trusted_journal_pid_uid_cgroup_unit_match": True,
        "systemd_invocation_present": True,
        "self_issued_ephemeral_signing_only": True,
        "trusted_agent_registration_verified": False,
        "live_message_transport_verified": False,
        "production_queue_modified": False,
        "execution_authority": "none",
    }


def inspect_coder_signing_journal(*, journal_entries: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    expected_uid = pwd.getpwnam("ubuntu").pw_uid
    if journal_entries is None:
        command = [
            "journalctl", "-u", UNIT, "-g", "CODER_AGENT_SIGNATURE_OBSERVE",
            "-n", str(MAX_JOURNAL_LINES), "--no-pager", "-o", "json",
        ]
        try:
            done = subprocess.run(
                command, capture_output=True, text=True,
                timeout=12, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "JOURNAL_UNAVAILABLE", "registered_agents": 0}
        if done.returncode != 0:
            return {"status": "JOURNAL_UNAVAILABLE", "registered_agents": 0}
        journal_entries = []
        for line in done.stdout.splitlines()[-MAX_JOURNAL_LINES:]:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                journal_entries.append(row)
    verified = [
        result
        for entry in journal_entries[-MAX_JOURNAL_LINES:]
        if (result := inspect_journal_entry(entry, expected_uid)) is not None
    ]
    if not verified:
        return {
            "status": "NO_VALID_MANAGED_CODER_SIGNING_JOURNAL_PROOF",
            "registered_agents": 0,
            "live_message_transport_verified": False,
        }
    latest = max(verified, key=lambda item: item["observed_at_utc"])
    return {**latest, "verified_process_signing_observation_count": len(verified),
            "registered_agents": 0}


def main() -> int:
    if sys.argv[1:] != ["--review-read-only"]:
        print("EXACT_READ_ONLY_REVIEW_FLAG_REQUIRED")
        return 2
    result = inspect_coder_signing_journal()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "VERIFIED_HISTORICAL_MANAGED_CODER_EPHEMERAL_SIGNATURE" else 4


if __name__ == "__main__":
    raise SystemExit(main())
