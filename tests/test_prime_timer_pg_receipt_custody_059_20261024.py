"""Original EmpireDB migration 059 against throwaway PostgreSQL; never production.

No real provider callback, customer, user/device, app runtime grant, live
scheduler, email, webhook or production original EmpireDB mutation.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT / "migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql"
SCRIPT=ROOT / "scripts/rehearse_prime_timer_pg_receipt_custody_059_20261024.sh"


def test_059_migration_is_held_and_provides_zero_runtime_delivery_authority():
    sql=MIGRATION.read_text()
    active=[
        line.strip().lower()
        for line in sql.splitlines()
        if line.strip() and not line.lstrip().startswith("--")
    ]
    normalized="\n".join(active)
    assert "timer059_wrong_database" in normalized
    assert "timer059_requires_original_ledger_057_and_guard_058" in normalized
    assert "timer059_migrator_role_membership_unreviewed" in normalized
    assert "set local role empiredb_migrator;" in active
    assert "unique (provider_code,callback_nonce_digest)" in normalized
    assert "unique (provider_code,receipt_digest)" in normalized
    assert "claim_event_digest" in normalized
    assert "for update" in normalized
    assert "timer059_first_receipt_must_accept_or_fail" in normalized
    assert "timer059_illegal_or_replayed_receipt_transition" in normalized
    assert "timer059_terminal_receipt_no_retry" in normalized
    assert "force row level security" in normalized
    assert "revoke all on function public.empire_prime_timer_provider_receipt_guard_held()" in normalized
    assert not any(line.startswith((
        "grant ","create role ","create user ","create login ",
        "create extension ","insert into ","update ","delete from ",
    )) for line in active)
    assert "source_attestation_digest" in normalized
    assert "real device" not in normalized
    assert "no runtime grants" in sql.lower()
    assert "no live provider" in sql.lower()


def test_059_refuses_canonical_postgresql_port_without_connecting():
    env=dict(os.environ)
    env["PGPORT"]="5432"
    env["PGHOST"]="/tmp"
    run=subprocess.run(
        ["bash",str(SCRIPT)],cwd=ROOT,env=env,text=True,
        capture_output=True,timeout=5,
    )
    assert run.returncode==9
    assert "REFUSED_NON_EPHEMERAL_PGPORT" in run.stdout
    assert "EPHEMERAL_PG059_RECEIPT_CUSTODY_PASS" not in run.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="throwaway PostgreSQL fixture utility not installed")
def test_059_actual_postgresql_rejects_replays_across_connections_and_workers():
    run=subprocess.run(
        ["pg_virtualenv","-t","bash",str(SCRIPT)],
        cwd=ROOT, text=True,capture_output=True,timeout=100,
    )
    assert run.returncode==0,run.stdout[-5000:]+"\n"+run.stderr[-1800:]
    assert "EPHEMERAL_PG059_RECEIPT_CUSTODY_PASS checks=35" in run.stdout
    assert "port=5433" in run.stdout
    assert "production_touched=false" in run.stdout
    assert "provider_network_calls=0" in run.stdout
    assert "late error rolls back receipt table" in run.stdout
    assert "receipt table FORCE RLS enabled" in run.stdout
    assert "ordered callback chain persisted in PostgreSQL" in run.stdout
    assert "two competing PostgreSQL sessions cannot record same callback nonce twice" in run.stdout
    assert "one persisted callback nonce after concurrent race" in run.stdout
    assert "FORCE RLS hides synthetic callbacks from fixture role" in run.stdout
    assert "no sender or delivery RPC installed" in run.stdout
    assert "Dropping cluster 18/regress" in run.stdout+run.stderr
