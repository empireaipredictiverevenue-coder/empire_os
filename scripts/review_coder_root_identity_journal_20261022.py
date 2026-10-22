#!/usr/bin/env python3
"""Read-only independent journal audit of a REAL Coder -> root-helper handshake.

Kernel journal provenance is not a key registry or an authorization grant.
This script never claims that a historic receipt authenticates the current
process or permits signed tasks, emails, payments, trades or other actions.
"""
from __future__ import annotations

import json
import pwd
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Mapping

UNIT = "empire-coder-worker.service"
ROOT_HELPER_UNIT = "empire-ops-privileged-helper.service"
PREFIX = "CODER_ROOT_IDENTITY_PREFLIGHT "
POSITIVE = "VERIFIED_CURRENT_CODER_MAIN_PROCESS_BY_ROOT_HELPER"
INVOCATION = re.compile(r"^[0-9a-f]{32}$")
MAX_LINES = 40
POSITIVE_FIELDS = frozenset({
    "status", "actual_worker_pid", "agent_id", "unit",
    "canonical_task_claimed", "execution_authority",
    "live_collaboration_activated", "persistent_signing_key_issued",
    "registered_agent", "root_helper_identity_preflight",
})


def verify_journal_event(
    event: Mapping[str, Any], *, expected_uid: int,
) -> dict[str, object] | None:
    """Requires journald *trusted underscore fields*, not payload-supplied facts."""
    msg = event.get("MESSAGE")
    if not isinstance(msg, str) or not msg.startswith(PREFIX):
        return None
    try:
        payload = json.loads(msg[len(PREFIX):])
    except (ValueError, UnicodeError, TypeError):
        return None
    if (
        not isinstance(payload, dict)
        or set(payload) != POSITIVE_FIELDS
        or payload["status"] != POSITIVE
        or payload["agent_id"] != "empire_coder"
        or payload["unit"] != UNIT
        or type(payload["actual_worker_pid"]) is not int
        or payload["actual_worker_pid"] <= 1
        or payload["root_helper_identity_preflight"] is not True
        or payload["canonical_task_claimed"] is not False
        or payload["live_collaboration_activated"] is not False
        or payload["persistent_signing_key_issued"] is not False
        or payload["registered_agent"] is not False
        or payload["execution_authority"] != "none"
        or event.get("_PID") != str(payload["actual_worker_pid"])
        or event.get("_UID") != str(expected_uid)
        or event.get("_SYSTEMD_UNIT") != UNIT
        or event.get("_SYSTEMD_CGROUP") != "/system.slice/" + UNIT
        or event.get("_TRANSPORT") != "stdout"
        or not isinstance(event.get("_SYSTEMD_INVOCATION_ID"), str)
        or INVOCATION.fullmatch(event["_SYSTEMD_INVOCATION_ID"]) is None
    ):
        return None
    try:
        microseconds = int(event["__REALTIME_TIMESTAMP"])
        moment = datetime.fromtimestamp(microseconds / 1_000_000, timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError, KeyError):
        return None
    if moment.year < 2026 or moment.year > 2100:
        return None
    return {
        "status": "VERIFIED_HISTORICAL_CODER_ROOT_HELPER_PROCESS_PROVENANCE",
        "observed_at_utc": moment.isoformat(),
        "actual_worker_pid": payload["actual_worker_pid"],
        "kernel_journal_pid_uid_unit_cgroup_match": True,
        "systemd_invocation_bound": True,
        "root_helper_positive_origin_preflight_reported": True,
        "historical_process_only": True,
        "persistent_signing_key_issued": False,
        "registered_production_agents": 0,
        "live_collaboration_activated": False,
        "canonical_queue_modified_by_preflight": False,
        "trusted_message_sent": False,
        "execution_authority": "none",
    }


def review(
    *,
    events: list[Mapping[str, Any]] | None = None,
    expected_uid: int | None = None,
) -> dict[str, object]:
    if expected_uid is None:
        expected_uid = pwd.getpwnam("ubuntu").pw_uid
    if events is None:
        try:
            command = [
                "journalctl", "-u", UNIT, "-g", "CODER_ROOT_IDENTITY_PREFLIGHT",
                "-n", str(MAX_LINES), "-o", "json", "--no-pager",
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "JOURNAL_NOT_ACCESSIBLE", "registered_production_agents": 0}
        if result.returncode:
            return {"status": "JOURNAL_NOT_ACCESSIBLE", "registered_production_agents": 0}
        events = []
        for line in result.stdout.splitlines()[-MAX_LINES:]:
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                events.append(obj)
    hits = [
        proof
        for event in events[-MAX_LINES:]
        if (proof := verify_journal_event(event, expected_uid=expected_uid)) is not None
    ]
    if not hits:
        return {
            "status": "NO_VERIFIED_CODER_ROOT_HELPER_ORIGIN_PROOF",
            "registered_production_agents": 0,
            "live_collaboration_activated": False,
        }
    latest = max(hits, key=lambda proof: proof["observed_at_utc"])
    return {
        **latest,
        "verified_historical_process_observation_count": len(hits),
    }


def main() -> int:
    if sys.argv[1:] != ["--review-read-only"]:
        print("EXACT_READ_ONLY_REVIEW_FLAG_REQUIRED")
        return 2
    output = review()
    print(json.dumps(output, sort_keys=True))
    return (
        0 if output["status"] ==
        "VERIFIED_HISTORICAL_CODER_ROOT_HELPER_PROCESS_PROVENANCE"
        else 4
    )


if __name__ == "__main__":
    raise SystemExit(main())
