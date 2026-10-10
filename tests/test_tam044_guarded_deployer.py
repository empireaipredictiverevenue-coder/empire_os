"""044 guarded release static and fail-closed execution gates."""
from pathlib import Path
import os
import subprocess

import pytest

SCRIPT=Path("scripts/deploy_empiredb_tam044.sh")


def test_tam044_deployment_held_without_exact_stage_approval():
    p=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    for args in ([],["--apply"],["--approved-044"],["--apply","--wrong"]):
        res=subprocess.run(["bash",str(SCRIPT),*args],
           capture_output=True,text=True,timeout=5)
        assert res.returncode==3
        assert "EXPLICIT_TAM044_APPROVAL_OR_PREFLIGHT_REQUIRED" in res.stderr


def test_tam044_deployer_requires_authorised_db_root():
    if os.geteuid()==0:
        pytest.skip("non-root guard is verified by normal EmpireOS user")
    for args in (["--apply","--approved-044"],["--preflight"]):
        res=subprocess.run(["bash",str(SCRIPT),*args],
           capture_output=True,text=True,timeout=5)
        assert res.returncode==3
        assert "AUTHORISED_DBA_ROOT_REQUIRED" in res.stderr


def test_tam044_pins_sql_and_performs_backup_before_ddl():
    text=SCRIPT.read_text()
    assert "TAM044_BACKUP=VERIFIED_FORMAT_AND_SHA256" in text
    assert "pg_dump -w -Fc -d empiredb" in text
    assert "pg_dumpall -w --globals-only" in text
    assert "sha256sum -c SHA256SUMS" in text
    assert "preflight_empiredb_tam044.sql" in text
    assert "verify_empiredb_tam044.sql" in text
    assert "migrations/empiredb/044_tam_scoped_market_sampling.sql" in text
    assert "TAM044_NEW_MARKET_DATA_READ=NO" in text
    assert "TAM044_READER_MODE_CHANGE=NO" in text
    assert "TAM044_OUTBOUND_OR_PAYMENTS_AUTHORITY=NONE" in text
    assert "TAM044_RESULT=SCOPED_FUNCTION_INSTALLED_READER_MODE_HELD" in text
    assert "flock -n -x 9" in text
    assert text.index("TAM044_BACKUP=VERIFIED_FORMAT_AND_SHA256") < text.index(
        'if ! runuser -u postgres -- psql'
    )
    for forbidden in (
      "ALTER ROLE empire_tam_market_login",
      "DROP FUNCTION public.get_tam_market_observations(integer)",
      "EMPIRE_TAM_READER_MODE=scoped_v1",
      "systemctl restart",
      "systemctl start",
      "systemctl enable",
      "--refresh",
      "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
      "/etc/empire/tam-market.dsn",
    ):
        assert forbidden not in text
