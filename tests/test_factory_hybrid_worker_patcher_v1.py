"""Source-integrity and feature flag regression for bounded worker patcher."""
from __future__ import annotations

import ast
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "patch_factory_hybrid_worker_v1.py"
_spec = importlib.util.spec_from_file_location("phase3_patcher", SCRIPT)
patcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(patcher)

SOURCE = '''from empire_os.department_work_queue import DepartmentWorkQueue
import os

def run_one_department_work(root, item, queue):
    if item.target_component == "agent_tool_execution_plane":
        try:
            result = _execution_plane_bridge(root, item)
            done = queue.complete(item, result, evidence_refs=("x",))
            return {"state": "DONE", "result": done}
        except Exception:
            raise
    if item.target_component == "empire_coder":
        try:
            result = _coder_bridge(root, item)
            done = queue.complete(item, result, evidence_refs=("x",))
            return {"state": "DONE", "result": done}
        except Exception:
            raise
    done = queue.complete(item, {"status": "AVAILABLE"})
    return {"state": "DONE", "result": done}
'''


def test_patch_is_two_hooks_only_and_parses():
    changed = patcher.patch_source(SOURCE)
    ast.parse(changed)
    assert changed.count(patcher.MARK) == 2
    assert changed.count("guard_department_bridge(") == 2
    assert changed.count("queue.complete(") == SOURCE.count("queue.complete(")
    assert '"AVAILABLE"' in changed


def test_prevents_double_patch():
    with pytest.raises(ValueError, match="already_installed"):
        patcher.patch_source(patcher.patch_source(SOURCE))


def test_rejects_routing_drift():
    with pytest.raises(ValueError):
        patcher.patch_source(SOURCE.replace('result = _execution_plane_bridge(root, item)', 'result = other_bridge(root, item)'))


def test_rejects_import_contract_drift():
    with pytest.raises(ValueError):
        patcher.patch_source(SOURCE.replace('from empire_os.department_work_queue import DepartmentWorkQueue', 'from another import Queue'))


class DummyQueue:
    def __init__(self):
        self.complete_calls = 0
        self.block_calls = 0
    def complete(self, item, result, **kwargs):
        self.complete_calls += 1
        return SimpleNamespace(id=item.id, result=result)
    def block(self, item, reason, result):
        self.block_calls += 1
        return SimpleNamespace(id=item.id, target_component=item.target_component, error=reason, result=result)
    def counts(self):
        return {}


def _run(monkeypatch, component, enabled):
    # Execute only AST function: no production imports, filesystem, or network.
    changed = patcher.patch_source(SOURCE)
    tree = ast.parse(changed)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    compiled = compile(ast.Module(body=[fn], type_ignores=[]), '<synthetic-worker>', 'exec')
    from empire_os.factory_hybrid_worker_guard_v1 import guard_department_bridge
    plan = dict(adapter='empire_coder_plan_bridge', coder_task_id='task', coder_job_id='job',
                implementation_performed=False, external_execution_performed=False, execution_authority='none')
    dispatch = dict(adapter='agent_tool_execution_plane', implementation_performed=False,
                    external_execution_performed=False, execution_authority='none',
                    dispatch=dict(request_id='work-1', worker='pi', status='QUEUED',
                                  production_deploy=False, external_send=False, payment_action=False,
                                  revenue_recognition=False, execution_authority='none'))
    namespace = dict(os=os, guard_department_bridge=guard_department_bridge,
                     _coder_bridge=lambda root, item: plan,
                     _execution_plane_bridge=lambda root, item: dispatch)
    exec(compiled, namespace)
    monkeypatch.setenv('EMPIRE_HYBRID_FACTORY_ENFORCE_V1', '1' if enabled else '0')
    item = SimpleNamespace(id='work-1', target_component=component,
                           intelligence_request={'execution_plane': {'capability':'backend_code'}})
    queue = DummyQueue()
    returned = namespace['run_one_department_work']('.', item, queue)
    return returned, queue


@pytest.mark.parametrize('component', ['agent_tool_execution_plane', 'empire_coder'])
def test_enforcement_holds_builder_not_done(monkeypatch, component):
    response, queue = _run(monkeypatch, component, True)
    assert response['state'] == 'BLOCKED'
    assert queue.complete_calls == 0 and queue.block_calls == 1
    assert response['hybrid_factory']['department_work_done'] is False


@pytest.mark.parametrize('component', ['agent_tool_execution_plane', 'empire_coder'])
def test_feature_flag_off_preserves_existing_behaviour(monkeypatch, component):
    response, queue = _run(monkeypatch, component, False)
    assert response['state'] == 'DONE'
    assert queue.complete_calls == 1 and queue.block_calls == 0


def test_unrelated_department_remains_complete_even_with_flag_on(monkeypatch):
    response, queue = _run(monkeypatch, 'identity_enrichment', True)
    assert response['state'] == 'DONE'
    assert queue.complete_calls == 1 and queue.block_calls == 0
