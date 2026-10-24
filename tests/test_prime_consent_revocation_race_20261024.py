"""Original PRIME/ASTRA: real PostgreSQL synthetic consent revocation race."""
from __future__ import annotations
from pathlib import Path
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RACE=ROOT/"scripts/rehearse_prime_consent_revocation_race_20261024.py"
FIXTURE=ROOT/"scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh"


def test_race_rehearsal_refuses_unverified_database_and_leaks_no_secrets():
    env=dict(os.environ)
    for key in ("EMPIRE_SIGNED_GATEWAY_FIXTURE_CHECKED",
                "EMPIRE_FIXTURE_READER_PASSWORD","EMPIRE_FIXTURE_LOGIN_PASSWORD"):
        env.pop(key,None)
    env.update({"PGPORT":"5432","PGHOST":"localhost","PGDATABASE":"postgres"})
    run=subprocess.run([sys.executable,"-B",str(RACE)],cwd=ROOT,env=env,
                       capture_output=True,text=True,timeout=5)
    assert run.returncode!=0
    assert "REFUSED_NON_EPHEMERAL_SIGNED_GATEWAY_DB_TARGET" in run.stderr
    assert "TWO_REAL_POSTGRESQL_REVOCATION_ORDERINGS_PASS" not in run.stdout


def test_two_lock_orderings_include_independent_scram_reader_writer():
    contents=RACE.read_text()
    fixture=FIXTURE.read_text()
    assert "_actual_fixture_identity_reader" in contents
    assert "_actual_fixture_login" in contents
    assert "SELECT public.fixture_lock_current_test_consent" in contents
    assert "_wait_for_block(READER_WAIT)" in contents
    assert "_wait_for_block(REVOKER_WAIT)" in contents
    assert "wait_event_type='Lock'" in contents
    assert "_count_receipts(revoked[0])==0" in contents
    assert "_count_receipts(before[0])==1" in contents
    assert '"real_device_alerts":0' in contents
    assert "rehearse_prime_consent_revocation_race_20261024.py" in fixture
    assert "pg_virtualenv" in fixture
    assert "REFUSED_NON_EPHEMERAL_PGPORT" in fixture
