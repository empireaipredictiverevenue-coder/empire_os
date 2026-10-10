"""TAM044 one-shot promote script: refusal, scope, safety and rollback."""
from pathlib import Path
import os
import subprocess

import pytest

SCRIPT=Path("scripts/promote_empiredb_tam044_one_shot.sh")


def run(*args):
    return subprocess.run(["bash",str(SCRIPT),*args],
        capture_output=True,text=True,timeout=5)


def test_bash_syntax_and_no_implicit_one_shot_approval():
    proc=subprocess.run(["bash","-n",str(SCRIPT)],
        capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    for args in ((),("--one-shot",),("--approved-scoped-research",),
                 ("--one-shot","--wrong"),("--apply","--approved-044")):
        result=run(*args)
        assert result.returncode==3
        assert "EXPLICIT_ONE_SHOT_APPROVAL_REQUIRED" in result.stderr


def test_authorised_one_shot_args_never_run_as_nonroot():
    if os.geteuid()==0:
        pytest.skip("non-root check is verified by the ubuntu runtime")
    result=run("--one-shot","--approved-scoped-research")
    assert result.returncode==3
    assert "ROOT_REQUIRED" in result.stderr


def test_preexisting_static_service_and_private_credential_are_reused():
    text=SCRIPT.read_text()
    assert "empire-tam-market-read.service" in text
    assert "UnitFileState --value" in text
    assert "cmp -s deploy/systemd/empire-tam-market-read.service" in text
    assert "/etc/empire/tam-market.dsn" in text
    assert "TAM_EXISTING_SECRET_UNVERIFIED" in text
    assert "scripts/verify_empiredb_tam044.sql" in text
    assert "flock -n -x 9" in text
    assert "systemctl start empire-tam-market-read.service" in text
    for forbidden in (
        "systemctl enable",
        "systemctl restart",
        "systemctl daemon-reload",
        "ALTER ROLE",
        "CREATE ROLE",
        "GRANT EXECUTE",
        "get_tam_market_observations_scoped(",  # only the protected unit may read
        "source /etc/empire/tam-market.dsn",
        "cat /etc/empire/tam-market.dsn",
        "EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",
        "market-gps.service",
    ):
        assert forbidden not in text


def test_one_shot_scope_limit_fails_closed_before_new_data_read():
    text=SCRIPT.read_text()
    for expected in (
        "EMPIRE_TAM_TENANT_ID=empire-platform-research",
        "EMPIRE_TAM_ACTIVE_INDUSTRIES=roofing,solar,insurance",
        "EMPIRE_TAM_ACTIVE_COUNTRIES=GB,US",
        "EMPIRE_TAM_READER_MODE=scoped_v1",
        "TAM044_SCOPED_RESEARCH_EVIDENCE_INVALID",
        "MARKET_QUOTA_SAMPLED",
        "requested_market_scope_count",
        "market_scope_sample_coverage",
        "requested_sample_limit",
        "TAM044_READ_RESULT=MARKET_AWARE_OBSERVE_VERIFIED",
    ):
        assert expected in text
    assert "data.get('requested_sample_limit')!=1000" in text
    assert "proof.get('requested_market_scope_count')!=6" in text
    assert "outreach_enabled" in text
    assert "automatic_external_execution_allowed" in text
    assert "market_size_claims':0" in text
    assert "TAM044_READ_NEW_TIMER=NONE" in text


def test_previous_market_snapshot_and_radar_will_be_restored_if_verification_fails():
    text=SCRIPT.read_text()
    for evidence in (
        "tam.before.json",
        "radar.before.json",
        "founder.before.json",
        "scope.before",
        "sha256sum -c SHA256SUMS",
        "restore \"$backup/tam.before.json\" \"$tam\"",
        "restore \"$backup/radar.before.json\" \"$radar\"",
        "restore \"$backup/founder.before.json\" \"$founder\"",
        "install -o root -g root -m 0600 \"$backup/scope.before\" \"$scope\"",
        "TAM044_READ_ROLLBACK=ATTEMPTED_RESTORE_SCOPE_AND_PRIVATE_SNAPSHOTS",
        "TAM044_READ_RESULT=FAILED_REVIEW_BEFORE_RETRY",
    ):
        assert evidence in text
    assert text.index("TAM044_READ_BASELINE_BACKUP=SHA256_VERIFIED") < text.index(
        "mv -f \"$new_scope\" \"$scope\""
    )
