"""V4.5: real isolated Redis 8 + PostgreSQL 18 consumer recovery acceptance.

No production Redis, PostgreSQL, service, source rights, or execution authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/rehearse_predictive_cloud_v45_consumer_20261024.sh"
RUN = ROOT / "scripts/rehearse_predictive_cloud_v45_consumer_20261024.py"


def test_v45_wrapper_isolated_and_no_install():
    sh = SHELL.read_text()
    for required in (
        "/tmp/pg_virtualenv.*/data/18/regress",
        "PGPORT >= 5433",
        "mktemp -d /tmp/empire-v45-redis-package.",
        "mktemp -d /tmp/empire-v4-redis-run.",
        "apt download redis-server redis-tools liblzf1",
        "dpkg-deb -x",
        "--port 0",
        "--unixsocketperm 700",
        '--save "" --appendonly no',
        "shutdown nosave",
        "trap cleanup EXIT",
        "migrations/empiredb/064_predictive_v4_projection_outbox_held.sql",
        "migrations/empiredb/065_predictive_v4_advisory_replay_receipts_held.sql",
    ):
        assert required in sh
    executable = "\n".join(
        line for line in sh.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    for forbidden in ("sudo ", "apt install", "systemctl start",
                      "docker run", "--port 6379", "PGPORT=5432"):
        assert forbidden not in executable


def test_v45_code_requires_pg_commit_before_disposable_ack():
    py = RUN.read_text()
    for required in (
        "XREADGROUP",
        "XGROUP",
        "XPENDING",
        "XAUTOCLAIM",
        "XACK",
        "V45_REFUSE_ACK_WITHOUT_DURABLE_PG_RECEIPT",
        "FIRST_OBSERVATION_HELD",
        "DUPLICATE_HELD",
        "WITHDRAWN_BLOCKED",
        "V4_065_UNKNOWN_TENANT_EVENT",
        "pending(redis) == 1",
        "live_redis_ack_sent",
        "production_empiredb_touched",
    ):
        assert required in py
    assert "redis.command(\"XACK\"" not in (
        py.split("def ack_after_durable_receipt")[0]
    )
    assert "create_v45_consumer_router" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


def test_v45_rejects_production_postgresql_port_without_opening_connections():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432")
    result = subprocess.run(
        ["bash", str(SHELL)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "REAL_LOCAL_REDIS8_PG18_CONSUMER_RECOVERY_PASS" not in result.stdout


@pytest.mark.skipif(
    any(shutil.which(x) is None for x in ("pg_virtualenv", "apt", "dpkg-deb")),
    reason="disposable Redis/PG tooling not available",
)
def test_v45_actual_redis_group_redelivery_receipt_ack_crash_windows():
    run = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(SHELL)],
        cwd=ROOT, capture_output=True, text=True, timeout=150,
    )
    assert run.returncode == 0, run.stdout[-6000:] + run.stderr[-4000:]
    json_rows = [line for line in run.stdout.splitlines() if line.startswith("{")]
    assert len(json_rows) == 1, run.stdout[-4000:]
    result = json.loads(json_rows[0])
    assert result["status"] == "REAL_LOCAL_REDIS8_PG18_CONSUMER_RECOVERY_PASS"
    assert result["tcp_redis_port"] == 0
    assert result["postgresql_cluster"] == "disposable_pg_virtualenv_18"
    for key in (
        "consumer_crash_before_db_commit_recovered",
        "consumer_crash_after_db_commit_recovered",
        "xautoclaim_pending_recovery",
        "duplicate_stream_event_deduplicated",
        "withdrawn_event_blocked",
        "unknown_event_stays_pending",
    ):
        assert result[key] is True
    assert result["redis_stream_event_count"] == 5
    assert result["durable_held_receipt_count"] == 3
    assert result["pending_unacked_count"] == 1
    for key in (
        "redis_cloud_connected", "real_source_authority_verified",
        "production_empiredb_touched", "live_redis_ack_sent",
        "money_moved", "outbound_sent", "paid_traffic",
    ):
        assert result[key] is False
    assert "V45_EPHEMERAL_CONSUMER_GAUNTLET_COMPLETE" in run.stdout
    assert "Dropping cluster 18/regress" in run.stdout + run.stderr
