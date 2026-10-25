"""V4.8 first-party CRM bearer + held Predictive Cloud admission gauntlet.

Read-only except for isolated PG18 fixture's prepared CRM/held schemas and
fictional membership state changes. No production keys or permissions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from empire_os.predictive_cloud_v48_crm_bound_shadow import (
    V48MembershipHold, review_crm_bound_admission_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "scripts/rehearse_predictive_cloud_v48_crm_bound_20261025.sh"
SCRIPT = ROOT / "scripts/rehearse_predictive_cloud_v48_crm_bound_20261025.py"


def test_v48_rejects_untrusted_or_malformed_crm_verifier_before_source_review():
    with pytest.raises(V48MembershipHold, match="original_crm_verifier_required"):
        review_crm_bound_admission_fixture(
            {"claim": {"tenant_id": "fake"}},
            signed_crm_bearer="made.up.token", crm_verifier=object(),
            canonical_row={}, trust_roots=object(), revocations=object(), now=None,
        )


def test_v48_crm_native_bearer_and_source_integrity_hold_only():
    py = (ROOT / "empire_os/predictive_cloud_v48_crm_bound_shadow.py").read_text()
    assert "SignedCrmTenantVerifier" in py
    assert "crm_verifier.authenticate(signed_crm_bearer)" in py
    assert "review_signed_source_fixture(" in py
    assert "production_source_admitted\": False" in py
    assert "redis_publish_authorized\": False" in py
    assert "live_production_crm_membership_attested\": False" in py
    assert "recognized_revenue_cents\": None" in py
    for forbidden in (
        "psycopg.connect(", "redis.Redis(", "send_message(",
        "create_router(", "execute_payment(", "os.environ",
        "BEGIN PRIVATE KEY",
    ):
        assert forbidden not in py
    assert "predictive_cloud_v48_crm_bound_shadow" not in (
        ROOT / "empire_os/hub.py"
    ).read_text()


def test_v48_temporary_pg18_guard_and_original_prepared_sql_only():
    sh = SHELL.read_text()
    assert "PGPORT >= 5433" in sh
    assert "/tmp/pg_virtualenv.*/data/18/regress" in sh
    assert "041_crm_membership_authority.sql" in sh
    assert "064_predictive_v4_projection_outbox_held.sql" in sh
    assert "createdb -E UTF8 -T template0" in sh
    assert "ALTER ROLE empire_crm_membership_login PASSWORD" in sh
    assert "empire_crm_read_member(text,uuid)" in sh
    for forbidden in ("sudo ", "systemctl start", "PGPORT=5432",
                      "redis-server", "apt install", "--port 6379"):
        assert forbidden not in sh


def test_v48_rejects_default_postgres_port_before_any_mutation():
    env = dict(os.environ, PGHOST="localhost", PGPORT="5432")
    run = subprocess.run(
        ["bash", str(SHELL)], cwd=ROOT, env=env,
        text=True, capture_output=True, timeout=5,
    )
    assert run.returncode != 0
    assert "V48_ORIGINAL_CRM041_AND_HELD064_BINDING_PASS" not in run.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL unavailable")
def test_v48_native_crm_signed_bearer_and_pg_membership_revalidation():
    run = subprocess.run(
        ["pg_virtualenv", "-t", "bash", str(SHELL)],
        cwd=ROOT, text=True, capture_output=True, timeout=100,
    )
    assert run.returncode == 0, run.stdout[-6000:] + run.stderr[-4000:]
    rows = [json.loads(line) for line in run.stdout.splitlines()
            if line.startswith("{")]
    assert len(rows) == 1
    output = rows[0]
    assert output["status"] == "V48_ORIGINAL_CRM041_AND_HELD064_BINDING_PASS"
    for field in (
        "real_ephemeral_pg18_crm_membership_reader_used",
        "signed_crm_bearer_verified_by_original_verifier",
        "owner_dual_signatures_bound_to_held_pg_event",
        "separate_tenant_denied",
        "revoked_membership_denied",
        "tampered_bearer_denied",
        "newer_source_withdrawal_denied",
    ):
        assert output[field] is True
    for field in (
        "redis_publish_authorized", "production_source_admitted",
        "live_db_touched", "real_source_rights_verified", "financial_execution",
    ):
        assert output[field] is False
    assert "Dropping cluster 18/regress" in run.stdout + run.stderr
