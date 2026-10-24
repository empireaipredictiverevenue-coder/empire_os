"""Original PRIME consent-bound database regression, fictional fixture only."""
from pathlib import Path
import os
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/'migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql'
FIXTURE=ROOT/'scripts/rehearse_prime_consent_gate_061_20261024.sh'
BOOTSTRAP=ROOT/'scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh'


def test_061_migration_deny_by_default_no_live_grants():
    source=MIGRATION.read_text().lower()
    for required in ('return false;', 'before insert on public.empire_prime_timer_provider_receipts', 'timer061_original_consent_authority_unverified', 'revoke all on function', 'security definer', "set search_path=''", 'set row_security=on'):
        assert required in source
    assert not any(line.strip().startswith('grant ') for line in source.splitlines())


def test_061_fixture_must_be_opted_into_explicitly():
    assert 'disposable_only' in BOOTSTRAP.read_text()
    assert 'fixture_authorised_device' in FIXTURE.read_text()
    assert 'PG061_DENY_WITHOUT_ORIGINAL_CONSENT_AUTHORITY=PASS' in FIXTURE.read_text()


def test_061_refuses_main_db_port():
    env=dict(os.environ)
    env.pop('EMPIRE_FIXTURE_LOGIN_PASSWORD',None)
    env.update(PGPORT='5432',PGDATABASE='postgres',PGHOST='localhost')
    out=subprocess.run(['bash',str(FIXTURE)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=5)
    assert out.returncode!=0


@pytest.mark.skipif(shutil.which('pg_virtualenv') is None,reason='temporary PG not installed')
def test_061_real_disposable_postgres_deny_and_revocation_race():
    env=dict(os.environ)
    env['EMPIRE_REHEARSE_HELD_CONSENT_061']='disposable_only'
    out=subprocess.run(['pg_virtualenv','-t','bash',str(BOOTSTRAP)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
    assert out.returncode==0,out.stdout[-4000:]+out.stderr[-2000:]
    for marker in ('PG061_DEFAULT_DENY_TRIGGER_NO_PUBLIC_GRANTS=PASS','PG061_DENY_WITHOUT_ORIGINAL_CONSENT_AUTHORITY=PASS','PG061_CONSENT_CHECK_ENFORCED_INSIDE_SQL_WRITER=PASS','PG061_REVOKED_CONSENT_REFUSES_WRITER_WITHOUT_ASTRA_PREFLIGHT=PASS','PG061_REVOKE_FIRST_RESTRICTED_WRITER_BLOCKED_AND_REFUSED=PASS','ORIGINAL_EMPIREDB_061_FIXTURE_PASS production_touched=false provider_calls=0 real_alerts=0 fake_consent=true'):
        assert marker in out.stdout
    assert 'Dropping cluster 18/regress' in out.stdout+out.stderr
