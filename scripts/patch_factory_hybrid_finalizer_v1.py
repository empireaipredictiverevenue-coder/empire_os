#!/usr/bin/env python3
"""Add opt-in privileged REVIEW->DONE method to native queue; no activation.

Refuses drift, backs up original and atomically updates a single source file.
Other changed lines remain byte-identical.
"""
from __future__ import annotations
import argparse
import ast
import os
from pathlib import Path
import stat
import tempfile

REL = Path('empire_os/department_work_queue.py')
MARK = '# EMPIRE_HYBRID_FACTORY_PHASE4B_FINALIZER'
ANCHOR = '    def complete(\n'
METHOD = '''    # EMPIRE_HYBRID_FACTORY_PHASE4B_FINALIZER: root-attested, explicit only.
    def finalize_hybrid_review(self, work_id: str) -> DepartmentWorkItem:
        from empire_os.factory_hybrid_review_finalizer_v1 import finalize_review_locked
        return finalize_review_locked(self, work_id)

'''


def patch_source(source: str) -> str:
    if MARK in source:
        raise ValueError('phase4b_already_installed')
    if source.count(ANCHOR) != 1:
        raise ValueError('queue_completion_method_contract_drift')
    required = (
        'def submit_for_review(',
        '# EMPIRE_HYBRID_FACTORY_PHASE4_REVIEW',
        'def _finish(',
        'DepartmentWorkStatus.REVIEW: self.review,',
        'self._locked()',
        'current.replace(target / current.name)',
    )
    for token in required:
        if token not in source:
            raise ValueError('missing_queue_contract:' + token)
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DepartmentWorkQueue']
    if len(matches) != 1:
        raise ValueError('queue_class_missing_or_ambiguous')
    names = [n.name for n in matches[0].body if isinstance(n, ast.FunctionDef)]
    if names.count('complete') != 1 or names.count('submit_for_review') != 1:
        raise ValueError('queue_methods_missing_or_ambiguous')
    updated = source.replace(ANCHOR, METHOD + ANCHOR, 1)
    ast.parse(updated)
    compile(updated, str(REL), 'exec')
    if updated.count(MARK) != 1:
        raise ValueError('patch_marker_count_failed')
    return updated


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--repo-root', type=Path, default=Path('/srv/empire_os'))
    options = p.add_mutually_exclusive_group()
    options.add_argument('--check', action='store_true')
    options.add_argument('--apply', action='store_true')
    args = p.parse_args()
    path = args.repo_root.resolve() / REL
    original = path.read_bytes()
    changed = patch_source(original.decode('utf-8'))
    if not args.apply:
        print('PHASE4B_FINALIZER_CONTRACT_PASS')
        print('NO_WRITES; GOVERNOR_DISABLED; ROOT_RECEIPTS_REQUIRED')
        return 0
    backup_dir = Path(tempfile.mkdtemp(prefix='empire_hybrid_phase4b_backup_'))
    backup = backup_dir / 'department_work_queue.py'
    backup.write_bytes(original)
    os.chmod(backup, 0o600)
    mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.hybrid_phase4b_', delete=False) as handle:
        temp = Path(handle.name)
        handle.write(changed.encode('utf-8'))
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp, mode)
        if path.read_bytes() != original:
            raise RuntimeError('concurrent_queue_change_detected')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    print('BACKUP=' + str(backup))
    print('PHASE4B_FINALIZER_INSTALLED; GOVERNOR_DISABLED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
