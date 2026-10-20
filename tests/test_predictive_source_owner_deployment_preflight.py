"""Deployment inventory cannot substitute original customer source proof."""
from pathlib import Path
import json
import pytest

from empire_os.predictive_source_owner_deployment_preflight import (
    review_original_source_deployment, SourceDeploymentHold,
)
import scripts.review_predictive_source_owner_deployment_20261020 as cli

UNIT="\n".join((
    "[Unit]","Description=Predictive Intelligence",
    "[Service]",
    "ExecStart=/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/build_predictive_intelligence.py --repo-root /srv/empire_os",
))+"\n"


def source_fixture(tmp_path, *, same):
    original=tmp_path/"original.py"
    candidate=tmp_path/"candidate.py"
    unit=tmp_path/"empire-predictive-intelligence.service"
    original.write_text("X"*130)
    candidate.write_text("X"*130 if same else "Y"*130)
    unit.write_text(UNIT)
    return original,candidate,unit


def test_matching_code_does_not_authenticate_database_or_runtime(tmp_path):
    paths=source_fixture(tmp_path,same=True)
    report=review_original_source_deployment(
        original=paths[0],candidate=paths[1],service_unit=paths[2])
    assert report["source_bytes_equal"] is True
    assert report["runtime_service_effective_unit_verified"] is False
    assert report["original_tenant_reader_role_verified"] is False
    assert report["commercial_outcomes_rls_force_verified"] is False
    assert report["customer_forecast_eligible"] is False
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"


def test_production_writer_drift_visible_with_no_mutation(tmp_path):
    paths=source_fixture(tmp_path,same=False)
    report=review_original_source_deployment(
        original=paths[0],candidate=paths[1],service_unit=paths[2])
    assert report["status"]=="ORIGINAL_SOURCE_OWNER_DEPLOYMENT_STILL_REQUIRED"
    assert report["source_bytes_equal"] is False
    assert len(report["original_production_code_sha256"])==64
    assert len(report["tested_candidate_code_sha256"])==64
    assert paths[0].read_text()=="X"*130


def test_service_unit_drift_holds(tmp_path):
    a,b,u=source_fixture(tmp_path,same=True)
    u.write_text("[Service]\nExecStart=/bin/false\n")
    with pytest.raises(SourceDeploymentHold):
        review_original_source_deployment(original=a,candidate=b,service_unit=u)


def test_group_writable_original_never_pretends_immutable_deployment(tmp_path):
    a,b,u=source_fixture(tmp_path,same=True)
    a.chmod(0o664)
    report=review_original_source_deployment(original=a,candidate=b,service_unit=u)
    assert report["source_bytes_equal"] is True
    assert report["original_shared_source_group_writable"] is True
    assert report["original_source_code_custody_trusted"] is False
    assert report["status"]=="ORIGINAL_SOURCE_OWNER_DEPLOYMENT_STILL_REQUIRED"


def test_mutable_code_and_symlink_refused(tmp_path):
    a,b,u=source_fixture(tmp_path,same=True)
    a.chmod(0o666)
    with pytest.raises(SourceDeploymentHold):
        review_original_source_deployment(original=a,candidate=b,service_unit=u)
    a.chmod(0o644)
    a.unlink()
    a.symlink_to(b)
    with pytest.raises(SourceDeploymentHold):
        review_original_source_deployment(original=a,candidate=b,service_unit=u)


def test_source_exception_not_leaked_in_cli(monkeypatch,capsys):
    monkeypatch.setattr(cli,"review_original_source_deployment",
                        lambda: (_ for _ in ()).throw(
                            SourceDeploymentHold("hidden hostname")))
    assert cli.main(["--read-only"])==2
    result=capsys.readouterr().out
    assert "hidden hostname" not in result
    assert json.loads(result)["customer_forecast_eligible"] is False
