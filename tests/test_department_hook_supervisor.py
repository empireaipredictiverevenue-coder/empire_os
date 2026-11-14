"""Bounded hook supervisor: preserve order, verify checkpoint, never blind-replay."""
import json
import subprocess
import pytest

from empire_os.department_hook_supervisor import (
    HookSupervisorError, validate_inventory, inventory_digest,
    matches_current_service, supervise, STATE_SCHEMA, INVENTORY_SCHEMA,
)


def inventory(commands=None):
    commands=commands or [
        ("/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/first.py",False),
        ("-/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/second.py",True),
        ("/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/third.py",False),
    ]
    return {
        "schema_version":INVENTORY_SCHEMA,
        "hooks":[
            {"order":i,"command":command,"drop_in":"unit/step.conf",
             "failure_ignored_by_systemd":opt}
            for i,(command,opt) in enumerate(commands,1)
        ],
    }


def test_full_contract_and_live_fingerprint_compare():
    jobs=validate_inventory(inventory())
    source="# unit\n"+"\n".join("ExecStartPost="+j["command"] for j in jobs)
    assert matches_current_service(jobs,source)
    assert not matches_current_service(jobs,source+"\nExecStartPost=/bin/true")
    assert len(inventory_digest(jobs))==64
    bad=inventory();bad["hooks"][0]["order"]=2
    with pytest.raises(HookSupervisorError,match="invalid_order"):
        validate_inventory(bad)


def test_no_exec_without_release_governance(tmp_path):
    jobs=validate_inventory(inventory())
    checkpoint=tmp_path/"checkpoint.json"
    r=supervise(jobs,cycle_id="pilot",checkpoint=checkpoint)
    assert r["status"]=="DRY_RUN"
    assert not checkpoint.exists()
    with pytest.raises(HookSupervisorError,match="governed_activation_required"):
        supervise(jobs,cycle_id="pilot",checkpoint=checkpoint,execute=True)


def test_bounded_progress_optional_failure_and_resume(tmp_path):
    jobs=validate_inventory(inventory())
    cp=tmp_path/"checkpoint.json"
    invoked=[]
    def runner(argv,**kw):
        invoked.append(argv[-1])
        return subprocess.CompletedProcess(argv,1 if "second" in argv[-1] else 0)
    r=supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,max_items=2,
                governance_check=lambda:True,runner=runner)
    assert r["status"]=="IN_PROGRESS"
    assert [x["state"] for x in r["jobs"]]==["DONE","OPTIONAL_FAILED","PENDING"]
    r=supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,max_items=2,
                governance_check=lambda:True,runner=runner)
    assert r["status"]=="COMPLETE"
    assert len(invoked)==3
    r=supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,
                governance_check=lambda:True,runner=runner)
    assert len(invoked)==3  # no repeat when cycle resumed


def test_required_failure_stays_held_and_no_next_step(tmp_path):
    jobs=validate_inventory(inventory())
    cp=tmp_path/"checkpoint.json"
    invoked=[]
    def runner(argv,**kw):
        invoked.append(argv[-1])
        return subprocess.CompletedProcess(argv,1)
    state=supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,
                    governance_check=lambda:True,runner=runner)
    assert state["status"]=="HELD_REQUIRED_FAILURE"
    assert [x["state"] for x in state["jobs"]]==["FAILED","PENDING","PENDING"]
    supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,
              governance_check=lambda:True,runner=runner)
    assert len(invoked)==1


def test_crash_running_requires_review_and_drift_rejected(tmp_path):
    jobs=validate_inventory(inventory())
    cp=tmp_path/"checkpoint.json"
    def runner(argv,**kw):
        raise KeyboardInterrupt("simulated_interruption")
    with pytest.raises(KeyboardInterrupt):
        supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,
                  governance_check=lambda:True,runner=runner)
    state=supervise(jobs,cycle_id="pilot",checkpoint=cp,execute=True,
                    governance_check=lambda:True,runner=lambda *_a,**_k:None)
    assert state["status"]=="INTERRUPTED_REQUIRES_REVIEW"
    altered=validate_inventory(inventory([
        ("/srv/empire_os/.venv/bin/python /srv/empire_os/scripts/replaced.py",False)
    ]))
    with pytest.raises(HookSupervisorError,match="unrecognised_or_changed_cycle"):
        supervise(altered,cycle_id="pilot",checkpoint=cp,execute=True,
                  governance_check=lambda:True)
    with pytest.raises(HookSupervisorError,match="unrecognised_or_changed_cycle"):
        supervise(jobs,cycle_id="pilot-2",checkpoint=cp,execute=True,
                  governance_check=lambda:True)


def test_timeout_required_holds(tmp_path):
    jobs=validate_inventory(inventory())
    def runner(*a,**kw):
        raise subprocess.TimeoutExpired(["test"],75)
    state=supervise(jobs,cycle_id="timeout",checkpoint=tmp_path/"c.json",
                    execute=True,governance_check=lambda:True,runner=runner)
    assert state["jobs"][0]["failure_class"]=="TIMEOUT"
    assert state["status"]=="HELD_REQUIRED_FAILURE"
