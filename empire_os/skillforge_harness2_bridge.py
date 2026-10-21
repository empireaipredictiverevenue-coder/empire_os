"""Read a pinned Harness² result as an unapproved SkillForge review candidate.

The original replay was a completed deterministic replay of archived model
outputs, not two independent successful agent runs. Its result is a review
lead—not a reusable agent skill or new source of execution authority.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

MANIFEST = Path("config/harness2_evidence_guard_candidate_20261021.json")
GUARD_SOURCE = Path("empire_os/astra_harness_evidence_guard.py")
REPLAY = Path("config/harness2_evidence_guard_replay_receipt_20261021.json")
FRESH_TRIAL = Path("config/harness2_original_source_shadow_receipt_20261021.json")
HEX = set("0123456789abcdef")
MAX_SIZE=32_000


def _read(root:Path,path:Path) -> tuple[dict,bytes]:
    original=root/path
    if (original.is_symlink() or not original.is_file() or
        not 0 < original.stat().st_size <= MAX_SIZE):
        raise ValueError("missing or unsafe review evidence")
    raw=original.read_bytes()
    value=json.loads(raw)
    if not isinstance(value,dict):
        raise ValueError("untrusted review evidence object")
    return value,raw


def skillforge_harness2_candidate(root:Path) -> dict:
    """Only exact local manifest and source artifacts are admissible."""
    result={
        "schema_version":"empire.skillforge.harness2_candidate_review.v1",
        "candidate_id":"empire-harness2-evidence-guard-v1",
        "status":"UNAVAILABLE",
        "approved":False,
        "skill_available_to_agents":False,
        "automatic_skill_promotion":False,
        "execution_authority":"none",
        "independent_real_agent_completions":0,
        "independent_holdout_verified":False,
        "source_replay_present_and_consistent":False,
        "release_allowed":False,
    }
    root=Path(root).resolve()
    if not (root/MANIFEST).exists() and not (root/MANIFEST).is_symlink():
        return {**result,"status":"CANDIDATE_NOT_INSTALLED_ON_THIS_WORKSPACE"}
    try:
        manifest,_=_read(root,MANIFEST)
        required={
            "schema_version":"empire.skillforge.harness2_candidate.v1",
            "candidate_id":result["candidate_id"],"status":"REVIEW_REQUIRED",
            "procedure_code_path":str(GUARD_SOURCE),
            "source_replay_path":str(REPLAY),
            "fresh_trial_path":str(FRESH_TRIAL),
            "source_review_schema":"empire.astra.harness2_guard_comparison.v1",
            "original_evidence_tasks":2,"baseline_grounding_pass_count":0,
            "guarded_grounding_pass_count":2,"independent_real_agent_completions":0,
            "independent_holdout_verified":False,"approved":False,
            "skill_available_to_agents":False,"execution_authority":"none",
            "model_generated_patch_executed":False,
            "model_driven_recursion_success_independently_verified":False,
        }
        if any(manifest.get(k)!=v for k,v in required.items()):
            raise ValueError("untrusted Harness2 review manifest")
        for digest_name in ("procedure_code_sha256","source_replay_sha256","fresh_trial_sha256"):
            digest=manifest.get(digest_name)
            if not isinstance(digest,str) or len(digest)!=64 or set(digest)-HEX:
                raise ValueError("invalid evidence fingerprint")
        code=root/GUARD_SOURCE
        if code.is_symlink() or not code.is_file() or code.stat().st_size>MAX_SIZE:
            raise ValueError("missing original guarded implementation")
        if sha256(code.read_bytes()).hexdigest()!=manifest["procedure_code_sha256"]:
            raise ValueError("guarded implementation changed since review")
        try:
            receipt,raw=_read(root,REPLAY)
        except (OSError,ValueError,TypeError,UnicodeError):
            return {**result,"status":"PINNED_REPLAY_NOT_AVAILABLE_ON_THIS_WORKSPACE",
                    "review_manifest_pinned":True,
                    "source_replay_present_and_consistent":False}
        if sha256(raw).hexdigest()!=manifest["source_replay_sha256"]:
            raise ValueError("Harness2 replay artifact changed")
        measured=receipt.get("measured")
        if (receipt.get("schema_version")!="empire.astra.harness2_real_source_replay.v1"
            or receipt.get("upstream_recursion_executed") is not True
            or receipt.get("recorded_model_outputs_replayed") is not True
            or receipt.get("fresh_model_calls")!=0
            or receipt.get("harness_done")!=2 or receipt.get("harness_failed")!=0
            or receipt.get("production_promotion_authorized") is not False
            or not isinstance(measured,dict)
            or measured.get("schema_version")!=required["source_review_schema"]
            or measured.get("basis")!="ORIGINAL_REDACTED_RUNTIME_SNAPSHOTS"
            or measured.get("baseline_passed")!=0 or measured.get("guarded_passed")!=2
            or measured.get("task_count")!=2
            or measured.get("production_activation_authorized") is not False
            or measured.get("realized_revenue_improvement_proven") is not False):
            raise ValueError("inconsistent upstream Harness2 replay receipt")
        # Fresh local-model responses are a separate test from Google's
        # archived upstream replay. They never qualify as independently
        # completed Department work or authorize skill loading.
        shadow_state='FRESH_MODEL_SHADOW_EVIDENCE_MISSING'
        fresh_calls=0
        try:
            shadow,shadow_bytes=_read(root,FRESH_TRIAL)
        except (OSError,ValueError,TypeError,UnicodeError):
            shadow=None
        if shadow is not None:
            if sha256(shadow_bytes).hexdigest()!=manifest["fresh_trial_sha256"]:
                raise ValueError("fresh shadow trial receipt changed")
            rows=shadow.get("tasks")
            if (shadow.get("schema_version")!="empire.harness2.original_source_shadow_review_receipt.v1"
                or shadow.get("model_calls_attempted")!=3
                or shadow.get("model_calls_succeeded")!=3
                or shadow.get("baseline_passed")!=0
                or shadow.get("guarded_passed")!=3
                or not isinstance(rows,list) or len(rows)!=3
                or {r.get("task_kind") for r in rows if isinstance(r,dict)}!={"conversion","acquisition","revenue"}
                or any(not isinstance(r,dict) or r.get("model_call_status")!="EVALUATED"
                       or r.get("baseline_pass") is not False
                       or r.get("guarded_pass") is not True
                       or r.get("distinct_department_completion_proven") is not False
                       or r.get("commercial_outcome_verified") is not False
                       for r in rows)
                or shadow.get("independently_verified_agent_completions")!=0
                or shadow.get("independent_holdout_verified") is not False
                or shadow.get("commercial_performance_improvement_verified") is not False
                or shadow.get("production_promotion_authorized") is not False
                or shadow.get("execution_authority")!="none"):
                raise ValueError("unsafe fresh shadow trial receipt")
            shadow_state='FRESH_LOCAL_MODEL_SHADOW_TRIAL_RECORDED_NOT_INDEPENDENT_COMPLETION'
            fresh_calls=3
        return {**result,"status":"REVIEW_REQUIRED_REPLAY_EVIDENCE_VERIFIED",
                "fresh_shadow_trial_status":shadow_state,
                "fresh_shadow_model_call_count":fresh_calls,
                "review_manifest_pinned":True,
                "source_replay_present_and_consistent":True,
                "original_evidence_tasks":2,
                "baseline_grounding_pass_count":0,
                "guarded_grounding_pass_count":2,
                "review_requirements":[
                    "verify_two_independent_agent_completions_not_a_replay",
                    "run_original_source_blinded_holdouts_and_negative_cases",
                    "confirm_no_tenant_identity_or_customer_proof_inferred",
                    "pin_digest_and_obtain_separate_explicit_skill_approval",
                ]}
    except (OSError,ValueError,TypeError,UnicodeError):
        return {**result,"status":"INVALID_OR_TAMPERED_HARNESS2_REVIEW_EVIDENCE"}
