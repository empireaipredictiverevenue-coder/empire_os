"""Phase 4 public review API and Phase 3 hook extension, no production calls."""
from __future__ import annotations
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import os
import pytest

PHASE4 = Path(__file__).resolve().parents[1] / 'scripts' / 'patch_factory_hybrid_review_v1.py'
sp = importlib.util.spec_from_file_location('p4p', PHASE4)
p4 = importlib.util.module_from_spec(sp)
sp.loader.exec_module(p4)

PHASE3 = Path(__file__).resolve().parents[1] / 'scripts' / 'patch_factory_hybrid_worker_v1.py'
if not PHASE3.is_file():
    PHASE3 = Path(__file__).resolve().parents[2] / 'empireos_hybrid_phase3' / 'scripts' / 'patch_factory_hybrid_worker_v1.py'
sp3 = importlib.util.spec_from_file_location('p3p', PHASE3)
p3 = importlib.util.module_from_spec(sp3)
sp3.loader.exec_module(p3)

WORKER_BASE = '''from empire_os.department_work_queue import DepartmentWorkQueue
import os

def run_one_department_work(root, item, queue):
    if item.target_component == "agent_tool_execution_plane":
        try:
            result = _execution_plane_bridge(root, item)
            done = queue.complete(item, result)
            return {"state": "DONE", "result": done}
        except Exception:
            raise
    if item.target_component == "empire_coder":
        try:
            result = _coder_bridge(root, item)
            done = queue.complete(item, result)
            return {"state": "DONE", "result": done}
        except Exception:
            raise
    done = queue.complete(item, {"status": "AVAILABLE"})
    return {"state": "DONE", "result": done}
'''
QUEUE_BASE = '''from enum import Enum
from typing import Any, Mapping
class DepartmentWorkStatus(Enum):
    REVIEW='REVIEW'
    DONE='DONE'
class DepartmentWorkItem:
    pass
class DepartmentWorkQueue:
    def _finish(
        self, *args, execution_completed: bool = False,
    ):
        current = self.running / 'name.json'
        if not current.exists():
            raise ValueError('not running')
        target = {DepartmentWorkStatus.REVIEW: self.review,}[args[1]]
        return args[1]
    def complete(
        self, item, result=None, *, evidence_refs=(), execution_completed=False,
    ):
        return self._finish(item, DepartmentWorkStatus.DONE, dict(result or {}), tuple(evidence_refs), None)
'''


def test_queue_method_added_only_once():
    changed=p4.patch_queue(QUEUE_BASE)
    assert changed.count('def submit_for_review(')==1
    assert changed.count('def complete(')==1
    ast.parse(changed)
    with pytest.raises(ValueError): p4.patch_queue(changed)


def test_queue_refuses_unsupported_contract():
    with pytest.raises(ValueError): p4.patch_queue(QUEUE_BASE.replace('current = self.running /', 'current = self.ready /'))


def test_worker_uses_review_without_dropping_other_paths():
    stage3=p3.patch_source(WORKER_BASE)
    changed=p4.patch_worker(stage3)
    assert changed.count('queue.submit_for_review(')==2
    assert changed.count('queue.complete(')==WORKER_BASE.count('queue.complete(')
    assert changed.count('execution_completed=True')==0
    ast.parse(changed)
    with pytest.raises(ValueError): p4.patch_worker(changed)


def test_worker_requires_phase3():
    with pytest.raises(ValueError): p4.patch_worker(WORKER_BASE)


class FakeQueue:
    def __init__(self):
        self.completed=0; self.blocked=0; self.reviewed=0
    def complete(self,item,result,**kwargs):
        self.completed+=1
        return SimpleNamespace(id=item.id, result=result)
    def block(self,item,reason,result):
        self.blocked+=1
        return SimpleNamespace(id=item.id,target_component=item.target_component,error=reason,result=result)
    def submit_for_review(self,item,result):
        self.reviewed+=1
        return SimpleNamespace(id=item.id,target_component=item.target_component,error=None,result=result)
    def counts(self): return {}


def _runner(monkeypatch, *, component='agent_tool_execution_plane', status='QUEUED', enabled=True):
    from empire_os.factory_hybrid_worker_guard_v1 import guard_department_bridge
    from test_factory_hybrid_review_v1 import fixture
    source=p4.patch_worker(p3.patch_source(WORKER_BASE))
    fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef))
    namespace=dict(os=os, guard_department_bridge=guard_department_bridge)
    bridge=fixture()['work_item']['result']
    bridge['dispatch']['status']=status
    namespace['_execution_plane_bridge']=lambda r,i:bridge
    namespace['_coder_bridge']=lambda r,i:dict(adapter='empire_coder_plan_bridge',coder_task_id='t',coder_job_id='j',
            implementation_performed=False,external_execution_performed=False,execution_authority='none')
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<patched>', 'exec'),namespace)
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_ENFORCE_V1', '1' if enabled else '0')
    item=SimpleNamespace(id='work-42', target_component=component,
         intelligence_request={'execution_plane': {'capability':'backend_code'}})
    queue=FakeQueue()
    return namespace['run_one_department_work']('.',item,queue),queue


