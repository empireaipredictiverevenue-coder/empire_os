"""Original Predictive Cloud V4.7 real disposable PG18 dual-signature acceptance."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/rehearse_predictive_cloud_v47_pg_admission_20261024.sh"
RUN = ROOT / "scripts/rehearse_predictive_cloud_v47_pg_admission_20261024.py"
VERIFIER = ROOT / "empire_os/predictive_cloud_v47_admission_shadow.py"


def test_v47_acceptance_exclusively_uses_existing_held_empiredb_contract():
    sh = SHELL.read_text()
    assert "/tmp/pg_virtualenv.*/data/18/regress" in sh
    assert "PGPORT >= 5433" in sh
    assert "064_predictive_v4_projection_outbox_held.sql" in sh
    assert "CREATE ROLE empiredb_migrator NOLOGIN" in sh
    assert "065_predictive" not in sh
    for forbidden in ("sudo ", "systemctl start", "PGPORT=5432",
                      "apt install", "redis-cli", "empire_ai_main"):
        assert forbidden not in sh


def test_v47_direct_reader_refuses_unauthorised_runtime_and_does_not_embed_keys():
    py = RUN.read_text()
    verifier = VERIFIER.read_text()
    assert 'V47_REFUSE_NON_DISPOSABLE_PG' in py
    assert 'V47_NON_EPHEMERAL_PG_CLUSTER_REFUSED' in py
    assert "BEGIN READ ONLY" in py
    assert "Ed25519PrivateKey.generate()" in py
    assert "trust_roots.source_keys" in verifier
    assert "trust_roots.tenant_keys" in verifier
    assert "production_source_admitted" in verifier
    for forbidden in ("-----BEGIN PRIVATE KEY-----", "PGPASSWORD=",
                      "REDIS_URL=", "create_role(", "public.outbound_intents"):
        assert forbidden not in py + verifier
    assert "predictive_cloud_v47_admission_shadow" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


def test_v47_pg_fixture_refuses_standard_port_before_connecting():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432")
    run = subprocess.run(
        ["bash", str(SHELL)], cwd=ROOT, env=env,
        capture_output=True, text=True, timeout=5,
    )
    assert run.returncode != 0
    assert "V47_DUAL_SIGNATURE_PG18_HELD_BINDING_PASS" not in run.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL unavailable")
def test_v47_pg18_signed_owner_admission_rejection_and_withdrawal():
    run = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(SHELL)],
        cwd=ROOT, capture_output=True, text=True, timeout=90,
    )
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
    records = [json.loads(line) for line in run.stdout.splitlines()
               if line.startswith("{")]
    assert len(records) == 1
    data = records[0]
    assert data["status"] == "V47_DUAL_SIGNATURE_PG18_HELD_BINDING_PASS"
    for key in (
        "independent_source_and_tenant_ed25519_fixture",
        "canonical_pg_owner_readback_bound",
        "cross_tenant_db_row_blocked",
        "source_revocation_blocked",
        "durable_newer_revision_and_withdrawal_blocked",
    ):
        assert data[key] is True
    for key in (
        "production_source_admitted", "real_source_rights_verified",
        "redis_published", "money_moved", "production_empiredb_writes",
    ):
        assert data[key] is False
    assert "Dropping cluster 18/regress" in run.stdout + run.stderr
