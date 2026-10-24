"""Predictive Cloud V4.6: real Redis 8 AOF restart with disposable PG18.

Never installs a service, contacts production EmpireDB, sends outbound or moves funds.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/rehearse_predictive_cloud_v46_restart_20261024.sh"
PHASES = ROOT / "scripts/rehearse_predictive_cloud_v46_restart_20261024.py"


def test_v46_guarded_temporary_aof_restart_no_runtime_activation():
    sh = SHELL.read_text()
    for expected in (
        '/tmp/pg_virtualenv.*/data/18/regress',
        "PGPORT >= 5433",
        'mktemp -d /tmp/empire-v46-redis-package.',
        'mktemp -d /tmp/empire-v4-redis-run.',
        "apt download redis-server redis-tools liblzf1",
        "dpkg-deb -x",
    ):
        assert expected in sh
    for required in (
        '--port 0', '--unixsocketperm 700', '--save ""',
        '--appendonly yes --appendfsync always',
        "check_owned_pid", "kill -KILL", "shutdown nosave",
        "trap cleanup EXIT", 'phase before_graceful', 'phase after_graceful',
        'phase after_crash', "V46_AOF_RESTART_GAUNTLET_COMPLETE",
    ):
        assert required in sh
    executable = "\n".join(
        line for line in sh.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    for forbidden in (
        "sudo ", "apt install", "systemctl start", "docker run",
        "--port 6379", "PGPORT=5432", "empire-ai.co.uk",
    ):
        assert forbidden not in executable


def test_v46_exact_pg_live_port_refusal_before_package_or_server():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432")
    result = subprocess.run(
        ["bash", str(SHELL)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "V46_GRACEFUL_SERVER_RESTART_BEGIN" not in result.stdout


def test_v46_phase_code_rejects_non_ephemeral_redis_socket():
    env = dict(os.environ, EMPIRE_V46_REDIS_FIXTURE_SOCKET="/run/redis/redis.sock")
    result = subprocess.run(
        ["/srv/empire_os/.venv/bin/python", "-B", str(PHASES), "before_graceful"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=5,
    )
    assert result.returncode != 0
    assert "V4_REFUSED_NON_EPHEMERAL_REDIS_UNIX_SOCKET" in result.stderr
    assert "V46_REAL_REDIS8_AOF_PG18_RESTART_RECOVERY_PASS" not in result.stdout


def test_v46_restart_phases_have_no_live_consumer_or_production_sql():
    source = PHASES.read_text()
    for marker in (
        "V46_REFUSE_ACK_WITHOUT_HELD_EMPIREDB_RECEIPT",
        "UNVERIFIED_BLOCKED", "DUPLICATE_HELD", "WITHDRAWN_BLOCKED",
        "XAUTOCLAIM", "XREADGROUP", "XPENDING", "XACK",
        "V46_REAL_REDIS8_AOF_PG18_RESTART_RECOVERY_PASS",
        "real_tenant_or_source_authority_verified",
        "production_empiredb_touched",
        "actual_revenue_verified",
    ):
        assert marker in source
    assert "psycopg.connect(" not in source
    assert "redis.Redis(" not in source
    assert "smtplib" not in source
    assert "rehearse_predictive_cloud_v46_restart" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


@pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in ("pg_virtualenv", "apt", "dpkg-deb")),
    reason="isolated Redis/PG test utilities unavailable",
)
def test_v46_real_redis8_graceful_and_forced_server_restarts_replay():
    run = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(SHELL)],
        cwd=ROOT, capture_output=True, text=True, timeout=150,
    )
    assert run.returncode == 0, run.stdout[-8000:] + run.stderr[-3000:]
    phases = [
        json.loads(line) for line in run.stdout.splitlines()
        if line.startswith("{")
    ]
    assert [x["phase"] for x in phases] == [
        "before_graceful", "after_graceful", "after_crash",
    ]
    assert phases[0]["pending_before_restart"] == 2
    assert phases[0]["acked_before_pg_receipt"] is False
    assert phases[1]["pre_restart_pending_reclaimed"] is True
    assert phases[1]["missing_pg_receipt_created"] is True
    assert phases[1]["pending_before_forced_crash"] == 2
    result = phases[2]
    assert result["status"] == "V46_REAL_REDIS8_AOF_PG18_RESTART_RECOVERY_PASS"
    assert result["redis_tcp_port"] == 0
    assert result["held_pg_receipts"] == 3
    assert result["stream_length"] == 5
    assert result["pending_unknown_count"] == 1
    for key in (
        "graceful_restart_persisted_stream_and_pel",
        "forced_crash_restart_persisted_stream_and_pel",
        "missing_db_receipt_recovered",
        "post_commit_replay_deduplicated",
        "duplicate_xadd_deduplicated",
        "source_withdrawal_blocked",
        "unknown_unadmitted_event_pending",
        "aof_appendfsync_always",
    ):
        assert result[key] is True
    for key in (
        "redis_cloud_connected", "real_tenant_or_source_authority_verified",
        "production_empiredb_touched", "production_redis_touched",
        "actual_revenue_verified", "paid_traffic", "outbound_sent", "money_moved",
    ):
        assert result[key] is False
    assert "V46_AOF_RESTART_GAUNTLET_COMPLETE" in run.stdout
    assert "Dropping cluster 18/regress" in run.stdout + run.stderr
