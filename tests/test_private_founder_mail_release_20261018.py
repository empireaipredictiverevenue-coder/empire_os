"""Release control for the already-built, loopback-only Founder Mail snapshot.

Tests never invoke the privileged deployment branch.
"""
from pathlib import Path
import subprocess

ROOT = Path("/srv/empire_os")
SCRIPT = ROOT / "scripts/deploy_private_founder_mail_solar_review_20261018.sh"


def test_bash_release_syntax_is_valid():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True, text=True, timeout=5, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_operator_release_flag_is_required():
    for argv in ([], ["--send"], ["--apply-approved-private-release", "extra"]):
        result = subprocess.run(
            ["bash", str(SCRIPT), *argv],
            capture_output=True, text=True, timeout=5, check=False,
        )
        assert result.returncode == 2
        assert "Usage:" in result.stderr


def test_only_private_founder_console_has_a_mutating_release_path():
    source = SCRIPT.read_text()
    assert "70-private-solar-review-release.conf" in source
    assert "empire-founder-console.service" in source
    assert "systemctl daemon-reload" in source
    assert 'systemctl restart "$UNIT"' in source
    assert "RELEASE_SMOKE_FAILED_ROLLING_BACK_PREVIOUS_FOUNDER_CONSOLE" in source
    assert "WORKING_DIRECTORY" not in source
    for string in (
        "/founder/youtube", "/founder/intent-review", "/founder/mail",
        "Commercial outreach tracking", "GB NRG", "100% Renewables",
        "https://empire-ai.co.uk/founder/mail",
        "UNCOMMITTED_FRONTEND_SOURCE_CHANGED_SINCE_BUILD",
        "ROOT_OPERATOR_REQUIRED",
        "--preflight",
        "--apply-approved-private-release",
    ):
        assert string in source
    for prohibited in ("git reset", "git checkout", "git clean", "git merge",
                       "npm ci", "curl -X POST", "gmail.send(", "psql -c",
                       "empire-revenue-crm-pilot.service restart"):
        assert prohibited not in source
