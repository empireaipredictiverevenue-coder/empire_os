"""Guarded stage-1 deployment script must not activate without DBA authority."""
from pathlib import Path
import subprocess

import pytest

SCRIPT=Path("scripts/deploy_empiredb_tam043_stage1.sh")


def test_deployer_bash_syntax_and_held_invocation():
    result=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    for args in ([],["--apply"],["--approved-stage1"],
                 ["--apply","--not-approved"],["--preflight"]):
        result=subprocess.run(["bash",str(SCRIPT),*args],
                              capture_output=True,text=True,timeout=5)
        assert result.returncode==3
        assert "EXPLICIT_STAGE1_APPROVAL_REQUIRED" in result.stderr


def test_deployer_refuses_nonroot_even_with_approved_stage1_args():
    import os
    if os.geteuid()==0:
        pytest.skip("nonroot enforcement must be exercised as normal ubuntu")
    result=subprocess.run(["bash",str(SCRIPT),"--apply","--approved-stage1"],
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==3
    assert "ROOT_DBA_EXECUTION_REQUIRED" in result.stderr


def test_deployer_has_pinned_reviewed_sql_backup_and_no_stage2_operations():
    text=SCRIPT.read_text()
    assert "63f6699b" in text
    assert "0aa7e8fa" in text
    assert "pg_dump -w -Fc -d empiredb" in text
    assert "pg_dumpall -w --globals-only" in text
    assert "pg_restore --list" in text
    assert "sha256sum -c SHA256SUMS" in text
    assert "SOURCE_TABLE" not in text or "CANONICAL_TABLE" in text
    assert "scripts/preflight_empiredb_tam043_stage1.sql" in text
    assert "scripts/verify_empiredb_tam043_stage1.sql" in text
    assert "BACKUP_SHA256_MISMATCH" in text
    assert "TAM043_RESULT=STAGE1_SQL_INSTALLED_STAGE2_HELD" in text
    assert "TAM043_LOGIN_ENABLED=NO" in text
    assert "TAM043_TAM_MARKET_DATA_READ=NO" in text
    assert "TAM043_OUTBOUND_OR_PAYMENT_AUTHORITY=NONE" in text
    assert "empiredb-tam043-stage1.lock" in text
    assert "EMPIREDB_DSN" in text
    for forbidden in (
        "ALTER ROLE empire_tam_market_login LOGIN",
        "ALTER ROLE empire_tam_market_login PASSWORD",
        "systemctl start empire-tam",
        "systemctl enable empire-tam",
        "/etc/empire/tam-market.dsn",
        "--refresh",
        "get_tam_market_observations(1000)",
    ):
        assert forbidden not in text
