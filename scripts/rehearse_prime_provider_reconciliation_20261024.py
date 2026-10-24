#!/usr/bin/env python3
"""Manual offline synthetic provider receipt roundtrip on original PRIME.

One hypothetical claimed timer and fictional HMAC receipts. No sender,
webhook, provider account, device, user, phone, network, DB, SMS or push.
This cannot verify delivery outside this process.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import new as hmac_new
import json

from empire_os.prime_flagship_provider_reconciliation_shadow import (
    PROVIDER, _canonical, reconcile_synthetic_provider_receipts,
    founder_provider_receipt_reconciliation,
)
from empire_os.prime_flagship_timer_recovery_shadow import replay_original_timer_shadow

STAMP = datetime(2026, 10, 24, 13, 0, 5, tzinfo=timezone.utc)
TENANT = "123e4567-e89b-42d3-a456-426614174000"


def dg(x: str) -> str:
    return sha256(x.encode()).hexdigest()


def make_test_receipt(
    *, n: int, status: str, timer: str, claim: str, delivery: str, key: bytes,
) -> dict:
    packet = {
        "schema_version": "empire.prime.synthetic_provider_receipt.v1",
        "provider": PROVIDER,
        "tenant_id": TENANT,
        "timer_digest": timer,
        "claim_event_digest": claim,
        "delivery_reference_digest": delivery,
        "receipt_nonce": dg("fictional-receipt-nonce-" + str(n)),
        "status_code": status,
        "occurred_at": (STAMP-timedelta(seconds=2-n)).isoformat(),
        "synthetic_only": True,
    }
    packet["signature_hex"] = hmac_new(
        key, _canonical({**packet, "signature_hex": None}), "sha256",
    ).hexdigest()
    return packet


def main() -> int:
    timer = dg("fictional-timer-ref")
    claim = dg("fictional-atomic-claim-event")
    delivery = dg("fictional-provider-ref")
    secret = sha256(b"test-only in-memory HMAC credential, not a provider key").digest()
    base = {
        "tenant_id": TENANT, "timer_digest": timer,
        "synthetic_fixture_only": True, "provider_receipt_digest": None,
    }
    events = [
        {
            **base, "seq": 1, "event_digest": dg("create-original-event"),
            "kind": "TIMER_CREATED",
            "occurred_at": (STAMP-timedelta(seconds=5)).isoformat(),
            "due_at": (STAMP-timedelta(seconds=3)).isoformat(),
            "duration_seconds": 2,
        },
        {
            **base, "seq": 2, "event_digest": claim,
            "kind": "DISPATCH_CLAIMED",
            "occurred_at": (STAMP-timedelta(seconds=3)).isoformat(),
            "due_at": None, "duration_seconds": None,
        },
    ]
    original = replay_original_timer_shadow(
        tenant_id=TENANT, timer_digest=timer,
        original_empiredb_event_rows=events, as_of=STAMP,
    )
    outcomes = []
    for label, statuses in [
        ("no_callback", []),
        ("accepted_only", ["ACCEPTED"]),
        ("reported_delivery", ["ACCEPTED", "DELIVERED"]),
        ("reported_failure", ["FAILED"]),
    ]:
        receipts = [
            make_test_receipt(
                n=i+1, status=s, timer=timer, claim=claim,
                delivery=delivery, key=secret,
            ) for i, s in enumerate(statuses)
        ]
        reviewed = reconcile_synthetic_provider_receipts(
            original_timer_replay=original, receipts=receipts,
            fixture_hmac_key=secret,
            expected_claim_event_digest=claim,
            expected_delivery_reference_digest=delivery,
            as_of=STAMP,
        )
        projection = founder_provider_receipt_reconciliation(reviewed)
        outcomes.append({
            "fictional_case":label,
            "status":projection["status"],
            "fake_receipts_reconciled":projection["synthetic_receipt_count"],
            "real_provider_delivery_verified":projection["verified_real_provider_delivery"],
            "execution_authority":projection["execution_authority"],
        })
    passed = (
        [x["fake_receipts_reconciled"] for x in outcomes] == [0,1,2,1]
        and all(x["real_provider_delivery_verified"] is False for x in outcomes)
        and all(x["execution_authority"]=="none" for x in outcomes)
    )
    print(json.dumps({
        "schema_version":"empire.prime.synthetic_receipt_chain_demo.v1",
        "status":("FOUR_SYNTHETIC_PROVIDER_RECONCILIATIONS_PASS"
                  if passed else "SYNTHETIC_RECONCILIATION_HOLD"),
        "cases":outcomes,
        "provider_network_calls":0,
        "original_empiredb_writes":False,
        "notifications_sent":False,
        "source_attestation_real":False,
        "actual_user_device_alert":False,
        "execution_authority":"none",
    },indent=2,sort_keys=True))
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())
