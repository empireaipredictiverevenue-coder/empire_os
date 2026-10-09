#!/usr/bin/env python3
"""Bounded source patch for existing department worker; default is --check.

Only inserts guarded control flow at two verified adapter boundaries. It does
not run the worker, alter queues, enable a feature flag, or restart services.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile

REL = Path("empire_os/department_worker.py")
MARK = "# EMPIRE_HYBRID_FACTORY_PHASE3_BEGIN"
IMPORT_OLD = "from empire_os.department_work_queue import DepartmentWorkQueue\n"
IMPORT_NEW = IMPORT_OLD + "from empire_os.factory_hybrid_worker_guard_v1 import guard_department_bridge\n"


def _injection(indent: str, *, component: str) -> str:
    # No unverified agent statement can turn a dispatch into DONE.
    return (
        f"{indent}{MARK}\n"
        f"{indent}if os.environ.get('EMPIRE_HYBRID_FACTORY_ENFORCE_V1') == '1':\n"
        f"{indent}    factory_hold = guard_department_bridge(\n"
        f"{indent}        work_id=item.id,\n"
        f"{indent}        target_component={component!r},\n"
        f"{indent}        intelligence_request=item.intelligence_request,\n"
        f"{indent}        result=result,\n"
        f"{indent}    )\n"
        f"{indent}    if factory_hold.enforced:\n"
        f"{indent}        hold_result = {{**result, 'hybrid_factory': factory_hold.as_dict()}}\n"
        f"{indent}        held = queue.block(\n"
        f"{indent}            item,\n"
        f"{indent}            'hybrid_factory_' + factory_hold.disposition.lower(),\n"
        f"{indent}            hold_result,\n"
        f"{indent}        )\n"
        f"{indent}        return {{\n"
        f"{indent}            'ok': True,\n"
        f"{indent}            'state': 'BLOCKED',\n"
        f"{indent}            'work_id': held.id,\n"
        f"{indent}            'target_component': held.target_component,\n"
        f"{indent}            'blocker': held.error,\n"
        f"{indent}            'hybrid_factory': factory_hold.as_dict(),\n"
        f"{indent}            'queue_counts': queue.counts(),\n"
        f"{indent}            'execution_authority': 'none',\n"
        f"{indent}        }}\n"
        f"{indent}# EMPIRE_HYBRID_FACTORY_PHASE3_END\n"
    )


def patch_source(src: str) -> str:
    if MARK in src:
        raise ValueError("hybrid_factory_phase3_already_installed")
    if src.count(IMPORT_OLD) != 1:
        raise ValueError("unexpected_department_queue_import_contract")
    anchors = {
        "agent_tool_execution_plane": "            result = _execution_plane_bridge(root, item)\n",
        "empire_coder": "            result = _coder_bridge(root, item)\n",
    }
    tree = ast.parse(src)
    # Confirm the exact call is *inside* the expected target_component branch,
    # not merely a similar line elsewhere in the source file.
    for component, anchor in anchors.items():
        if src.count(anchor) != 1:
            raise ValueError(f"unexpected_{component}_anchor_count")
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (isinstance(test, ast.Compare) and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Eq)
                    and isinstance(test.left, ast.Attribute)
                    and test.left.attr == "target_component"
                    and len(test.comparators) == 1
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value == component):
                continue
            found = any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == ("_coder_bridge" if component == "empire_coder" else "_execution_plane_bridge")
                for call in ast.walk(node)
            )
            break
        if not found:
            raise ValueError(f"{component}_routing_contract_drift")
    updated = src.replace(IMPORT_OLD, IMPORT_NEW, 1)
    for component, anchor in anchors.items():
        updated = updated.replace(
            anchor,
            anchor + _injection("            ", component=component),
            1,
        )
    ast.parse(updated)
    compile(updated, str(REL), "exec")
    if updated.count(MARK) != 2:
        raise ValueError("patch_integrity_failed")
    return updated


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("/srv/empire_os"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate and show diff without writing (default)")
    mode.add_argument("--apply", action="store_true", help="add opt-in hooks; flag remains disabled")
    args = p.parse_args()
    repo = args.repo_root.resolve()
    worker = repo / REL
    old = worker.read_text(encoding="utf-8")
    new = patch_source(old)
    delta = "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                          fromfile=str(REL), tofile=str(REL) + " (hybrid phase3)"))
    if not args.apply:
        print("PHASE3_CONTRACT_CHECK_PASS")
        print(delta)
        print("NO_FILES_WRITTEN; flag disabled by default")
        return 0
    status = subprocess.run(["git", "status", "--porcelain", "--", str(REL)], cwd=repo,
                            check=True, text=True, capture_output=True, timeout=10)
    if status.stdout.strip():
        raise RuntimeError("refusing_to_modify_existing_dirty_department_worker")
    # Refuse to clobber a concurrent edit after the initial contract read.
    if worker.read_bytes() != old.encode("utf-8"):
        raise RuntimeError("department_worker_changed_during_phase3_preflight")
    # Atomic replacement with backup outside the working tree; no service
    # restart and no feature flag changes. User controls eventual activation.
    backup = Path(tempfile.mkdtemp(prefix="empire_hybrid_phase3_backup_")) / "department_worker.py"
    backup.write_text(old, encoding="utf-8")
    mode = stat.S_IMODE(worker.stat().st_mode)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=worker.parent,
                                     prefix=".department_worker_phase3_", delete=False) as f:
        tmp = Path(f.name)
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(tmp, mode)
        if worker.read_bytes() != old.encode("utf-8"):
            raise RuntimeError("department_worker_changed_before_phase3_replace")
        os.replace(tmp, worker)
    finally:
        if tmp.exists():
            tmp.unlink()
    print("PHASE3_HOOKS_INSTALLED_FEATURE_FLAG_OFF")
    print("BACKUP=" + str(backup))
    print("FEATURE_FLAG=EMPIRE_HYBRID_FACTORY_ENFORCE_V1 (default off)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
