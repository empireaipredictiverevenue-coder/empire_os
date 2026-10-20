"""Crash-resilient change-only journal for the EXISTING Ops Control cycle.

One small OS-owned JSONL ledger. No scheduler, CRM action, outbound or
commercial writes. The event is already privacy-minimal and schema-validated.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re

from empire_os.commercial_adaptive_intelligence_control import POLICY_LOOKUP
from empire_os.commercial_sales_director_adaptive_review import SOURCE_KINDS

HEX64 = re.compile(r"^[a-f0-9]{64}$")
EVENT_KEYS = frozenset({
    "event_id", "owner_receipt_set_digest", "observed_at", "event_code",
    "decision_signature", "changed_gate_names", "gates_newly_blocking",
    "gates_no_longer_reported", "changed_owner_source_names",
    "owner_dispatch_executed", "outbound_sent", "execution_authority",
})
MAX_ENTRY = 8000


def _event_shape(value: dict) -> None:
    if not isinstance(value, dict) or set(value) != EVENT_KEYS:
        raise ValueError("exact privacy-safe commercial event contract required")
    if any(not isinstance(value[k], str) or not HEX64.fullmatch(value[k])
           for k in ("event_id", "owner_receipt_set_digest", "decision_signature")):
        raise ValueError("commercial event digest invalid")
    if value["event_code"] not in (
        "COMMERCIAL_EVIDENCE_STATE_CHANGED", "ORIGINAL_SOURCE_RECEIPT_CHANGED_ONLY"
    ) or value["execution_authority"] != "none":
        raise ValueError("commercial event lacks non-executing authority")
    if value["owner_dispatch_executed"] is not False or value["outbound_sent"] is not False:
        raise ValueError("commercial event cannot claim action")
    if not isinstance(value["observed_at"], str) or len(value["observed_at"]) > 40:
        raise ValueError("bounded event observation timestamp required")
    for field in ("changed_gate_names", "gates_newly_blocking", "gates_no_longer_reported"):
        arr = value[field]
        if not isinstance(arr, list) or len(arr) > 8 or any(
            not isinstance(s, str) or s not in POLICY_LOOKUP for s in arr
        ):
            raise ValueError("unknown commercial gate in event")
    changes = value["changed_owner_source_names"]
    if not isinstance(changes, list) or len(changes) > 10 or any(
        not isinstance(s, str) or s not in SOURCE_KINDS for s in changes
    ):
        raise ValueError("unknown source receipt in commercial event")


def append_change_once(path: Path, event: dict) -> bool:
    """Append once by stable event_id despite retry or interrupted snapshot write.

    Linux flock serialises journal read/check/write across any overlapping runs.
    Only a *trailing incomplete* JSONL record is dropped after a crash.
    """
    _event_shape(event)
    serialized = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    if len(serialized.encode("utf-8")) > MAX_ENTRY:
        raise ValueError("commercial journal entry too large")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+", encoding="utf-8", closefd=False) as stream:
            stream.seek(0, os.SEEK_END)
            end = stream.tell()
            stream.seek(max(0, end - 16384))
            tail = stream.read()
            if tail and not tail.endswith("\n"):
                # Restore the last complete record before retrying an append.
                trim = tail.rfind("\n")
                target = end - len(tail) + trim + 1
                stream.truncate(target if trim >= 0 else 0)
                stream.flush()
                os.fsync(fd)
                tail = tail[:trim + 1] if trim >= 0 else ""
            last_line = tail.strip().splitlines()[-1:] if tail.strip() else []
            if last_line:
                try:
                    prior = json.loads(last_line[0])
                except json.JSONDecodeError as exc:
                    raise ValueError("last complete journal record invalid") from exc
                if prior.get("event_id") == event["event_id"]:
                    return False
            stream.seek(0, os.SEEK_END)
            stream.write(serialized)
            stream.flush()
            os.fsync(fd)
            return True
    finally:
        os.close(fd)
