"""Original PRIME held device-specific consent metadata, real disposable PG18."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/"migrations/empiredb/062_flagship_device_binding_consent_events_held.sql"
FIXTURE=ROOT/"scripts/rehearse_prime_device_binding_062_20261024.sh"
BOOTSTRAP=ROOT/"scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh"


def test_062_schema_has_tenant_actor_device_foreign_keys_and_zero_runtime_grants():
    source=MIGRATION.read_text().lower()
    for token in (
        "timer062_wrong_database",
        "timer062_original_057_to_061_required",
        "timer062_already_present_owner_review_required",
        "empire_prime_reminder_devices_held",
        "empire_prime_reminder_timer_devices_held",
        "empire_prime_reminder_consent_events_held",
        "primary key(tenant_id,timer_digest)",
        "primary key(tenant_id,actor_digest,device_digest)",
        "foreign key(tenant_id,actor_digest,device_digest)",
        "original_timer_actor_source_consent_mismatch",
        "timer062_first_event_must_grant",
        "timer062_consent_event_order_or_duplicate",
        "for update",
        "before update or delete",
        "force row level security",
        "empiredb_migrator",
        "revoke all on table",
        "revoke all on function",
        "security definer",
    ):
        assert token in source,token
    assert "create or replace function public.empire_prime_timer_consent_authority_held" not in source
    assert not any(line.strip().startswith(("grant ","create user ","create role "))
                   for line in source.splitlines())
    assert "no production" in source


def test_062_has_explicit_opt_in_and_is_not_part_of_normal_061_fixture():
    bootstrap=BOOTSTRAP.read_text()
    source=FIXTURE.read_text()
    assert "EMPIRE_REHEARSE_HELD_DEVICE_062" in bootstrap
    assert '"disposable_only"' in bootstrap
    assert "EMPIRE_REHEARSE_HELD_CONSENT_061" in bootstrap
    assert "pg_virtualenv." in source
    assert "PG062_NO_AUTO_PROMOTION_OF_UNVERIFIED_DEVICE_CONSENT=PASS" in source
    assert "PG062_REVOCATION_TIED_TO_BOUND_DEVICE_NOT_OTHER_DEVICE=PASS" in source
    assert "PG062_REVOKE_EVENT_FIRST_PREVENTS_LATE_WRITER=PASS" in source
    assert "FICTIONAL_OWNER_ADAPTER" not in source
    assert "TEST_ADAPTER" in source


def test_062_refuses_canonical_pg_port_and_missing_fixture():
    env=dict(os.environ)
    env.update({
        "PGPORT":"5432","PGHOST":"localhost",
        "PGDATABASE":"postgres",
        "EMPIRE_REHEARSE_HELD_CONSENT_061":"disposable_only",
        "EMPIRE_REHEARSE_HELD_DEVICE_062":"disposable_only",
    })
    env.pop("EMPIRE_FIXTURE_LOGIN_PASSWORD",None)
    result=subprocess.run(["bash",str(FIXTURE)],cwd=ROOT,
                          env=env,capture_output=True,text=True,timeout=5)
    assert result.returncode!=0
    assert "ORIGINAL_PG062_DEVICE_BINDING_FIXTURE_PASS" not in result.stdout


@pytest.mark.skipif(shutil.which("pg_virtualenv") is None,
                    reason="disposable PostgreSQL cluster utility unavailable")
def test_062_real_pg18_binding_consent_revocation_and_callback_gate():
    env=dict(os.environ)
    env["EMPIRE_REHEARSE_HELD_CONSENT_061"]="disposable_only"
    env["EMPIRE_REHEARSE_HELD_DEVICE_062"]="disposable_only"
    result=subprocess.run(
        ["pg_virtualenv","-t","bash",str(BOOTSTRAP)],
        cwd=ROOT,env=env,capture_output=True,text=True,timeout=140,
    )
    assert result.returncode==0,result.stdout[-6000:]+"\n"+result.stderr[-1500:]
    for line in (
        "PG062_HELD_SCHEMA_FORCE_RLS_NO_RUNTIME_GRANTS=PASS",
        "PG062_TIMER_TO_ONE_MATCHING_ACTOR_DEVICE=PASS",
        "PG062_DIFFERENT_ENROLLED_ACTOR_CANNOT_BIND_ORIGINAL_TIMER=PASS",
        "PG062_NO_AUTO_PROMOTION_OF_UNVERIFIED_DEVICE_CONSENT=PASS",
        "PG062_FIXTURE_ONLY_DEVICE_GRANT_ALLOW_VERIFIED_BY_DB=PASS",
        "PG062_REVOCATION_TIED_TO_BOUND_DEVICE_NOT_OTHER_DEVICE=PASS",
        "PG062_EXPLICIT_NEW_GRANT_RESTORES_ONLY_FIXTURE_CUSTODY=PASS",
        "PG062_REVOKE_EVENT_FIRST_PREVENTS_LATE_WRITER=PASS",
        "ORIGINAL_PG062_DEVICE_BINDING_FIXTURE_PASS production_touched=false real_consent=false real_device_alerts=0",
    ):
        assert line in result.stdout,line
    assert result.stdout.count("062_REJECTED=TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED")>=3
    assert "Dropping cluster 18/regress" in result.stdout+result.stderr
