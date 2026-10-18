"""Safety contract for one-off Founder Mail historical status UI release."""
from pathlib import Path
import subprocess

SCRIPT=Path("/srv/empire_os/scripts/deploy_private_founder_mail_historical_status_20261018.sh")


def test_script_syntax_and_explicit_mode_required():
    assert subprocess.run(
        ["bash","-n",str(SCRIPT)],capture_output=True,timeout=5
    ).returncode==0
    for arguments in ([],["--send"],["--apply-approved-private-release","extra"]):
        r=subprocess.run(
            ["bash",str(SCRIPT),*arguments],
            text=True,capture_output=True,timeout=5,
        )
        assert r.returncode==2


def test_existing_frozen_console_and_rollback_are_preserved():
    source=SCRIPT.read_text()
    for marker in (
        "empire_founder_mail_reply_triage_candidate_20261018",
        "empire_founder_mail_historical_evidence_candidate_20261018",
        "70-private-solar-review-release.conf",
        "80-private-reply-triage-release.conf",
        "90-private-historical-evidence-release.conf",
        "HISTORICAL_EVIDENCE_UI_ROLLBACK_TO_PRIOR_CONSOLE",
        "ROOT_OPERATOR_REQUIRED",
        "PUBLIC_FOUNDER_ROUTE_EXPOSED",
        "/founder/youtube",
        "/founder/intent-review",
        "workspace-solar-historical-evidence-status",
        "OTHER_FOUNDER_FEATURE_DRIFT",
        "HISTORICAL_EVIDENCE_UI_RELEASE_VERIFIED",
        "systemctl restart",
    ):
        assert marker in source
    for prohibited in (
        "psql -c", "pg_dump", "ALTER TABLE", "git reset",
        "git checkout", "npm ci", "git merge", "drop database",
        "empire-revenue-crm-pilot.service restart",
    ):
        assert prohibited not in source


def test_only_explicit_private_ui_systemd_dropin_is_mutable():
    source=SCRIPT.read_text()
    assert 'mv "$tmp" "$DROP"' in source
    assert 'rm -f "$DROP"' in source
    assert 'systemctl daemon-reload' in source
    assert "Read-only" not in source or "crm_writes=no" in source