def test_verified_candidate_routes_review_not_done(monkeypatch):
    result,q=_runner(monkeypatch,status='CANDIDATE_GATE_PASSED')
    assert result['state']=='REVIEW'
    assert q.reviewed==1 and q.blocked==0 and q.completed==0


def test_queued_candidate_remains_blocked(monkeypatch):
    result,q=_runner(monkeypatch,status='QUEUED')
    assert result['state']=='BLOCKED'
    assert q.reviewed==0 and q.blocked==1 and q.completed==0


def test_plan_bridge_remains_blocked(monkeypatch):
    result,q=_runner(monkeypatch,component='empire_coder')
    assert result['state']=='BLOCKED'
    assert q.reviewed==0 and q.completed==0


def test_nonengineering_unchanged(monkeypatch):
    result,q=_runner(monkeypatch,component='identity_enrichment')
    assert result['state']=='DONE'
    assert q.completed==1 and q.blocked==0 and q.reviewed==0


def test_enforcement_flag_off_preserves_old_worker(monkeypatch):
    result,q=_runner(monkeypatch,status='CANDIDATE_GATE_PASSED',enabled=False)
    assert result['state']=='DONE'
    assert q.completed==1 and q.reviewed==0


def test_patching_preserves_unrelated_worker_edit():
    src=p3.patch_source(WORKER_BASE) + '\n# AN_UNRELATED_CHANGE_TO_KEEP\n'
    changed=p4.patch_worker(src)
    assert changed.endswith('\n# AN_UNRELATED_CHANGE_TO_KEEP\n')


def test_new_queue_method_only_calls_finish_with_review():
    from empire_os.factory_hybrid_review_intake_v1 import ReviewIntakeError
    from test_factory_hybrid_review_v1 import fixture
    new=p4.patch_queue(QUEUE_BASE)
    node=next(n for n in ast.parse(new).body if isinstance(n,ast.ClassDef) and n.name=='DepartmentWorkQueue')
    method=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='submit_for_review')
    code=compile(ast.Module(body=[method],type_ignores=[]),'<queue-review>', 'exec')
    from enum import Enum
    class Status(Enum): REVIEW='REVIEW'; DONE='DONE'
    namespace={'DepartmentWorkStatus':Status,'DepartmentWorkItem':object,
               'Mapping':dict,'Any':object}
    exec(code,namespace)
    class Queue:
        submit_for_review=namespace['submit_for_review']
        def __init__(self):self.calls=[]
        def _finish(self,*args,**kwargs):
            self.calls.append((args,kwargs))
            return args[1]
    queue=Queue()
    item=SimpleNamespace(id='work-42',target_component='agent_tool_execution_plane')
    result=fixture()['work_item']['result']
    assert queue.submit_for_review(item,result) is Status.REVIEW
    args,kw=queue.calls[0]
    assert args[1] is Status.REVIEW and kw['execution_completed'] is False
    result['dispatch']['status']='QUEUED'
    with pytest.raises(ReviewIntakeError):queue.submit_for_review(item,result)
    assert len(queue.calls)==1


def test_queue_and_worker_patcher_apply_preflight_no_side_effects(tmp_path):
    from contextlib import redirect_stdout
    from io import StringIO
    root=tmp_path
    (root/'empire_os').mkdir()
    (root/'empire_os'/'department_work_queue.py').write_text(QUEUE_BASE)
    (root/'empire_os'/'department_worker.py').write_text(p3.patch_source(WORKER_BASE))
    out=StringIO()
    import sys
    old=sys.argv
    try:
        sys.argv=['patch_factory_hybrid_review_v1.py','--repo-root',str(root),'--check']
        with redirect_stdout(out):
            assert p4.main()==0
    finally:
        sys.argv=old
    assert 'PHASE4_QUEUE_AND_WORKER_CONTRACT_PASS' in out.getvalue()
    assert (root/'empire_os'/'department_work_queue.py').read_text()==QUEUE_BASE
    assert (root/'empire_os'/'department_worker.py').read_text()==p3.patch_source(WORKER_BASE)
