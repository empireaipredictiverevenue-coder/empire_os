"""Owner-aware, hash-pinned additive CRM name preview release checks."""
from pathlib import Path
import subprocess

SCRIPT=Path("/srv/empire_os/scripts/deploy_private_crm_solar_tenant_name_preview_20261019.sh")


def test_invalid_operator_modes_and_shell_syntax():
    assert subprocess.run(
        ["bash","-n",str(SCRIPT)],capture_output=True,timeout=5
    ).returncode == 0
    for args in ([], ["--send-emails"],
                 ["--apply-founder-approved-private-crm-name-preview","unexpected"]):
        p=subprocess.run(
            ["bash",str(SCRIPT),*args],capture_output=True,text=True,timeout=5
        )
        assert p.returncode==2


def test_new_route_is_additive_and_no_authority_or_data_mutation():
    script=SCRIPT.read_text()
    required=(
        "founder-queue-20261018v1",
        "founder-queue-solar-name-20261019v1",
        "empire_crm_solar_tenant_name_preview_20261019",
        "50-founder-release-20261018.conf",
        "60-solar-tenant-prospect-name-preview.conf",
        "OTHER_AGENT_CRM_PACKAGE_DRIFT",
        "CRM_DROPINS_DRIFT",
        "UNEXPECTED_SOURCE_DRIFT",
        "PRECHECK_PASS:",
        "systemctl restart \"$UNIT\"",
        "PRIVATE_CRM_SOLAR_NAME_PREVIEW_ROLLBACK_TO_FOUNDER_QUEUE",
        "FOUNDER_CRM_ALL_PRIOR_ROUTE_AND_SIGNATURE_PARITY_VERIFIED",
        "PRIVATE_CRM_SOLAR_TENANT_NAME_PREVIEW_RELEASE_VERIFIED",
        "/v1/revenue-crm/prospects",
        "/v1/revenue-crm/partner-conversations/review",
        "/v1/revenue-crm/commercial-loop/review",
        "verify_private_crm_router_parity_20261019 --compare-staged",
        "verify_private_crm_router_parity_20261019 --compare-deployed",
        "PUBLIC_CRM_DOCUMENTATION_UNEXPECTEDLY_EXPOSED",
        "PUBLIC_CRM_DOCUMENTATION_EXPOSED_AFTER_RELEASE",
        "== 401",
    )
    for key in required:
        assert key in script
    forbidden=(
        "sudo ",
        "psql ",
        "INSERT INTO",
        "UPDATE public.",
        "ALTER TABLE",
        "DELETE FROM",
        "DROP TABLE",
        "git reset",
        "git checkout",
        "git merge",
        "npm install",
        "npm ci",
        "systemctl restart empire-founder-console",
        "systemctl restart empire-buyer-acquisition-team",
        "curl -X POST",
    )
    for key in forbidden:
        assert key not in script
    assert "Environment=PYTHONPATH=%s" in script
    assert "PrivateTmp" not in script  # unit owns its existing sandbox
    assert "empire_os/" in script


def test_every_owned_crm_source_matches_frozen_candidate_checksum():
    script=SCRIPT.read_text()
    stage=Path("/home/ubuntu/empire_worktrees/empire_crm_solar_tenant_name_preview_20261019")
    assert stage.joinpath("empire_os/revenue_crm_api.py").is_file()
    assert stage.joinpath("empire_os/workspace_solar_crm_tenant_prospect_match.py").is_file()
    assert "OLD_SHA=2cf8a796201d2bd914fb8ee206974606857fd6a4393e6b3234fadd2bba651e49" in script
    assert "NEW_SHA=9ca7e8bc10b68208a5ce3e1444ce64260e1d8fc4152c99c18cb83570d1208507" in script
    assert "HELPER_SHA=2449618a5e14ae6a269f53523072ee09029cd91f71b344cde48bf4c05d929b1b" in script
