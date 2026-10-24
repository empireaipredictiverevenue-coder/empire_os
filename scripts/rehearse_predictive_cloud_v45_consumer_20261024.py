#!/usr/bin/env python3
"""V4.5 controlled real Redis 8 consumer-group + disposable PG18 receipt drill.

No live infrastructure, Redis Cloud, public API, real tenant, email, funds or
paid traffic. The only Redis ACKs happen in a private disposable Unix socket.
The canonical migration remains PREPARED, never applied to production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import subprocess

from empire_os.predictive_cloud_v4_redis_shadow import (
    STREAM, emit_fixture_swarm_observation,
)
from scripts.rehearse_predictive_cloud_v4_real_redis_20261024 import RedisSocket

TENANT = "00000000-0000-0000-0000-000000000101"
TENANT_DIGEST = sha256(b"fictional-v45-tenant").hexdigest()
SOURCE_DIGEST = sha256(b"fictional-v45-source").hexdigest()
ENTITY = sha256(b"fictional-v45-entity").hexdigest()
STREAM_KEY = f"{STREAM}:{TENANT_DIGEST}"
GROUP = "v45-shadow-review"
HEX = re.compile(r"^[a-f0-9]{64}$")


def digest(label: str) -> str:
    return sha256(("fictional-v45-event:" + label).encode()).hexdigest()


def sql(query: str, *, expect_failure: bool = False) -> str:
    """SQL constructed ONLY with known fictional constants and validated digests."""
    result = subprocess.run(
        ["psql", "-XAtq", "-v", "ON_ERROR_STOP=1",
         "-d", "empire_v4_outbox_fixture", "-c",
         "SET ROLE empiredb_migrator; " + query],
        capture_output=True, text=True, timeout=8, check=False,
    )
    if expect_failure:
        assert result.returncode != 0, result.stdout
        assert "V4_065_UNKNOWN_TENANT_EVENT" in result.stderr
        return ""
    assert result.returncode == 0, result.stderr[-1000:]
    return result.stdout.strip()


def stage(event: str, rev: int, kind: str = "OBSERVED") -> None:
    assert HEX.fullmatch(event)
    assert kind in ("OBSERVED", "WITHDRAWN")
    res = json.loads(sql(
        "SELECT public.stage_empire_predictive_v4_projection_held("
        f"'{TENANT}','roofing','{ENTITY}','{SOURCE_DIGEST}',"
        f"{rev},'{event}','{kind}')"
    ))
    assert res["status"] == "HELD_STAGED"
    assert res["redis_publish_authorized"] is False


def observe(event: str, message_id: str, *, absent: bool = False) -> dict:
    assert HEX.fullmatch(event)
    assert re.fullmatch(r"[0-9]{1,20}-[0-9]{1,20}", message_id)
    raw = sql(
        "SELECT public.audit_empire_predictive_v4_stream_observation_held("
        f"'{TENANT}','{event}','{message_id}')",
        expect_failure=absent,
    )
    return {} if absent else json.loads(raw)


def durable_receipt(event: str) -> bool:
    assert HEX.fullmatch(event)
    value = sql(
        "SELECT count(*) FROM public.empire_predictive_v4_advisory_receipts_held "
        f"WHERE tenant_id='{TENANT}' AND event_digest='{event}' "
        "AND receipt_state='HELD' AND redis_acknowledged=false "
        "AND action_executed=false AND source_authorized=false"
    )
    return value == "1"


def receipt_count() -> int:
    return int(sql(
        "SELECT count(*) FROM public.empire_predictive_v4_advisory_receipts_held "
        f"WHERE tenant_id='{TENANT}'"
    ))


def as_text(value):
    return value.decode("ascii") if type(value) is bytes else value


def unpack(entries: object) -> tuple[str, dict[str, str]]:
    assert type(entries) is list and len(entries) == 1
    mid, packed = entries[0]
    assert type(packed) is list and len(packed) % 2 == 0
    fields = {as_text(k): as_text(v)
              for k, v in zip(packed[::2], packed[1::2])}
    assert set(fields) == {
        "schema_version", "event_digest", "source_evidence_digest",
        "signal", "mode", "execution_authority", "observed_at"
    }
    assert fields["mode"] == "OBSERVE"
    assert fields["execution_authority"] == "none"
    assert fields["signal"] == "RISK_CONSTRAINT_OBSERVED"
    assert fields["source_evidence_digest"] == SOURCE_DIGEST
    assert HEX.fullmatch(fields["event_digest"])
    return as_text(mid), fields


def read_one(redis: RedisSocket, consumer: str) -> tuple[str, dict]:
    result = redis.command(
        "XREADGROUP", "GROUP", GROUP, consumer,
        "COUNT", 1, "STREAMS", STREAM_KEY, ">"
    )
    assert type(result) is list and len(result) == 1
    assert as_text(result[0][0]) == STREAM_KEY
    return unpack(result[0][1])


def reclaim_one(redis: RedisSocket, consumer: str) -> tuple[str, dict]:
    # min-idle=0 is ONLY for this disposable, deterministic test.
    result = redis.command(
        "XAUTOCLAIM", STREAM_KEY, GROUP, consumer, 0, "0-0", "COUNT", 1
    )
    assert type(result) is list and len(result) >= 2
    return unpack(result[1])


def pending(redis: RedisSocket) -> int:
    result = redis.command("XPENDING", STREAM_KEY, GROUP)
    assert type(result) is list and type(result[0]) is int
    return result[0]


def ack_after_durable_receipt(redis: RedisSocket, mid: str, event: str) -> None:
    assert durable_receipt(event), "V45_REFUSE_ACK_WITHOUT_DURABLE_PG_RECEIPT"
    assert redis.command("XACK", STREAM_KEY, GROUP, mid) == 1


def append_event(redis: RedisSocket, event: str) -> str:
    result = emit_fixture_swarm_observation(
        redis, tenant_scope_digest=TENANT_DIGEST,
        event_digest=event, source_evidence_digest=SOURCE_DIGEST,
        signal="RISK_CONSTRAINT_OBSERVED", now=datetime.now(timezone.utc),
        fixture_authorised=True,
    )
    assert result["execution_authority"] == "fixture_only"
    assert result["durable_ledger_committed"] is False
    return result["stream_id"]


def main() -> None:
    socket_path = os.environ.get("EMPIRE_V45_REDIS_FIXTURE_SOCKET", "")
    redis = RedisSocket(socket_path)  # refuses all non-temporary sockets
    assert redis.command("CONFIG", "GET", "port") == [b"port", b"0"]
    assert redis.command("CONFIG", "GET", "appendonly") == [b"appendonly", b"no"]
    assert redis.command("CONFIG", "GET", "save") == [b"save", b""]
    assert redis.command("PING") == "PONG"
    redis.command("XGROUP", "CREATE", STREAM_KEY, GROUP, "0", "MKSTREAM")

    # Consumer crash BEFORE durable PostgreSQL audit, no Redis XACK.
    a = digest("before-durable")
    stage(a, 1)
    mid_a = append_event(redis, a)
    delivered_a, msg = read_one(redis, "worker-before-crash")
    assert delivered_a == mid_a and msg["event_digest"] == a
    assert pending(redis) == 1 and not durable_receipt(a)
    try:
        ack_after_durable_receipt(redis, delivered_a, a)
    except AssertionError as exc:
        assert "V45_REFUSE_ACK_WITHOUT_DURABLE_PG_RECEIPT" in str(exc)
    else:
        raise AssertionError("V45_ACK_WAS_NOT_BLOCKED_BEFORE_DURABLE_RECEIPT")
    assert pending(redis) == 1
    claimed_a, msg = reclaim_one(redis, "worker-recovery")
    assert claimed_a == mid_a and msg["event_digest"] == a
    first = observe(a, claimed_a)
    assert first["status"] == "FIRST_OBSERVATION_HELD"
    assert first["decision"] == "UNVERIFIED_BLOCKED"
    ack_after_durable_receipt(redis, claimed_a, a)
    assert pending(redis) == 0 and receipt_count() == 1

    # Crash AFTER database COMMIT but BEFORE Redis ACK: replay must be idempotent.
    b = digest("after-durable-before-ack")
    stage(b, 2)
    mid_b = append_event(redis, b)
    delivered_b, msg = read_one(redis, "worker-crash-after-commit")
    assert delivered_b == mid_b and msg["event_digest"] == b
    first_b = observe(b, mid_b)
    assert first_b["status"] == "FIRST_OBSERVATION_HELD"
    assert pending(redis) == 1 and durable_receipt(b)
    claimed_b, msg = reclaim_one(redis, "worker-recovery")
    assert claimed_b == mid_b
    duplicate_b = observe(b, claimed_b)
    assert duplicate_b["status"] == "DUPLICATE_HELD"
    assert receipt_count() == 2
    ack_after_durable_receipt(redis, claimed_b, b)
    assert pending(redis) == 0

    # Redis XADD can store duplicate event digests under DIFFERENT IDs.
    another_id_b = append_event(redis, b)
    assert another_id_b != mid_b
    delivered_dup, msg = read_one(redis, "worker-duplicate")
    assert delivered_dup == another_id_b and msg["event_digest"] == b
    assert observe(b, another_id_b)["status"] == "DUPLICATE_HELD"
    assert receipt_count() == 2
    ack_after_durable_receipt(redis, another_id_b, b)

    # Withdrawal is terminal in held 064 and 065, even across redelivery.
    c = digest("withdrawal")
    stage(c, 3, "WITHDRAWN")
    mid_c = append_event(redis, c)
    delivered_c, msg = read_one(redis, "worker-withdrawal")
    assert delivered_c == mid_c and msg["event_digest"] == c
    blocked_c = observe(c, mid_c)
    assert blocked_c["decision"] == "WITHDRAWN_BLOCKED"
    ack_after_durable_receipt(redis, mid_c, c)
    assert receipt_count() == 3

    # Unknown forged stream entry MUST remain pending, unacknowledged.
    unknown = digest("no-canonical-outbox")
    mid_unknown = append_event(redis, unknown)
    received_unknown, msg = read_one(redis, "worker-unknown")
    assert received_unknown == mid_unknown and msg["event_digest"] == unknown
    assert not durable_receipt(unknown)
    observe(unknown, mid_unknown, absent=True)
    claimed_unknown, msg = reclaim_one(redis, "worker-unknown-retry")
    assert claimed_unknown == mid_unknown and msg["event_digest"] == unknown
    assert pending(redis) == 1 and receipt_count() == 3
    assert redis.command("XRANGE", STREAM_KEY, "-", "+") is not None
    assert int(redis.command("XLEN", STREAM_KEY)) == 5

    print(json.dumps({
        "status": "REAL_LOCAL_REDIS8_PG18_CONSUMER_RECOVERY_PASS",
        "tcp_redis_port": 0,
        "redis_cloud_connected": False,
        "postgresql_cluster": "disposable_pg_virtualenv_18",
        "consumer_crash_before_db_commit_recovered": True,
        "consumer_crash_after_db_commit_recovered": True,
        "xautoclaim_pending_recovery": True,
        "duplicate_stream_event_deduplicated": True,
        "withdrawn_event_blocked": True,
        "unknown_event_stays_pending": True,
        "durable_held_receipt_count": 3,
        "redis_stream_event_count": 5,
        "pending_unacked_count": pending(redis),
        "redis_ack_gate": "local_ephemeral_postgres_receipt_readback_only",
        "real_source_authority_verified": False,
        "production_empiredb_touched": False,
        "live_redis_ack_sent": False,
        "money_moved": False,
        "outbound_sent": False,
        "paid_traffic": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
