"""Owner-preserving read-only API release control (no schema/application writes)."""
from pathlib import Path
import subprocess

SCRIPT=Path("/srv/empire_os/scripts/deploy_private_founder_hist052_read_api_20261018.sh")
BASE=Path("/opt/empire-ai/founder-read-releases/bridge-sources-history-75912015/empire_os")
FROZEN=Path("/home/ubuntu/empire_worktrees/empire_founder_api_hist052_bridge_additive_20261018/empire_os")


def test_exact_operator_modes_and_shell_syntax():
    assert subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,timeout=6).returncode==0
    for args in ([], ["--post"], ["--apply-approved-additive-private-read-api","extra"]):
        result=subprocess.run(["bash",str(SCRIPT),*args],text=True,capture_output=True,timeout=6)
        assert result.returncode==2


def test_source_changes_are_exactly_two_additive_files():
    assert BASE.joinpath("founder_mailbox_api.py").is_file()
    assert FROZEN.joinpath("founder_mailbox_api.py").is_file()
    assert FROZEN.joinpath("workspace_solar_historical_status.py").is_file()
    old=BASE.joinpath("founder_mailbox_api.py").read_text()
    new=FROZEN.joinpath("founder_mailbox_api.py").read_text()
    assert old not in ("",new)
    assert new.count('@router.get("/workspace-solar-historical-evidence-status")')==1
    assert '@router.get("/workspace-solar-canonical-intent-review")' in new
    assert '@router.get("/workspace-solar-reply-review")' in new
    assert '@router.get("/workspace-solar-historical-evidence-status")' not in old


def test_release_is_only_frozen_private_read_api_with_rollback():
    script=SCRIPT.read_text()
    for marker in (
        "90-commercial-pipeline-release.conf",
        "95-private-historical-evidence-read-api.conf",
        "PRIVATE_HISTORICAL_READ_API_ROLLBACK_TO_EXISTING_BRIDGE",
        "ROOT_OPERATOR_REQUIRED",
        "EXPECTED_MISSING_ROUTE_ALREADY_CHANGED",
        "UNEXPECTED_ACTIVE_READ_RELEASE",
        "UNEXPECTED_CONCURRENT_SOURCE_CHANGE",
        "FOUNDER_HISTORICAL_READ_API_ADDITIVE_RELEASE_VERIFIED",
        "PRIVATE_CUSTODY_ONLY_DATABASE_SCHEMA_HELD",
        "PRECHECK_PASS:",
        "/founder/mail",
    ):
        assert marker in script
    for prohibited in (
        "psql -c","ALTER TABLE","CREATE TABLE","UPDATE public.outbound_intents",
        "INSERT INTO public.workspace_historical_sent_receipts",
        "systemctl restart empire-revenue-crm-pilot",
        "rm -rf", "npm ci", "git reset", "git merge",
    ):
        assert prohibited not in script
