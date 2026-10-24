#!/usr/bin/env python3
"""Cross-process synthetic timer replay for original EmpireDB ledger design.

Transfers ONLY fictional opaque events via standard input into a NEW Python
process. No database is written; no disk snapshot, timer worker, customer,
network, contact, notification provider, email or production service.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import subprocess
import sys

from empire_os.prime_flagship_timer_recovery_shadow import (
    replay_original_timer_shadow, founder_timer_recovery_status,
)

START = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
TENANT = "123e4567-e89b-42d3-a456-426614174000"
TIMER = sha256(b"synthetic-recovery-only-purpose-fixture").hexdigest()


def _event(seq: int, kind: str, *, seconds: int | None = None,
           after: int = 0, receipt: bool = False) -> dict:
    at = START + timedelta(seconds=after)
    return {
        "tenant_id": TENANT,
        "timer_digest": TIMER,
        "event_digest": sha256(("synthetic-replay-event-"+str(seq)+"-"+kind).encode()).hexdigest(),
        "seq": seq,
        "kind": kind,
        "occurred_at": at.isoformat(),
        "due_at": (at+timedelta(seconds=seconds)).isoformat() if seconds is not None else None,
        "duration_seconds": seconds,
        "provider_receipt_digest": sha256(
            ("synthetic-unverified-provider-"+str(seq)).encode()
        ).hexdigest() if receipt else None,
        "synthetic_fixture_only": True,
    }


def fixtures() -> dict[str, list[dict]]:
    return {
        "cancelled": [
            _event(1,"TIMER_CREATED",seconds=2),
            _event(2,"TIMER_CANCELLED",after=1),
        ],
        "claimed_crash": [
            _event(1,"TIMER_CREATED",seconds=2),
            _event(2,"DISPATCH_CLAIMED",after=2),
        ],
        "provider_accepted": [
            _event(1,"TIMER_CREATED",seconds=2),
            _event(2,"DISPATCH_CLAIMED",after=2),
            _event(3,"PROVIDER_ACCEPTED_REPORTED",after=3,receipt=True),
        ],
        "provider_reported_delivered": [
            _event(1,"TIMER_CREATED",seconds=2),
            _event(2,"DISPATCH_CLAIMED",after=2),
            _event(3,"PROVIDER_ACCEPTED_REPORTED",after=3,receipt=True),
            _event(4,"PROVIDER_DELIVERED_REPORTED",after=4,receipt=True),
        ],
    }


EXPECTED = {
    "cancelled": "CANCELLED_BEFORE_DISPATCH",
    "claimed_crash": "CLAIMED_RECONCILIATION_REQUIRED",
    "provider_accepted": "PROVIDER_ACCEPTED_NOT_DELIVERED",
    "provider_reported_delivered": "DELIVERY_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
}


def _child() -> int:
    try:
        packet = json.load(sys.stdin)
        if (type(packet) is not dict or set(packet) != {
            "fixture_name","tenant_id","timer_digest","events","as_of"
        } or packet["fixture_name"] not in EXPECTED):
            raise ValueError("strict_cross_process_synthetic_fixture_required")
        result = replay_original_timer_shadow(
            tenant_id=packet["tenant_id"],
            timer_digest=packet["timer_digest"],
            original_empiredb_event_rows=packet["events"],
            as_of=datetime.fromisoformat(packet["as_of"]),
        )
        summary = founder_timer_recovery_status(result)
        print(json.dumps({
            "fixture": packet["fixture_name"], "recovered_state": summary["status"],
            "real_notification_delivery_verified": False,
            "original_db_readback_verified": False,
            "child_process_replay_success": True,
            "execution_authority": "none",
        },sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError) as exc:
        print(json.dumps({
            "status": "SYNTHETIC_EVENT_REPLAY_HELD",
            "reason_type": type(exc).__name__,
            "execution_authority": "none",
        }))
        return 1


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--replay-stdin":
        return _child()
    if len(sys.argv) != 1:
        raise SystemExit("Only manual synthetic replay or --replay-stdin allowed")
    outcomes = []
    for name, events in fixtures().items():
        packet = {
            "fixture_name": name, "tenant_id": TENANT,
            "timer_digest": TIMER, "events": events,
            "as_of": (START+timedelta(seconds=5)).isoformat(),
        }
        run = subprocess.run(
            [sys.executable, "-B", __file__, "--replay-stdin"],
            input=json.dumps(packet), text=True, capture_output=True,
            timeout=8, check=False,
        )
        try:
            output = json.loads(run.stdout)
        except ValueError:
            output = {"recovered_state": "NO_VALID_READBACK"}
        valid = (
            run.returncode == 0
            and output.get("fixture") == name
            and output.get("recovered_state") == EXPECTED[name]
            and output.get("real_notification_delivery_verified") is False
            and output.get("original_db_readback_verified") is False
            and output.get("execution_authority") == "none"
        )
        outcomes.append({"fictional_case": name,
                         "new_process_replay_passed": valid,
                         "state": output.get("recovered_state")})
    success = all(x["new_process_replay_passed"] for x in outcomes)
    print(json.dumps({
        "schema_version": "empire.prime.original_cross_process_timer_recovery.v1",
        "mode": "SYNTHETIC_RESTART_REPLAY_ONLY",
        "status": "FOUR_FICTIONAL_RESTART_CONTRACTS_PASS" if success
                  else "RESTART_REPLAY_CONTRACT_HOLD",
        "fresh_processes_launched": len(outcomes),
        "cases": outcomes,
        "database_snapshot_restored": False,
        "persistent_empiredb_ledger_live": False,
        "real_customer_timer_created": False,
        "external_notification_delivered": False,
        "original_empiredb_writes": False,
        "execution_authority": "none",
    },indent=2,sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
