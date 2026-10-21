"""No untrusted historical Coder commands may be executed for skill promotion."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest

from empire_os.skillforge_coder_test_replay import (
    FIXED_TESTS,original_coder_test_sources,replay_current_tests,
)
from empire_os.skillforge_learning import capture_completed_work


def make_source(root:Path):
    for n in (1,2):
        work_id="dept_work_"+f"{n:024x}"
        task_id="coder_"+f"{n:032x}"
        plan_id="coder_job_"+f"{n:032x}"
        verify_id="coder_job_"+f"{n+500:032x}"
        work=root/"runtime/departments/work/done"/(work_id+".json")
        work.parent.mkdir(parents=True,exist_ok=True)
        work.write_text(json.dumps({
            "id":work_id,"status":"DONE","authority":"observe",
            "error":None,"target_component":"empire_coder",
            "result":{
                "adapter":"empire_coder_plan_bridge",
                "coder_task_id":task_id,"coder_job_id":plan_id,
                "implementation_performed":False,
                "external_execution_performed":False,
                "execution_authority":"none",
            },
            "result_evidence_refs":["coder_task:"+task_id,"coder_job:"+plan_id],
        }))
        task=root/"runtime/coder/tasks"/(task_id+".json")
        plan=root/"runtime/coder/jobs/completed"/(plan_id+".json")
        verify=root/"runtime/coder/jobs/completed"/(verify_id+".json")
        for file in (task,plan,verify):file.parent.mkdir(parents=True,exist_ok=True)
        task.write_text(json.dumps({"id":task_id,"status":"running"}))
        plan.write_text(json.dumps({
            "id":plan_id,"task_id":task_id,"status":"COMPLETED",
            "kind":"PLAN","error":None,
            "payload":{"department_work_id":work_id,"execution_authority":"none"},
            "result":{"production_mutation":False,
                      "external_execution_performed":False,
                      "execution_authority":"none"},
        }))
        tests=list(FIXED_TESTS)
        verify.write_text(json.dumps({
            "id":verify_id,"task_id":task_id,"status":"COMPLETED",
            "kind":"VERIFY","error":None,
            "payload":{"source_plan_job_id":plan_id,
                       "source_plan_task_id":task_id,
                       "department_work_id":work_id,
                       "execution_authority":"none","tests":tests},
            "result":{
                "production_mutation":False,
                "external_execution_performed":False,
                "execution_authority":"none","tests":tests,
                "verification":{
                    "verdict":"PASS",
                    "checks":[
                        {"name":"pytest","returncode":0,"passed":True,"tests":tests},
                        {"name":"git_diff_check","returncode":0,"passed":True},
                    ],
                },
            },
        }))
        assert capture_completed_work(root,work_id)["status"]=="candidate_saved"
    return root


def development(root:Path):
    root.mkdir(parents=True,exist_ok=True)
    (root/".git").write_text("gitdir: /tmp/fake-test-only\n")
    for name in FIXED_TESTS:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text("def test_fixture(): assert True\n")
    return root


def git_stub(root,*args):
    return "" if args[0]=="status" else "0"*40


def good_runner(cmd,**kwargs):
    assert isinstance(cmd,list) and cmd[-3:]==list(FIXED_TESTS)
    assert "-p" in cmd and "no:cacheprovider" in cmd
    assert kwargs["timeout"]<=45
    assert kwargs["env"]["PYTHONDONTWRITEBYTECODE"]=="1"
    return SimpleNamespace(returncode=0)


def test_two_distinct_original_plan_receipts_are_not_implementation_proof(tmp_path):
    source=make_source(tmp_path/"source")
    sources=original_coder_test_sources(source)
    assert len(sources)==2
    assert len({r["source_plan_reference_sha256"] for r in sources})==2
    assert all(len(r["historical_verify_receipt_sha256"])==64 for r in sources)
    assert not any("coder_job_" in str(r) for r in sources)


def test_fixed_current_test_run_does_not_promote_a_skill(tmp_path,monkeypatch):
    import empire_os.skillforge_coder_test_replay as module
    source=make_source(tmp_path/"source")
    worktree=development(tmp_path/"work")
    monkeypatch.setattr(module,"_git",git_stub)
    report=replay_current_tests(worktree,source,execute=good_runner)
    assert report["selected_historical_receipt_count"]==2
    assert report["current_revision_tests_passed"] is True
    assert report["historical_source_revision_reproduced"] is False
    assert report["historical_production_change_authenticated"] is False
    assert report["independent_agent_completion_or_owner_attestation"] is False
    assert report["independently_verified_code_implementations"]==0
    assert report["skillforge_promotion_authorized"] is False
    assert report["production_activation_authorized"] is False
    assert report["execution_authority"]=="none"


def test_pytest_failure_held_without_auto_approval(tmp_path,monkeypatch):
    import empire_os.skillforge_coder_test_replay as module
    monkeypatch.setattr(module,"_git",git_stub)
    result=replay_current_tests(development(tmp_path/"work"),
        make_source(tmp_path/"source"),
        execute=lambda *args,**kw:SimpleNamespace(returncode=1))
    assert result["current_revision_tests_passed"] is False
    assert result["skillforge_promotion_authorized"] is False


def test_changed_worktree_after_run_fails_closed(tmp_path,monkeypatch):
    import empire_os.skillforge_coder_test_replay as module
    source=make_source(tmp_path/"source")
    worktree=development(tmp_path/"work")
    calls=iter(["","0"*40," M tests/test_search_traffic_forecast.py","0"*40])
    monkeypatch.setattr(module,"_git",lambda *_:next(calls))
    report=replay_current_tests(worktree,source,execute=good_runner)
    assert report["current_revision_tests_passed"] is False
    assert report["current_revision_test_workspace_clean"] is False


def test_dirty_worktree_cannot_begin_a_replay(tmp_path,monkeypatch):
    import empire_os.skillforge_coder_test_replay as module
    monkeypatch.setattr(module,"_git",lambda *_:" M conflicting.py")
    with pytest.raises(ValueError,match="clean"):
        replay_current_tests(development(tmp_path/"work"),make_source(tmp_path/"source"),
                            execute=good_runner)


@pytest.mark.parametrize("alter",[
    lambda j:j["result"]["verification"]["checks"][0].update(returncode=1),
    lambda j:j["payload"].update(tests=["tests/test_other.py"]),
    lambda j:j["payload"].update(source_plan_task_id="coder_"+"f"*32),
    lambda j:j["result"]["verification"].update(verdict="FAIL"),
])
def test_untrusted_or_changed_historical_receipt_cannot_qualify(tmp_path,alter):
    source=make_source(tmp_path/"source")
    p=source/"runtime/coder/jobs/completed"/("coder_job_"+f"{502:032x}"+".json")
    job=json.loads(p.read_text());alter(job);p.write_text(json.dumps(job))
    with pytest.raises(ValueError,match="fewer than two"):
        original_coder_test_sources(source)


def test_symlinked_test_path_rejected_before_running(tmp_path,monkeypatch):
    import empire_os.skillforge_coder_test_replay as module
    monkeypatch.setattr(module,"_git",git_stub)
    worktree=development(tmp_path/"work")
    a=worktree/FIXED_TESTS[0]; b=worktree/"test-data"
    a.rename(b);a.symlink_to(b)
    with pytest.raises(ValueError,match="unsafe"):
        replay_current_tests(worktree,make_source(tmp_path/"source"),execute=good_runner)


def test_cannot_run_on_production_source_worktree(tmp_path):
    source=make_source(tmp_path/"source")
    (source/".git").write_text("dummy")
    with pytest.raises(ValueError,match="isolated"):
        replay_current_tests(source,source,execute=good_runner)
