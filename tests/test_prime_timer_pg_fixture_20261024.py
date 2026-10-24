"""Actual disposable PostgreSQL 18 migration-057 DBA fixture smoke test.

This test must use pg_virtualenv's temporary data directory and port >5432.
The fixture script itself refuses any other data directory / production port.
No canonical EmpireDB migration is performed.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/rehearse_prime_timer_pg_fixture_20261024.sh"


def test_fixture_script_rejects_non_ephemeral_postgresql_port_without_connecting():
    env = dict(os.environ)
    env["PGPORT"] = "5432"
    env["PGHOST"] = "/tmp"
    done = subprocess.run(
        ["bash", str(SCRIPT)], cwd=REPO, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5,
    )
    assert done.returncode == 9
    assert "REFUSED_NON_EPHEMERAL_PGPORT" in done.stdout
    assert "EPHEMERAL_POSTGRES_FIXTURE_PASS" not in done.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL tool unavailable")
def test_real_postgresql_fixture_executes_held_ddl_and_proves_known_gap():
    completed = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(SCRIPT)],
        cwd=REPO, text=True, capture_output=True, timeout=90,
    )
    assert completed.returncode == 0, (
        completed.stdout[-6000:] + "\n" + completed.stderr[-3000:]
    )
    assert "EPHEMERAL_POSTGRES_FIXTURE_PASS count=30" in completed.stdout
    assert "pg_port=5433" in completed.stdout
    assert "production_touched=false" in completed.stdout
    assert "provider_transition_writer=NOT_IMPLEMENTED" in completed.stdout
    assert "known gap demonstrated: raw SQL accepts reported delivery without prior claim" in completed.stdout
    assert "FORCE RLS hides existing request from fixture role" in completed.stdout
    assert "late DDL error rolls back all tables" in completed.stdout
    assert "semantic-gap transaction rolled back" in completed.stdout
    assert "Dropping cluster 18/regress" in completed.stdout + completed.stderr
