"""Non-privileged contract tests: guarded production source owner release."""
from pathlib import Path
import subprocess

INSTALLER = Path(__file__).resolve().parents[1] / "scripts/install_guarded_predictive_refresh_20261021.sh"


def test_service_installer_has_no_implicit_apply():
    r = subprocess.run(["bash", str(INSTALLER)], text=True, capture_output=True, timeout=12)
    assert r.returncode != 0
    assert "PINNED_GUARDED_REFRESH_DEPLOYED" not in r.stdout


def test_commit_must_be_full_exact_sha_and_pinned_not_branch():
    for commit in ("main", "feature/predictive", "not-a-commit", "f" * 40):
        r = subprocess.run(
            ["bash", str(INSTALLER), "--check", commit],
            text=True, capture_output=True, timeout=12,
        )
        assert r.returncode != 0
        assert "PRODUCTION_UNCHANGED=true" not in r.stdout


def test_installer_rolls_back_guarded_only_and_never_promotes_customers():
    source = INSTALLER.read_text()
    for required in (
        "flock -n", "EXPECTED_ORIGINAL", "EXPECTED_UNIT",
        "EXPECTED_DROPIN", "sha256sum --status -c",
        "SOURCE_COMMIT=$SOURCE_SHA", "systemctl daemon-reload",
        "Environment=PYTHONPATH=$TARGET", "ExecStart=",
        "systemctl start empire-predictive-intelligence.service",
        "systemctl start empire-predictive-intelligence.timer",
        "GLOBAL_UNSCOPED_OUTCOMES_QUARANTINED",
        "GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED",
        "ROLLBACK_SERVICE_DROPIN", "rollback_needed",
    ):
        assert required in source
    assert "GRANT " not in source
    assert "CREATE ROLE" not in source
    assert "EMPIREDB_TENANT_OUTCOME_READER_DSN" not in source
    assert "--apply-owner-approved-observe" in source
    # Do not clear rollback until the timer itself is active again.
    assert (source.rfind("systemctl start empire-predictive-intelligence.timer")
            < source.rfind("rollback_needed=0"))
    assert "ActiveState --value)\" == 'active'" in source
