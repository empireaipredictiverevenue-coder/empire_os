"""Guarded Cloud service install contract (never invoke privileged apply)."""
from pathlib import Path
import subprocess

INSTALLER = Path(__file__).resolve().parents[1] / (
    "scripts/install_guarded_predictive_cloud_materializer_20261021.sh"
)


def test_install_requires_exact_commit_and_explicit_apply():
    for args in [(), ("--check",), ("--check", "main"),
                 ("--apply-owner-approved-observe", "bogus")]:
        result = subprocess.run(
            ["bash", str(INSTALLER), *args],
            text=True, capture_output=True, timeout=12, check=False,
        )
        assert result.returncode != 0
        assert "PREDICTIVE_CLOUD_GUARD_DEPLOYED" not in result.stdout


def test_guard_never_edits_db_or_mutable_original_source():
    script = INSTALLER.read_text()
    for expected in (
        'git -c safe.directory="$OWNER" -C "$OWNER" archive "$SHA"',
        'sha256sum --status -c .verified-source-checksums.sha256',
        'chown -R root:root "$stage"',
        'chmod 0555', 'chmod 0444',
        "EXPECTED_UNIT=", "EXPECTED_ORIGINAL=", "EXPECTED_RUNNER=",
        'systemctl stop "$TIMER"', 'systemctl start "$TIMER"',
        'systemctl daemon-reload', 'ROLLBACK_DROPIN=',
        'result[\'prediction_ready\'] is False',
        'result[\'independent_source_admitted\'] is False',
        'result[\'economic_rows_independently_verified\'] is False',
    ):
        assert expected in script
    assert "CREATE ROLE" not in script
    assert "GRANT SELECT" not in script
    assert "ALTER ROLE" not in script
    assert "curl " not in script
    assert "EMPIREDB_TENANT_OUTCOME_READER_DSN" not in script
    assert script.rfind('systemctl start "$TIMER"') < script.rfind("rollback_needed=0")


def test_cloud_root_code_belongs_under_opt_because_home_is_protected():
    script = INSTALLER.read_text()
    assert 'TARGET="/opt/empire/predictive_cloud_guard_$SHORT"' in script
    assert 'Environment=PYTHONPATH=$TARGET' in script
    assert 'scripts/run_predictive_cloud_materializer.py' in script
    assert '/srv/empire_os/runtime/predictive_cloud/' in script
