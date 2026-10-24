"""Original ASTRA synthetic signed callback -> SCRAM-login held EmpireDB 060.

An integrated, isolated PostgreSQL fixture. This NEVER opens production DB,
a real provider, a webhook, a sender, actual user consent or external devices.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
SHELL=ROOT/"scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh"
PYTHON=ROOT/"scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py"


def test_standalone_bridge_refuses_any_unverified_db_target_before_connecting():
    env=dict(os.environ)
    env["PGPORT"]="5432"
    env["PGHOST"]="localhost"
    env["PGDATABASE"]="postgres"
    env.pop("EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED",None)
    run=subprocess.run(
        [sys.executable,"-B",str(PYTHON)],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=5,
    )
    assert run.returncode!=0
    assert "REFUSED_NON_EPHEMERAL_SIGNED_GATEWAY_DB_TARGET" in run.stderr
    assert "SIGNED_SYNTHETIC_CALLBACKS_PERSISTED" not in run.stdout


def test_shell_fixture_refuses_normal_postgres_port_without_query():
    env=dict(os.environ)
    env["PGPORT"]="5432"
    env["PGHOST"]="localhost"
    run=subprocess.run(
        ["bash",str(SHELL)],cwd=ROOT,env=env,
        capture_output=True,text=True,timeout=5,
    )
    assert run.returncode==9
    assert "REFUSED_NON_EPHEMERAL_PGPORT" in run.stdout


def test_bridge_uses_only_verified_signed_payload_and_locks_fixture_consent():
    text=PYTHON.read_text()
    assert 'payload=envelope["payload"]' in text
    assert 'owner_payload=owner["payload"]' in text
    assert "fixture_lock_current_test_consent" in text
    assert "_actual_fixture_identity_reader()" in text
    assert "FOR SHARE" in SHELL.read_text()
    assert "SYNTHETIC_IN_TRANSACTION_CONSENT_REVOKED" in text
    assert "REFUSED_NON_TEMPORARY_SIGNED_GATEWAY_DB_CLUSTER" in text
    assert "source_attestation_digest" in text
    assert "callback_nonce_digest" in text
    assert "fixture_authorised_device" in text
    assert "_actual_fixture_login()" in text
    assert "timer_fixture_gateway_login" in text
    assert "password=secret" in text
    assert "SET LOCAL ROLE timer_fixture_gateway_exec" not in text
    assert "public.empire_prime_timer_receipt_record_held(" in text
    assert "INSERT INTO public.empire_prime_timer_provider_receipts" not in text
    assert "original_empiredb_writes" not in text or "production_empiredb_writes" in text


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL fixture utility missing")
def test_real_pg060_restricted_writer_records_verified_fictional_callbacks_only_once():
    run=subprocess.run(
        ["pg_virtualenv","-t","bash",str(SHELL)],
        cwd=ROOT,capture_output=True,text=True,timeout=90,
    )
    assert run.returncode==0,run.stdout[-5500:]+"\n"+run.stderr[-2500:]
    start=run.stdout.index("{")
    end=run.stdout.index("\n}",start)+2
    receipt=json.loads(run.stdout[start:end])
    assert receipt["status"]=="SIGNED_SYNTHETIC_CALLBACKS_PERSISTED_IN_TEMP_POSTGRES"
    assert receipt["checks_passed"]==6
    assert receipt["receipt_rows_verified"]==2
    assert receipt["independent_database_connections_used"] is True
    expected={
        "VALID_SIGNED_ACCEPTED_CALLBACK_PERSISTED",
        "RECONNECT_REPLAY_REJECTED_WITHOUT_SECOND_WRITE",
        "FORGED_PROVIDER_SIGNATURE_ZERO_WRITES",
        "REVOKED_OWNER_CONSENT_ZERO_WRITES",
        "DB_CONSENT_REVOCATION_PREVENTED_WRITE",
        "SIGNED_DELIVERED_REPORT_ORDERED_WITH_PREVIOUS_ACCEPTED",
    }
    assert set(receipt["checks"])==expected
    assert receipt["real_provider_authenticated"] is False
    assert receipt["real_consent_verified"] is False
    assert receipt["real_device_delivered"] is False
    assert receipt["live_sender_activated"] is False
    assert receipt["production_empiredb_writes"] is False
    assert receipt["execution_authority"]=="fixture_only"
    assert "SIGNED_GATEWAY_060_RESTRICTED_PG_FIXTURE_FINISHED production_touched=false provider_network_calls=0" in run.stdout
    assert "EPHEMERAL_SCRAM_LOGIN_AUTHENTICATED=true" in run.stdout
    assert "SCRAM_WRONG_PASSWORD_AND_HIGH_PRIVILEGES_DENIED=true" in run.stdout
    assert "SCRAM_OTHER_DATABASES_REJECTED=true" in run.stdout
    assert "REAL_SCRAM_LOGIN_NO_TABLE_PERMISSIONS=true" in run.stdout
    assert "SCRAM_LOGIN_DIRECT_TABLE_SELECT_DENIED=true" in run.stdout
    assert "INDEPENDENT_SCRAM_TENANT_SCOPED_READER_AUTHENTICATED=true" in run.stdout
    assert "INDEPENDENT_READER_TENANT_RLS_AND_NO_WRITES=PASS" in run.stdout
    assert "SCRAM_LOGIN_TWO_WORKERS_ONE_CALLBACK=true" in run.stdout
    assert "Dropping cluster 18/regress" in run.stdout+run.stderr


def test_reader_is_separate_from_writer_and_cannot_obtain_table_mutation_rights():
    source=PYTHON.read_text()
    fixture=SHELL.read_text()
    assert 'user="timer_fixture_identity_reader_login"' in source
    assert 'user="timer_fixture_gateway_login"' in source
    assert 'password=secret' in source
    assert 'REFUSED_FIXTURE_READER_WRITE_OR_EXECUTE_PRIVILEGE' in source
    assert 'fixture_lock_current_test_consent' in source
    assert 'timer_fixture_reader_request_held' in fixture
    assert 'timer_fixture_reader_event_held' in fixture
    assert 'timer_fixture_reader_receipt_held' in fixture
    assert 'timer_fixture_reader_consent_held' in fixture
    assert 'CREATE ROLE timer_fixture_identity_reader_login LOGIN PASSWORD' in fixture
    assert 'NOINHERIT NOBYPASSRLS' in fixture
    assert 'READER_RLS_CROSS_TENANT_REQUEST_LEAK' in fixture
    assert 'READER_RLS_CROSS_TENANT_CONSENT_LEAK' in fixture
    assert 'READER_RLS_CROSS_TENANT_CLAIM_LEAK' in fixture
    assert 'READER_RLS_CROSS_TENANT_RECEIPT_LEAK' in fixture
    assert 'READER_RLS_OWN_RECEIPT_READ_FAILED' in fixture
    assert 'READER_CONSENT_UPDATE_WRONGLY_ACCEPTED' in fixture
    assert 'READER_WRITER_EXECUTE_WRONGLY_ACCEPTED' in fixture
    assert 'READER_LOCK_CROSSTENANT_AUTHORITY_LEAK' in fixture
    assert 'INDEPENDENT_READER_TENANT_RLS_AND_NO_WRITES=PASS' in fixture
    assert 'REVOKE ALL ON FUNCTION public.fixture_lock_current_test_consent' in fixture
