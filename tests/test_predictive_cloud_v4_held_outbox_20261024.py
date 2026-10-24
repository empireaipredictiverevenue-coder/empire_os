"""Predictive Cloud V4.2: held, ephemeral EmpireDB projection/outbox.
Never connect to production: PG fixture is pg_virtualenv and destroys the cluster.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/empiredb/064_predictive_v4_projection_outbox_held.sql"
HARNESS = ROOT / "scripts/rehearse_predictive_cloud_v4_held_outbox_20261024.sh"


def test_064_no_live_activation_or_runtime_grants():
    sql = MIGRATION.read_text()
    for requirement in (
        "V4_064_WRONG_DATABASE",
        "V4_064_RESTRICTED_OWNER_REQUIRED",
        "V4_064_EXISTING_CONTRACT_REQUIRES_REVIEW",
        "V4_064_STALE_OR_WITHDRAWN",
        "V4_064_EVENT_IDENTITY_COLLISION",
        "V4_064_APPEND_ONLY_OUTBOX",
        "SECURITY INVOKER",
        "FORCE ROW LEVEL SECURITY",
        "HELD_DUPLICATE",
        "HELD_STAGED",
        "source_review_state",
        "redis_publish_authorized",
        "REVOKE ALL ON FUNCTION",
        "REVOKE ALL ON TABLE",
    ):
        assert requirement in sql
    assert "SECURITY DEFINER" not in sql
    assert "CREATE ROLE " not in sql
    assert "GRANT EXECUTE" not in sql
    assert "CREATE EXTENSION" not in sql
    assert "dblink" not in sql
    assert "pg_net" not in sql
    assert "Redis" not in sql or "Redis IO" in sql
    assert "public.stage_empire_predictive_v4_projection_held" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


def test_064_fixture_rejects_production_port_before_any_db_access():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432", PGDATABASE="postgres")
    result = subprocess.run(["bash", str(HARNESS)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert "V4_064_DISPOSABLE_ONLY" not in result.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="no disposable PostgreSQL cluster tool")
def test_064_real_postgresql_cas_withdrawal_outbox_append_only_and_rls():
    run = subprocess.run(["pg_virtualenv", "-t", "bash", str(HARNESS)],
                         cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-4000:]
    for expected in (
        "V4_064_ATOMIC_REVISION_AND_TOMBSTONE_FIXTURE=PASS",
        "V4_064_OUTBOX_UNIQUE_RLS_OWNER_HELD=PASS",
        "production_empiredb_writes=false",
        "redis_published=false",
        "money_moved=false",
        "Dropping cluster 18/regress",
    ):
        assert expected in run.stdout + run.stderr
