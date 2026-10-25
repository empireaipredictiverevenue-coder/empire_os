"""Infrastructure core source parity and original Jev OBSERVE audit."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import pytest

from empire_os.predictive_cloud_core_jev_observer import (
    inspect_cloud_core_jev,SCHEMA,SERVICES,
)

NOW=datetime(2026,10,25,22,20,tzinfo=timezone.utc)
GUARD_REL="empire_os/predictive_cloud_materializer.py"
RUNNER_REL="scripts/run_predictive_cloud_materializer.py"


def setup(tmp_path):
    repo=tmp_path/"repo"
    guard=tmp_path/"guard"
    def save(root,rel,data):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(data) if type(data) is dict else data)
        return p
    save(repo,"runtime/predictive_cloud/status_latest.json",{
        "schema_version":"empire.predictive_cloud.status.v2",
        "mode":"OBSERVE","execution_authority":"none",
        "generated_at":NOW.isoformat(),"component_count":28,
        "available_component_count":28,
    })
    save(repo,"runtime/predictive_intelligence/latest.json",{
        "schema_version":"empire.predictive_intelligence.v1",
        "mode":"OBSERVE","execution_authority":"none",
        "generated_at":NOW.isoformat(),"matched_outcome_count":0,
    })
    save(repo,"runtime/jev_client_pain_discovery/aggregate_latest.json",{
        "schema_version":"empire.jev.client_pain_production_observe.v1",
        "mode":"OBSERVE",
        "status":"CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
        "generated_at_utc":NOW.isoformat(),
        "execution_authority":"none",
        "model_calls":0,"database_writes":False,"crm_writes":False,
        "buyer_purchase_intent_verified":False,
    })
    save(repo,GUARD_REL,"protected code")
    save(guard,GUARD_REL,"protected code")
    save(guard,RUNNER_REL,"protected runner")
    return repo,guard,save


def report(repo,guard,**kwargs):
    opts=dict(repo_root=repo,guard_root=guard,
              effective_runner=str(guard/RUNNER_REL),
              services=dict.fromkeys(SERVICES,"active"),now=NOW)
    opts.update(kwargs)
    return inspect_cloud_core_jev(**opts)


def test_core_jev_28_components_and_all_services_do_not_imply_revenue(tmp_path):
    root,guard,_=setup(tmp_path)
    result=report(root,guard)
    assert result["schema_version"]==SCHEMA
    assert result["cloud_components_available"]==28
    assert result["core_services_operational"] is True
    assert result["canonical_materializer_parity"] is True
    assert result["protected_materializer_selected"] is True
    assert result["jev_research_observation_available"] is True
    assert result["jev_revenue_ground_truth_admitted"] is False
    assert result["bank_settled_cash_minor"] is None
    assert result["training_examples_eligible"]==0
    assert result["model_weights_updated"] is False
    assert result["external_jev_calls"]==0
    assert result["service_restarts"]==0
    assert result["execution_authority"]=="none"


def test_materializer_parity_drift_flagged_without_replacing_protected_runner(tmp_path):
    root,guard,_=setup(tmp_path)
    (root/GUARD_REL).write_text("vulnerable old core")
    result=report(root,guard)
    assert result["canonical_materializer_parity"] is False
    assert "CANONICAL_MATERIALIZER_NOT_IN_PARITY_WITH_GUARD" in result["blockers"]
    assert result["protected_materializer_selected"] is True


def test_wrong_effective_unit_command_denied(tmp_path):
    root,guard,_=setup(tmp_path)
    out=report(root,guard,effective_runner="/srv/empire_os/scripts/run_predictive_cloud_materializer.py")
    assert out["protected_materializer_selected"] is False
    assert "PROTECTED_MATERIALIZER_NOT_SELECTED" in out["blockers"]


@pytest.mark.parametrize("fields",[
    {"model_calls":1},
    {"model_calls":False},
    {"database_writes":True},
    {"crm_writes":True},
    {"execution_authority":"execute"},
    {"buyer_purchase_intent_verified":True,"model_calls":1},
    {"status":"JEV_PAID_ACTION"},
    {"generated_at_utc":(NOW-timedelta(days=4)).isoformat()},
    {"generated_at_utc":(NOW+timedelta(seconds=10)).isoformat()},
])
def test_forged_paid_stale_or_future_jev_receipt_cannot_admit_evidence(tmp_path,fields):
    repo,guard,_=setup(tmp_path)
    path=repo/"runtime/jev_client_pain_discovery/aggregate_latest.json"
    obj=json.loads(path.read_text())
    obj.update(fields)
    path.write_text(json.dumps(obj))
    out=report(repo,guard)
    assert out["jev_research_observation_available"] is False
    assert out["jev_revenue_ground_truth_admitted"] is False
    assert out["training_examples_eligible"]==0


@pytest.mark.parametrize("outcome",[-1,"7",True,1e40])
def test_malformed_local_outcome_cannot_promote_prediction(tmp_path,outcome):
    root,guard,_=setup(tmp_path)
    path=root/"runtime/predictive_intelligence/latest.json"
    payload=json.loads(path.read_text());payload["matched_outcome_count"]=outcome
    path.write_text(json.dumps(payload))
    out=report(root,guard)
    assert out["predictive_intelligence_observed"] is False
    assert out["training_examples_eligible"]==0


def test_missing_source_snapshot_and_bad_symlink_fail_closed(tmp_path):
    repo,guard,_=setup(tmp_path)
    file=repo/"runtime/jev_client_pain_discovery/aggregate_latest.json"
    file.unlink()
    file.symlink_to("/etc/passwd")
    out=report(repo,guard)
    assert out["jev_research_observation_available"] is False
    assert out["input_snapshot_digests"]["jev"] is None
    assert out["execution_authority"]=="none"


def test_inactive_inference_not_silently_available(tmp_path):
    root,guard,_=setup(tmp_path)
    services=dict.fromkeys(SERVICES,"active")
    services["empire-laya-shadow"]="inactive"
    out=report(root,guard,services=services)
    assert out["core_services_operational"] is False
    assert "CORE_SERVICE_INACTIVE" in out["blockers"]


def test_cli_review_requires_explicit_read_only(tmp_path,capsys):
    from scripts.review_predictive_cloud_core_jev_20261025 import main
    assert main([])==2
    assert "EXPLICIT_READ_ONLY_REQUIRED" in capsys.readouterr().out


def test_unsupported_service_inventory_fails_closed(tmp_path):
    repo,guard,_=setup(tmp_path)
    with pytest.raises(ValueError,match="EXACT_CORE_SERVICE"):
        report(repo,guard,services={"random":"active"})


def test_no_mutating_commands_present():
    root=Path(__file__).resolve().parents[1]
    code=(root/"empire_os/predictive_cloud_core_jev_observer.py").read_text()
    script=(root/"scripts/review_predictive_cloud_core_jev_20261025.py").read_text()
    for forbidden in ("psycopg.connect(","INSERT INTO ","systemctl restart",
                      "systemctl start","model.fit(","send_email(","redis.Redis("):
        assert forbidden not in code+script
