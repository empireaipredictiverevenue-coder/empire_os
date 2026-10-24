#!/usr/bin/env python3
"""V4.6 research: Redis 8 AOF server restart + durable held PG18 reconciliation.

Three fixture-only phases executed by the guarded shell wrapper, with the real
Redis process stopped/restarted between invocations. No production clients.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from scripts.rehearse_predictive_cloud_v4_real_redis_20261024 import RedisSocket
from scripts.rehearse_predictive_cloud_v45_consumer_20261024 import (
    STREAM_KEY, TENANT, SOURCE_DIGEST, digest, stage, append_event,
    observe, durable_receipt, receipt_count, unpack, as_text,
)

GROUP = "v46-server-recovery"
A = digest("v46-no-db-receipt")
B = digest("v46-db-receipt-no-ack")
C = digest("v46-source-withdrawn")
UNKNOWN = digest("v46-unverified-no-pg-event")


def pending(redis: RedisSocket) -> list[tuple[str, str]]:
    rows = redis.command("XPENDING", STREAM_KEY, GROUP, "-", "+", 32)
    assert type(rows) is list
    return [(as_text(x[0]), as_text(x[1])) for x in rows]


def read(redis: RedisSocket, consumer: str, count: int = 1) -> list:
    batch = redis.command("XREADGROUP", "GROUP", GROUP, consumer,
                          "COUNT", count, "STREAMS", STREAM_KEY, ">")
    assert type(batch) is list and len(batch) == 1
    assert as_text(batch[0][0]) == STREAM_KEY
    return [unpack([x]) for x in batch[0][1]]


def reclaim(redis: RedisSocket, consumer: str) -> list:
    # min-idle 0 is safe only in disposable, serialised acceptance testing.
    reply = redis.command("XAUTOCLAIM", STREAM_KEY, GROUP, consumer,
                          0, "0-0", "COUNT", 32)
    assert type(reply) is list and len(reply) >= 2
    return [unpack([entry]) for entry in reply[1]]


def assert_aof_config(redis: RedisSocket) -> None:
    assert redis.command("PING") == "PONG"
    assert redis.command("CONFIG", "GET", "port") == [b"port", b"0"]
    assert redis.command("CONFIG", "GET", "save") == [b"save", b""]
    assert redis.command("CONFIG", "GET", "appendonly") == [b"appendonly", b"yes"]
    assert redis.command("CONFIG", "GET", "appendfsync") == [b"appendfsync", b"always"]


def ack_after_held_pg_readback(redis: RedisSocket, mid: str, event: str) -> None:
    assert durable_receipt(event), "V46_REFUSE_ACK_WITHOUT_HELD_EMPIREDB_RECEIPT"
    assert redis.command("XACK", STREAM_KEY, GROUP, mid) == 1


def before_graceful(redis: RedisSocket) -> dict:
    redis.command("XGROUP", "CREATE", STREAM_KEY, GROUP, "0", "MKSTREAM")
    stage(A, 1)
    a_id = append_event(redis, A)
    rows = read(redis, "reader-crashed-pre-db")
    assert rows[0][0] == a_id and rows[0][1]["event_digest"] == A

    # Stream contains untrusted data not admitted into held PG outbox.
    unknown_id = append_event(redis, UNKNOWN)
    rows = read(redis, "reader-unknown-pre-db")
    assert rows[0][0] == unknown_id and rows[0][1]["event_digest"] == UNKNOWN
    assert len(pending(redis)) == 2
    assert not durable_receipt(A)
    assert not durable_receipt(UNKNOWN)
    try:
        ack_after_held_pg_readback(redis, a_id, A)
    except AssertionError as exc:
        assert "V46_REFUSE_ACK_WITHOUT_HELD_EMPIREDB_RECEIPT" in str(exc)
    else:
        raise AssertionError("V46_PREMATURE_ACK_UNEXPECTEDLY_PERMITTED")
    assert len(pending(redis)) == 2
    return {
        "phase": "before_graceful",
        "pending_before_restart": 2,
        "acked_before_pg_receipt": False,
        "redis_stream_length": redis.command("XLEN", STREAM_KEY),
    }


def after_graceful(redis: RedisSocket) -> dict:
    assert redis.command("XLEN", STREAM_KEY) == 2
    assert len(pending(redis)) == 2
    claimed = reclaim(redis, "reader-recovered-graceful")
    assert len(claimed) == 2
    by_event = {fields["event_digest"]: mid for mid, fields in claimed}
    assert set(by_event) == {A, UNKNOWN}
    assert not durable_receipt(A)
    assert observe(A, by_event[A])["decision"] == "UNVERIFIED_BLOCKED"
    assert durable_receipt(A)
    ack_after_held_pg_readback(redis, by_event[A], A)
    assert len(pending(redis)) == 1
    assert pending(redis)[0][0] == by_event[UNKNOWN]
    assert not durable_receipt(UNKNOWN)

    # A second event obtains durable PG held receipt but deliberately lacks XACK.
    stage(B, 2)
    b_id = append_event(redis, B)
    rows = read(redis, "reader-crashed-after-pg")
    assert rows[0][0] == b_id and rows[0][1]["event_digest"] == B
    assert observe(B, b_id)["status"] == "FIRST_OBSERVATION_HELD"
    assert durable_receipt(B)
    assert len(pending(redis)) == 2
    assert receipt_count() == 2
    return {
        "phase": "after_graceful",
        "pre_restart_pending_reclaimed": True,
        "missing_pg_receipt_created": True,
        "pending_before_forced_crash": 2,
        "durable_held_receipts": receipt_count(),
    }


def after_crash(redis: RedisSocket) -> dict:
    assert redis.command("XLEN", STREAM_KEY) == 3
    assert len(pending(redis)) == 2
    claimed = reclaim(redis, "reader-recovered-kill")
    assert len(claimed) == 2
    by_event = {fields["event_digest"]: mid for mid, fields in claimed}
    assert set(by_event) == {B, UNKNOWN}
    assert observe(B, by_event[B])["status"] == "DUPLICATE_HELD"
    assert receipt_count() == 2
    ack_after_held_pg_readback(redis, by_event[B], B)
    assert pending(redis) == [(by_event[UNKNOWN], "reader-recovered-kill")]
    assert not durable_receipt(UNKNOWN)

    # Redis stream ID must never be treated as independently verified source.
    stage(C, 3, "WITHDRAWN")
    c_id = append_event(redis, C)
    rows = read(redis, "reader-withdrawal-after-kill")
    assert rows[0][0] == c_id and rows[0][1]["event_digest"] == C
    assert observe(C, c_id)["decision"] == "WITHDRAWN_BLOCKED"
    ack_after_held_pg_readback(redis, c_id, C)
    assert receipt_count() == 3

    # A second XADD carrying an identical event digest gets a distinct ID but
    # only a held dedup receipt; never another source admission or financial action.
    duplicate_id = append_event(redis, B)
    rows = read(redis, "reader-duplicate-after-kill")
    assert rows[0][0] == duplicate_id and rows[0][1]["event_digest"] == B
    assert observe(B, duplicate_id)["status"] == "DUPLICATE_HELD"
    ack_after_held_pg_readback(redis, duplicate_id, B)

    final = pending(redis)
    assert len(final) == 1
    assert final[0][0] == by_event[UNKNOWN]
    assert redis.command("XLEN", STREAM_KEY) == 5
    assert receipt_count() == 3
    return {
        "status": "V46_REAL_REDIS8_AOF_PG18_RESTART_RECOVERY_PASS",
        "phase": "after_crash",
        "graceful_restart_persisted_stream_and_pel": True,
        "forced_crash_restart_persisted_stream_and_pel": True,
        "missing_db_receipt_recovered": True,
        "post_commit_replay_deduplicated": True,
        "duplicate_xadd_deduplicated": True,
        "source_withdrawal_blocked": True,
        "unknown_unadmitted_event_pending": True,
        "aof_appendfsync_always": True,
        "redis_tcp_port": 0,
        "held_pg_receipts": receipt_count(),
        "stream_length": redis.command("XLEN", STREAM_KEY),
        "pending_unknown_count": len(final),
        "redis_cloud_connected": False,
        "real_tenant_or_source_authority_verified": False,
        "production_empiredb_touched": False,
        "production_redis_touched": False,
        "actual_revenue_verified": False,
        "paid_traffic": False,
        "outbound_sent": False,
        "money_moved": False,
    }


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in (
        "before_graceful", "after_graceful", "after_crash"
    ):
        raise SystemExit("V46_GUARDED_PHASE_REQUIRED")
    path = os.environ.get("EMPIRE_V46_REDIS_FIXTURE_SOCKET", "")
    redis = RedisSocket(path)
    assert_aof_config(redis)
    mode = sys.argv[1]
    if mode == "before_graceful":
        result = before_graceful(redis)
    elif mode == "after_graceful":
        result = after_graceful(redis)
    else:
        result = after_crash(redis)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
