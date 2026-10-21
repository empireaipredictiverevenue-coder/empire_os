"""Read and verify a pinned, read-only *current-revision* Coder replay receipt.

A recorded current-development pytest PASS is neither reproduction of the
historical source revision nor permission to approve or dispatch any skill.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
from typing import Any

from empire_os.skillforge_coder_test_replay import FIXED_TESTS

PINNED_REPLAY = Path("config/skillforge_coder_current_revision_replay_20261021.json")
PINNED_DIGEST = "f14efc40997973d05ae96db0e81fa8ce826388174afa3ae9cd4480e149bb8838"


def _base(status:str)->dict[str,Any]:
    return {
        "schema_version":"empire.skillforge.coder_replay_review.v1",
        "status":status,
        "recorded_current_revision_tests_passed":False,
        "recorded_replay_attested_by_independent_owner":False,
        "historical_source_revision_reproduced":False,
        "independently_verified_code_implementations":0,
        "skillforge_promotion_authorized":False,
        "automatic_dispatch_authorized":False,
        "execution_authority":"none",
    }


def read_pinned_coder_replay(root:Path)->dict[str,Any]:
    root=Path(root).resolve()
    file=root/PINNED_REPLAY
    if not file.exists() and not file.is_symlink():
        return _base("REPLAY_NOT_INSTALLED")
    try:
        if (file.is_symlink() or not file.is_file()
            or not 0 < file.stat().st_size <= 16000):
            return _base("REPLAY_TAMPER_OR_UNSAFE_ARTIFACT")
        raw=file.read_bytes()
        if sha256(raw).hexdigest()!=PINNED_DIGEST:
            return _base("REPLAY_TAMPER_OR_UNSAFE_ARTIFACT")
        receipt=json.loads(raw)
        if not isinstance(receipt,dict):
            raise ValueError("replay receipt must be object")
        head=receipt.get("current_worktree_head")
        rows=receipt.get("historical_original_receipts")
        digests=receipt.get("current_test_file_sha256")
        requirements={
            "schema_version":"empire.skillforge.coder_current_revision_test_replay.v1",
            "mode":"ISOLATED_DEVELOPMENT_READONLY_TEST_REPLAY",
            "current_revision_head_unchanged":True,
            "current_revision_test_exit_code":0,
            "current_revision_test_files_unchanged":True,
            "current_revision_test_subprocess_executed":True,
            "current_revision_test_workspace_clean":True,
            "current_revision_tests_passed":True,
            "historical_source_revision_reproduced":False,
            "historical_production_revision_tested":False,
            "historical_production_change_authenticated":False,
            "independent_agent_completion_or_owner_attestation":False,
            "independently_verified_code_implementations":0,
            "independently_verified_business_outcomes":0,
            "skillforge_promotion_authorized":False,
            "production_activation_authorized":False,
            "execution_authority":"none",
            "source_original_root_used_for_read_only_receipts":True,
            "selected_historical_receipt_count":2,
            "fixed_test_files":list(FIXED_TESTS),
        }
        if any(receipt.get(k)!=v for k,v in requirements.items()):
            raise ValueError("nonconforming replay authority/proof fields")
        if not isinstance(head,str) or not re.fullmatch("[0-9a-f]{40}",head):
            raise ValueError("replay source revision invalid")
        if not isinstance(digests,dict) or set(digests)!=set(FIXED_TESTS):
            raise ValueError("fixed test revision digests missing")
        if (not isinstance(rows,list) or len(rows)!=2
            or not all(isinstance(row,dict)
                       and set(row)=={
                        "historical_verify_job_reference_sha256",
                        "historical_verify_receipt_sha256",
                        "source_plan_reference_sha256",
                        "source_work_reference_sha256",
                       }
                       and all(isinstance(v,str)
                               and re.fullmatch("[0-9a-f]{64}",v)
                               for v in row.values())
                       for row in rows)
            or len({x["source_plan_reference_sha256"] for x in rows})!=2):
            raise ValueError("original plan jobs not separately linked")
        # Validate test bytes from the recorded commit, not the working
        # tree (which may have moved ahead since this bounded replay).
        for path in FIXED_TESTS:
            proc=subprocess.run(
                ["git","show",head+":"+path],cwd=root,
                capture_output=True,timeout=12,check=False,
            )
            if (proc.returncode!=0 or
                not re.fullmatch("[0-9a-f]{64}",str(digests[path])) or
                sha256(proc.stdout).hexdigest()!=digests[path]):
                raise ValueError("recorded test bytes do not match source revision")
        return {
            **_base("PINNED_CURRENT_REVISION_TEST_REPLAY_REVIEW_ONLY"),
            "recorded_current_revision_tests_passed":True,
            "recorded_test_files":len(FIXED_TESTS),
            "distinct_historical_coder_plans":2,
            "test_source_revision":head,
            "source_receipt_sha256":PINNED_DIGEST,
        }
    except (OSError,ValueError,TypeError,UnicodeError,subprocess.SubprocessError):
        return _base("REPLAY_TAMPER_OR_UNSAFE_ARTIFACT")
