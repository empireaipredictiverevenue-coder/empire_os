#!/usr/bin/env python3
"""Fail-closed addition of REVIEW intake to existing EmpireOS queue and worker.

--check (default) validates both exact contracts without writes. --apply
atomically patches each file, preserving unrelated content and backing both up.
No migrations, restarts, job running or feature-flag changes.
"""
from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
import stat
import tempfile

QUEUE_PATH = "empire_os/department_work_queue.py"
WORKER_PATH = "empire_os/department_worker.py"
WORKER_MARK = "# EMPIRE_HYBRID_FACTORY_PHASE3_BEGIN"
PHASE4_MARK = "# EMPIRE_HYBRID_FACTORY_PHASE4_REVIEW"

QUEUE_METHOD = '''    # EMPIRE_HYBRID_FACTORY_PHASE4_REVIEW: only a leased RUNNING item can enter REVIEW.
    def submit_for_review(
        self,
        item: DepartmentWorkItem,
        result: Mapping[str, Any],
    ) -> DepartmentWorkItem:
        from empire_os.factory_hybrid_review_intake_v1 import validate_review_intake
        validate_review_intake(item, result)
        return self._finish(
            item, DepartmentWorkStatus.REVIEW, dict(result), (), None,
            execution_completed=False,
        )

'''

BLOCK_OLD = '''                    held = queue.block(
                        item,
                        'hybrid_factory_' + factory_hold.disposition.lower(),
                        hold_result,
                    )
'''
BLOCK_NEW = '''                    if factory_hold.disposition == 'READY_FOR_INDEPENDENT_REVIEW':
                        held = queue.submit_for_review(item, hold_result)
                    else:
                        held = queue.block(
                            item,
                            'hybrid_factory_' + factory_hold.disposition.lower(),
                            hold_result,
                        )
'''
STATE_OLD = "                        'state': 'BLOCKED',\n"
STATE_NEW = "                        'state': 'REVIEW' if factory_hold.disposition == 'READY_FOR_INDEPENDENT_REVIEW' else 'BLOCKED',\n"


def patch_queue(source: str) -> str:
    if PHASE4_MARK in source:
        raise ValueError("phase4_queue_already_patched")
    if source.count("    def complete(\n") != 1:
        raise ValueError("queue_complete_contract_drift")
    required = (
        "    def _finish(\n", "DepartmentWorkStatus.REVIEW: self.review,",
        "current = self.running /", "if not current.exists():",
        "execution_completed: bool = False",
    )
    if any(x not in source for x in required):
        raise ValueError("queue_finish_contract_drift")
    tree = ast.parse(source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DepartmentWorkQueue"]
    if len(classes) != 1 or not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "complete" for n in classes[0].body):
        raise ValueError("queue_class_contract_drift")
    result = source.replace("    def complete(\n", QUEUE_METHOD + "    def complete(\n", 1)
    ast.parse(result)
    compile(result, QUEUE_PATH, "exec")
    return result


def patch_worker(source: str) -> str:
    if PHASE4_MARK in source:
        raise ValueError("phase4_worker_already_patched")
    if source.count(WORKER_MARK) != 2:
        raise ValueError("worker_phase3_hooks_required")
    starts = source.split(WORKER_MARK)
    if len(starts) != 3:
        raise ValueError("worker_phase3_contract_drift")
    if source.count(BLOCK_OLD) != 2:
        raise ValueError("worker_review_holds_contract_drift")
    end_marker = "# EMPIRE_HYBRID_FACTORY_PHASE3_END"
    if source.count(end_marker) != 2:
        raise ValueError("worker_phase3_end_markers_missing")
    parts = []
    rest = source
    for _ in range(2):
        start = rest.index(WORKER_MARK)
        end = rest.index(end_marker, start) + len(end_marker)
        section = rest[start:end]
        if section.count(BLOCK_OLD) != 1 or section.count(STATE_OLD) != 1:
            raise ValueError("worker_review_block_structure_drift")
        patched = section.replace(BLOCK_OLD, BLOCK_NEW).replace(STATE_OLD, STATE_NEW)
        patched = patched.replace(WORKER_MARK, WORKER_MARK + "\n            " + PHASE4_MARK, 1)
        parts.append(rest[:start] + patched)
        rest = rest[end:]
    result = "".join(parts) + rest
    if result.count(PHASE4_MARK) != 2:
        raise ValueError("worker_phase4_markers_incomplete")
    ast.parse(result)
    compile(result, WORKER_PATH, "exec")
    return result


def _write_atomic(path: Path, expected: bytes, updated: str) -> None:
    if path.read_bytes() != expected:
        raise RuntimeError(f"concurrent_edit_detected:{path.name}")
    mode = stat.S_IMODE(path.stat().st_mode)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".hybrid_phase4_", delete=False) as f:
        temp = Path(f.name)
        f.write(updated)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(temp, mode)
        if path.read_bytes() != expected:
            raise RuntimeError(f"concurrent_edit_detected:{path.name}")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = p.parse_args()
    root = args.repo_root.resolve()
    paths = (root / QUEUE_PATH, root / WORKER_PATH)
    old = [path.read_bytes() for path in paths]
    updated = [patch_queue(old[0].decode("utf-8")), patch_worker(old[1].decode("utf-8"))]
    if not args.apply:
        print("PHASE4_QUEUE_AND_WORKER_CONTRACT_PASS")
        print("REVIEW_INTAKE_ONLY; no DONE transition; FEATURE_FLAG_UNCHANGED")
        return 0
    backup_root = Path(tempfile.mkdtemp(prefix="empire_hybrid_phase4_backup_"))
    for path, blob in zip(paths, old):
        dest = backup_root / path.name
        dest.write_bytes(blob)
        os.chmod(dest, 0o600)
    print("BACKUP=" + str(backup_root), flush=True)
    # Both preflight checks were performed before either file is changed. If a
    # subsequent replace fails, do not overwrite an unknown concurrent editor;
    # the flag remains off and previous backup is available for reconciliation.
    for path, blob, next_source in zip(paths, old, updated):
        _write_atomic(path, blob, next_source)
        print("PHASE4_PATCHED=" + str(path.relative_to(root)), flush=True)
    print("PHASE4_REVIEW_INTAKE_PATCH_PASS; FEATURE_FLAG_UNCHANGED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
