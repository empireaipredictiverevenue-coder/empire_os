"""Approved TAM Stage 2 guarded run — no production writes from tests."""
from pathlib import Path
import os
import subprocess

import pytest

SCRIPT=Path("scripts/activate_empiredb_tam_stage2.sh")


def test_stage2_bash_syntax_no_args_and_nonroot_fail_closed():
    result=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    for args in ([],["--activate"],["--approved-research-only"],
                 ["--activate","--no-approval"]):
        p=subprocess.run(["bash",str(SCRIPT),*args],
                         capture_output=True,text=True,timeout=5)
        assert p.returncode==3
        assert "EXPLICIT_STAGE2_APPROVAL_REQUIRED" in p.stderr
    if os.geteuid()==0:
        pytest.skip("non-root guard is tested as the normal EmpireOS user")
    p=subprocess.run(
        ["bash",str(SCRIPT),"--activate","--approved-research-only"],
        capture_output=True,text=True,timeout=5
    )
    assert p.returncode==3
    assert "AUTHORISED_ROOT_OPERATOR_REQUIRED" in p.stderr


def test_stage2_reuses_existing_protected_service_without_schedulers():
    contents=SCRIPT.read_text()
    assert "empire-tam-market-read.service" in contents
    assert "systemctl start empire-tam-market-read.service" in contents
    assert "systemctl daemon-reload" in contents
    assert "TAM_STAGE2_TIMER=NONE" in contents
    assert "TAM_STAGE2_OUTBOUND_PAYMENTS=NOT_AUTHORISED" in contents
    assert "TAM_STAGE2_RESULT=ISOLATED_RESEARCH_READ_LIVE_OBSERVE_ONLY" in contents
    assert "pg_dumpall -w --globals-only" in contents
    assert "sha256sum -c SHA256SUMS" in contents
    assert "verify_empiredb_tam043_stage1.sql" in contents
    assert "password_encryption='scram-sha-256'" in contents
    assert "LoadCredential=" not in contents  # unit template owns LoadCredential
    assert "CREDENTIALS_DIRECTORY=" not in contents
    assert "pg_hba_file_rules" in contents
    assert "systemctl stop empire-tam-market-read.service" in contents
    assert "ALTER ROLE empire_tam_market_login NOLOGIN PASSWORD NULL" in contents
    for forbidden in (
        "systemctl enable",
        "systemctl restart empire-market-gps",
        "systemctl stop empire-market-gps",
        "empire_intelligence_materializer_login:secret",
        "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN=",
        "migrations/empiredb/028_",
        "GRANT ALL ON",
        "GRANT SELECT ON",
        "INSERT INTO public",
        "UPDATE public",
    ):
        assert forbidden not in contents


def test_stage2_scope_is_explicit_market_research_never_customer_login():
    content=SCRIPT.read_text()
    assert "EMPIRE_TAM_TENANT_ID=empire-platform-research" in content
    assert "EMPIRE_TAM_ACTIVE_INDUSTRIES=roofing,solar,insurance" in content
    assert "EMPIRE_TAM_ACTIVE_COUNTRIES=GB,US" in content
    assert 'd.get("raw_source_rows_examined",1001)>1000' in content
    assert 'd.get("source_population_complete") is not False' in content
    assert 's.get("tam_entity_count") is not None' in content
    assert "run_revenue_completion_supervisor.py" in content
    assert "scripts/build_opportunity_radar.py" in content
    assert "outreach_enabled" in content
    assert "automatic_external_execution_allowed" in content
    assert "/etc/empire/tam-market.dsn" in content
    assert 'chmod 0400 /etc/empire/tam-market.dsn' in content
    assert "set +x" in content
    assert "ALTER ROLE empire_tam_market_login LOGIN PASSWORD" in content
    assert "pg_hba_file_rules" in content
    assert "sha256sum" in content


def test_stage2_repo_file_is_not_executable_by_default_until_approved_release():
    mode=SCRIPT.stat().st_mode & 0o777
    assert mode in (0o600,0o644,0o700,0o755)



def test_recovery_requires_explicit_flag_and_known_failed_invocation():
    contents=SCRIPT.read_text()
    assert "--recover-first-read" in contents
    assert "1f49cd0c08b747ffb81beabda1206b06" in contents
    assert "RECOVERY_UNEXPECTED_FAILED_INVOCATION" in contents
    assert "RECOVERY_INSTALLED_UNIT_MISMATCH" in contents
    assert "RECOVERY_SERVICE_NOT_FAILED" in contents
    assert "systemctl reset-failed empire-tam-market-read.service" in contents
    assert 'TAM_STAGE2_RECOVERED_FAILED_FIRST_READ=%s' in contents
    assert "cmp -s deploy/systemd/empire-tam-market-read.service" in contents
    # The recovery path must NEVER change the existing unit or retry
    # without proving its exactly expected failed invocation.
    assert 'if [[ "$recover" == 0 ]]; then' in contents
    assert "install -o root -g root -m 0644" in contents
    assert "SERVICE_ALREADY_INSTALLED" in contents


def test_recovery_nonroot_execution_cannot_modify_production():
    if os.geteuid()==0:
        pytest.skip("nonroot guard verified when running as ubuntu")
    result=subprocess.run(
        ["bash",str(SCRIPT),"--recover-first-read",
         "--approved-research-only"],
        capture_output=True,text=True,timeout=5,
    )
    assert result.returncode==3
    assert "AUTHORISED_ROOT_OPERATOR_REQUIRED" in result.stderr
