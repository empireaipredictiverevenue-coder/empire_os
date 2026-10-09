from __future__ import annotations
import ast
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[1]/'scripts/patch_factory_hybrid_finalizer_v1.py'
spec=spec_from_file_location('p4bpatch',path)
mod=module_from_spec(spec)
spec.loader.exec_module(mod)

QUEUE='''from typing import Any, Mapping
class DepartmentWorkItem: pass
class DepartmentWorkQueue:
    # EMPIRE_HYBRID_FACTORY_PHASE4_REVIEW
    def submit_for_review(self,item,result): return self._finish(item,DepartmentWorkStatus.REVIEW,dict(result),(),None)
    def complete(
        self,item,result=None
    ): return self._finish(item,DepartmentWorkStatus.DONE,result,(),None)
    def _finish(self,*args):
        with self._locked():
            target = {DepartmentWorkStatus.REVIEW: self.review,}[args[1]]
            current = self.running / 'file.json'
            current.replace(target / current.name)
'''


def test_preserves_all_existing_source():
    patched=mod.patch_source(QUEUE+'\n# UNRELATED DIRTY CHANGE\n')
    assert patched.endswith('# UNRELATED DIRTY CHANGE\n')
    assert patched.count('def finalize_hybrid_review(')==1
    assert patched.count('def complete(')==1
    assert 'finalize_review_locked(self, work_id)' in patched
    ast.parse(patched)


def test_refuses_double_patch():
    with pytest.raises(ValueError,match='already_installed'):
        mod.patch_source(mod.patch_source(QUEUE))

@pytest.mark.parametrize('old,new',[
    ('    def complete(\n','    def complete_something_else(\n'),
    ('def submit_for_review(', 'def not_review('),
    ('self._locked()', 'no_lock()'),
    ('current.replace(target / current.name)', 'current.unlink()'),
])
def test_refuses_contract_drift(old,new):
    with pytest.raises(ValueError): mod.patch_source(QUEUE.replace(old,new))
