"""Empire Predictive Cloud V4.4: prepared-only advisory receipt replay fencing.

Real PostgreSQL 18 acceptance is *disposable* pg_virtualenv. No runtime worker.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "migrations/empiredb/065_predictive_v4_advisory_replay_receipts_held.sql"
RUN = ROOT / "scripts/rehearse_predictive_cloud_v4_held_advisory_receipt_20261024.sh"


def test_065_only_held_receipts_not_a_stream_consumer():
    sql = SQL.read_text()
    for expected in (
        "V4_065_WRONG_DATABASE",
        "V4_065_ORIGINAL_HELD_OUTBOX_REQUIRED",
        "V4_065_EXISTING_RECEIPTS_REQUIRES_REVIEW",
        "V4_065_RESTRICTED_OWNER_REQUIRED",
        "V4_065_STREAM_ID_COLLISION",
        "V4_065_UNKNOWN_TENANT_EVENT",
        "V4_065_INVALID_HELD_OBSERVATION",
        "V4_065_APPEND_ONLY_RECEIPTS",
        "DUPLICATE_HELD",
        "FIRST_OBSERVATION_HELD",
        "FOR SHARE OF o,w",
        "FORCE ROW LEVEL SECURITY",
        "SECURITY INVOKER",
        "CHECK (NOT redis_acknowledged)",
        "CHECK (NOT action_executed)",
        "CHECK (NOT source_authorized)",
        "REVOKE ALL ON FUNCTION",
        "REVOKE ALL ON TABLE",
    ):
        assert expected in sql
    for forbidden in (
        "CREATE ROLE ",
        "SECURITY DEFINER",
        "GRANT EXECUTE ",
        "NOTIFY ",
        "pg_net",
        "dblink(",
        "INSERT INTO public.bsc_payment_requests",
    ):
        assert forbidden not in sql
    assert "audit_empire_predictive_v4_stream_observation_held" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()
    assert "redis.publish(" not in sql
    assert "redis.xack(" not in sql


def test_065_refuses_canonical_port_before_any_connection():
    env = dict(os.environ, PGPORT="5432", PGHOST="localhost")
    result = subprocess.run(["bash", str(RUN)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert "V4_065_DISPOSABLE_ONLY" not in result.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL not installed")
def test_065_real_pg_durable_idempotence_held_replay_and_rls():
    process = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(RUN)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert process.returncode == 0, process.stdout[-4000:] + process.stderr[-5000:]
    for marker in (
        "V4_065_ATOMIC_EVENT_DIGEST_DEDUP=PASS",
        "V4_065_CROSS_TENANT_STREAM_COLLISION_WITHDRAWAL=PASS",
        "V4_065_APPEND_ONLY_HELD_OWNER_RLS=PASS",
        "production_empiredb_writes=false",
        "redis_acknowledged=false",
        "executed=false",
        "Dropping cluster 18/regress",
    ):
        assert marker in process.stdout + process.stderr
