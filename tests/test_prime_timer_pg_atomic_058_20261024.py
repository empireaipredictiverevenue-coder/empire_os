"""Original EmpireDB 058 atomic timer transition test, never production.

Each real SQL fixture creates/drops its own pg_virtualenv cluster.
The executable refuses the main PostgreSQL 5432 and non-temporary data dirs.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT / "migrations/empiredb/058_flagship_timer_atomic_transition_held.sql"
SCRIPT=ROOT / "scripts/rehearse_prime_timer_pg_atomic_058_20261024.sh"


def test_058_never_grants_a_new_public_or_runtime_executor():
    data=SQL.read_text()
    lines=[line.strip().lower() for line in data.splitlines()
           if line.strip() and not line.lstrip().startswith("--")]
    assert "set local role empiredb_migrator;" in lines
    assert "revoke all on function public.empire_prime_voice_timer_transition_held(" in data.lower()
    assert "revoke all on function public.empire_prime_voice_timer_insert_guard_held() from public;" in data.lower()
    assert "security definer" in data.lower()
    assert "for update" in data.lower()
    assert "timer058_illegal_or_undue_transition" in data.lower()
    assert "pg_catalog.clock_timestamp()" in data.lower()
    assert "timer058_migrator_membership_requires_security_review" in data.lower()
    assert not any(line.startswith(("grant ","create role ","create user ","create login ",
                                    "create extension ","create scheduled","update ",
                                    "delete from ")) for line in lines)
    assert not any("to public" in line for line in lines if line.startswith("create policy"))


def test_058_fixture_refuses_original_postgresql_port_without_query():
    env=dict(os.environ)
    env["PGPORT"]="5432"
    env["PGHOST"]="/tmp"
    result=subprocess.run(["bash",str(SCRIPT)],cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==9
    assert "REFUSED_NON_EPHEMERAL_PGPORT" in result.stdout
    assert "EPHEMERAL_PG058_ATOMIC_TRANSITIONS_PASS" not in result.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL fixture not installed")
def test_058_actual_postgres_claim_cancel_trigger_and_concurrency():
    result=subprocess.run(
        ["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT,capture_output=True,text=True,timeout=90,
    )
    assert result.returncode==0,result.stdout[-5000:]+"\n"+result.stderr[-1500:]
    assert "EPHEMERAL_PG058_ATOMIC_TRANSITIONS_PASS checks=29" in result.stdout
    assert "port=5433" in result.stdout
    assert "production_touched=false" in result.stdout
    assert "external_notifications=0" in result.stdout
    assert "runtime_grants=0" in result.stdout
    assert "rollback removes RLS policies" in result.stdout
    assert "no PUBLIC EXECUTE permission on either function" in result.stdout
    assert "direct superuser INSERT cannot skip provider state" in result.stdout
    assert "future timer cancellation is atomic" in result.stdout
    assert "two concurrent workers yield one atomic claim and one refused replay" in result.stdout
    assert "single DB event after concurrent claim" in result.stdout
    assert "Dropping cluster 18/regress" in result.stdout+result.stderr
