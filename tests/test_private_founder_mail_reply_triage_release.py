"""Strict owner-gated private Founder Mail incremental release contract."""
from pathlib import Path
import subprocess

SCRIPT = Path("/srv/empire_os/scripts/deploy_private_founder_mail_reply_triage_20261018.sh")


def test_script_syntax_and_invalid_modes_never_enter_mutating_branch():
    assert subprocess.run(["bash", "-n", str(SCRIPT)],capture_output=True,
                          timeout=6).returncode == 0
    for args in ([], ["--send"], ["--apply-approved-private-release", "extra"]):
        p=subprocess.run(["bash",str(SCRIPT),*args],capture_output=True,
                         text=True,timeout=6)
        assert p.returncode == 2


def test_exact_previous_private_release_is_preserved_for_rollback():
    text=SCRIPT.read_text()
    assert "70-private-solar-review-release.conf" in text
    assert "80-private-reply-triage-release.conf" in text
    assert "TRIAGE_RELEASE_FAILED_REVERTING_TO_VERIFIED_PRIOR_CONSOLE" in text
    assert 'rm -f "$DROP"' in text
    assert 'systemctl restart "$UNIT"' in text
    assert '[[ "$(id -u)" == 0 ]]' in text
    assert "PUBLIC_EXPOSURE_CONFLICT" in text
    assert "NEW_CONSOLE_ROUTE_REGRESSION" in text
    assert "OTHER_AGENTS_SOURCE_DIFFERS" in text
    assert "CRM" in text or "crm" in text
    assert "empire-buyer-acquisition-team.timer" in text
    for route in ("/founder/youtube","/founder/intent-review","/founder/mail"):
        assert route in text
    for unwanted in ("git checkout","git reset","git merge","git clean",
                     "npm ci","psql", "gmail.send", "POST /v1/revenue-crm"):
        assert unwanted not in text
