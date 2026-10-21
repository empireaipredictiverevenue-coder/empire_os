"""Read-only independent-evidence review of existing canonical SkillForge observations.

Counts repeated original *work records* separately from distinct evidence-reference
strings.  A hash of a reference string proves neither custody of the referenced
artifact nor an independently successful agent outcome.  Never auto-promote.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import re
from typing import Any

from empire_os.skillforge_learning import (
    MAX_RECORD, WORK_ID, _verified_learning_observations,
)

MAX_OBSERVATIONS = 5000
MAX_OBSERVATION_BYTES = 64_000
MAX_CODER_JOB_RECEIPTS = 15000
CODER_TASK_ID = re.compile(r"^coder_[0-9a-f]{32}$")
CODER_JOB_ID = re.compile(r"^coder_job_[0-9a-f]{32}$")


def _sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _read_safe(path: Path, limit: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("missing or unsafe original evidence packet")
    item=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item,dict):
        raise ValueError("evidence packet must be an object")
    return item



def _coder_failed_reason(error: str) -> str:
    """Bounded non-sensitive classification: never emit freeform error text."""
    if error.startswith("HermesControlError: OmniRoute has no healthy eligible zero-cost Hermes mode"):
        return "NO_HEALTHY_ELIGIBLE_MODEL_ROUTE"
    if error.startswith("RuntimeError:model_provider_not_configured"):
        return "MODEL_PROVIDER_NOT_CONFIGURED"
    if error.startswith("PolicyError:path escapes workspace"):
        return "WORKSPACE_PATH_POLICY_REJECTION"
    return "OTHER_FAILED_CODER_PLAN_JOB"


def _correlate_original_coder_plan(root: Path, work: dict[str, Any],
                                   refs: list[str]) -> tuple[str, str | None]:
    """Identify local PLAN job receipts, including failures, not code outcomes."""
    result=work["result"]
    task_id=result.get("coder_task_id")
    job_id=result.get("coder_job_id")
    unresolved=("UNRESOLVED_CODER_PLAN_JOB", None)
    if (not isinstance(task_id,str) or not CODER_TASK_ID.fullmatch(task_id)
            or not isinstance(job_id,str) or not CODER_JOB_ID.fullmatch(job_id)
            or set(refs)!={f"coder_task:{task_id}",f"coder_job:{job_id}"}
            or len(refs)!=2
            or result.get("implementation_performed") is not False
            or result.get("external_execution_performed") is not False
            or result.get("execution_authority")!="none"):
        return unresolved
    task_path=root/"runtime/coder/tasks"/(task_id+".json")
    completed_path=root/"runtime/coder/jobs/completed"/(job_id+".json")
    failed_path=root/"runtime/coder/jobs/failed"/(job_id+".json")
    # Duplicated receipts in both terminal directories cannot be trusted.
    if completed_path.exists() and failed_path.exists():
        return unresolved
    is_completed=completed_path.is_file() and not completed_path.is_symlink()
    is_failed=failed_path.is_file() and not failed_path.is_symlink()
    if not (is_completed or is_failed):
        return unresolved
    try:
        task=_read_safe(task_path,MAX_RECORD)
        job=_read_safe(completed_path if is_completed else failed_path,MAX_RECORD)
    except (OSError,ValueError,UnicodeError,TypeError):
        return unresolved
    payload=job.get("payload")
    job_result=job.get("result")
    if not (
        task.get("id")==task_id and
        job.get("id")==job_id and
        job.get("task_id")==task_id and
        job.get("kind")=="PLAN" and
        isinstance(payload,dict) and
        payload.get("department_work_id")==work.get("id") and
        payload.get("execution_authority")=="none" and
        isinstance(job_result,dict)
    ):
        return unresolved
    if is_completed:
        if (job.get("status")=="COMPLETED"
            and job.get("error") is None
            and job_result.get("execution_authority")=="none"
            and job_result.get("external_execution_performed") is False
            and job_result.get("production_mutation") is False):
            return ("COMPLETED_CODER_PLAN_JOB",None)
        return unresolved
    error=job.get("error")
    if (is_failed and job.get("status")=="FAILED"
        and isinstance(error,str) and 0<len(error)<=10_000
        and job_result.get("execution_authority") in (None,"none")
        and job_result.get("external_execution_performed") is not True
        and job_result.get("production_mutation") is not True):
        return ("FAILED_CODER_PLAN_JOB",_coder_failed_reason(error))
    return unresolved



def _internal_pytest_receipt(result: dict[str, Any],
                            payload: dict[str, Any]) -> bool:
    """Check recorded pytest/diff return codes; does not rerun any tests.

    VERIFY can be driven either by the bounded deterministic verifier or the
    generic Coder verifier. Both must name the exact requested test files and
    report a passing git diff check. A summary verdict alone is insufficient.
    """
    tests=payload.get("tests")
    report=result.get("verification")
    if (not isinstance(tests,list) or not 0<len(tests)<=100
        or len(tests)!=len(set(tests))
        or any(not isinstance(t,str) or not t.startswith("tests/")
               or not t.endswith(".py") or len(t)>256
               or ".." in Path(t).parts or "\\" in t
               or "//" in t for t in tests)
        or result.get("tests")!=tests
        or not isinstance(report,dict)
        or report.get("verdict")!="PASS"
        or not isinstance(report.get("checks"),list)):
        return False
    checks=report["checks"]
    if len(checks)>64:
        return False
    diff_ok=pytest_ok=False
    for check in checks:
        if not isinstance(check,dict):
            return False
        name=check.get("name")
        passed=check.get("passed")
        rc=check.get("returncode")
        if passed is not True:
            return False
        if name=="git_diff_check":
            if rc==0 and type(rc) is int:
                diff_ok=True
            else:
                return False
        if name=="pytest":
            if (rc==0 and type(rc) is int and check.get("tests")==tests):
                pytest_ok=True
            else:
                return False
        if isinstance(name,str) and name.startswith("command:") and "pytest" in name:
            cmd=check.get("command")
            if (rc==0 and type(rc) is int and isinstance(cmd,list)
                and len(cmd)>=len(tests)+3
                and all(isinstance(k,str) for k in cmd)
                and cmd[-len(tests):]==tests
                and "pytest" in cmd):
                pytest_ok=True
            else:
                return False
    return diff_ok and pytest_ok

def _verify_coder_job_outcome(root: Path, expected_plans: dict[str, tuple[str,str]]
                              ) -> tuple[dict[str,int], bool]:
    """Bounded original VERIFY job linkage. A PASS is not independent proof."""
    counts={
        "completed_verify_job_receipts":0,
        "completed_verify_report_pass":0,
        "completed_verify_report_fail":0,
        "completed_verify_pass_with_internal_test_receipt":0,
        "completed_verify_pass_without_sufficient_test_receipt":0,
        "internal_test_receipts_all_named_test_paths_present":0,
        "internal_test_receipts_one_or_more_test_paths_missing":0,
        "failed_verify_job_receipts":0,
        "untrusted_or_inconsistent_verify_job_receipts":0,
    }
    if not expected_plans:
        return counts,False
    root_jobs=root/"runtime/coder/jobs"
    if root_jobs.is_symlink():
        return counts,True
    seen_jobs:set[str]=set()
    inspected=0
    incomplete=False
    for state in ("completed","failed"):
        folder=root_jobs/state
        if folder.is_symlink():
            incomplete=True
            continue
        if not folder.is_dir():
            continue
        for path in folder.glob("coder_job_*.json"):
            inspected+=1
            if inspected>MAX_CODER_JOB_RECEIPTS:
                return counts,True
            # Reject unreadable/unsafe receipts without interpreting content.
            try:
                job=_read_safe(path,MAX_RECORD)
            except (OSError,ValueError,UnicodeError,TypeError):
                incomplete=True
                continue
            payload=job.get("payload")
            if not isinstance(payload,dict):
                continue
            source=payload.get("source_plan_job_id")
            if (not isinstance(source,str) or source not in expected_plans
                or job.get("kind")!="VERIFY"):
                continue
            task,work=expected_plans[source]
            job_id=job.get("id")
            if (not isinstance(job_id,str) or not CODER_JOB_ID.fullmatch(job_id)
                or path.stem!=job_id or job_id in seen_jobs
                or job.get("task_id")!=task
                or payload.get("source_plan_task_id")!=task
                or payload.get("department_work_id")!=work
                or payload.get("execution_authority")!="none"):
                counts["untrusted_or_inconsistent_verify_job_receipts"]+=1
                continue
            seen_jobs.add(job_id)
            other_dir="failed" if state=="completed" else "completed"
            # A contradictory terminal receipt cannot count as a PASS,
            # regardless of which directory is traversed first.
            if (root_jobs/other_dir/(job_id+".json")).exists():
                counts["untrusted_or_inconsistent_verify_job_receipts"]+=1
                continue
            if state=="failed":
                if job.get("status")=="FAILED":
                    counts["failed_verify_job_receipts"]+=1
                else:
                    counts["untrusted_or_inconsistent_verify_job_receipts"]+=1
                continue
            result=job.get("result")
            check=result.get("verification") if isinstance(result,dict) else None
            verdict=check.get("verdict") if isinstance(check,dict) else None
            if (job.get("status")!="COMPLETED" or job.get("error") is not None
                or not isinstance(result,dict)
                or result.get("production_mutation") is not False
                or result.get("external_execution_performed") is True
                or result.get("execution_authority") not in (None,"none")
                or not isinstance(check,dict)
                or not isinstance(check.get("checks"),list)
                or verdict not in ("PASS","FAIL")):
                counts["untrusted_or_inconsistent_verify_job_receipts"]+=1
                continue
            counts["completed_verify_job_receipts"]+=1
            counts["completed_verify_report_pass"]+=int(verdict=="PASS")
            counts["completed_verify_report_fail"]+=int(verdict=="FAIL")
            if verdict=="PASS":
                has_test_proof=_internal_pytest_receipt(result,payload)
                counts["completed_verify_pass_with_internal_test_receipt"]+=int(has_test_proof)
                counts["completed_verify_pass_without_sufficient_test_receipt"]+=int(not has_test_proof)
                if has_test_proof:
                    # Availability is a current filesystem observation, not a
                    # fresh test execution or authentic code-change receipt.
                    declared=payload["tests"]
                    present=all(
                        (root/test).is_file() and not (root/test).is_symlink()
                        for test in declared)
                    counts["internal_test_receipts_all_named_test_paths_present"]+=int(present)
                    counts["internal_test_receipts_one_or_more_test_paths_missing"]+=int(not present)
    return counts,incomplete

def _source_context(root: Path, row: dict[str, str],
                    indexed_done: dict[str, Path]) -> tuple[tuple[str, ...], dict[str, str], tuple[str, str | None], tuple[str,str,str] | None]:
    # The existing SkillForge auditor already validated the candidate against
    # the original DONE work. Recheck the immutable-looking content during this
    # second read rather than trusting an index entry which may have changed.
    source=row["source_work_sha256"]
    path=indexed_done.get(source)
    if path is None:
        raise ValueError("original DONE work missing after source audit")
    work=_read_safe(path, MAX_RECORD)
    source_row=root/"runtime/skillforge/observations"/(row["candidate_id"]+".json")
    observation=_read_safe(source_row,MAX_OBSERVATION_BYTES)
    result=work.get("result")
    refs=work.get("result_evidence_refs")
    if (work.get("status")!="DONE" or work.get("id")!=path.stem
            or _sha(path.stem)!=source or not isinstance(result,dict)
            or not isinstance(refs,list) or not refs
            or any(not isinstance(ref,str) or not ref.strip() for ref in refs)
            or observation.get("source_work_sha256")!=source
            or observation.get("candidate_id")!=row["candidate_id"]
            or observation.get("component")!=row["component"]
            or observation.get("adapter")!=row["adapter"]):
        raise ValueError("original DONE work no longer matches validated observation")
    hashes=sorted({_sha(ref) for ref in refs})
    result_sha=_sha(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False))
    if (observation.get("source_evidence_sha256")!=hashes
            or observation.get("source_result_sha256")!=result_sha):
        raise ValueError("original referenced evidence or result changed")
    context={}
    for field in ("plan_id","goal_key","worker_id"):
        value=work.get(field)
        # Only count correctly shaped, nonempty contextual identifiers. We
        # publish counts, never names, identities, work ids, or raw references.
        if isinstance(value,str) and value.strip() and len(value)<=512:
            context[field]=_sha(value)
    coder_outcome = (
        _correlate_original_coder_plan(root,work,refs)
        if row["component"]=="empire_coder"
           and row["adapter"]=="empire_coder_plan_bridge"
        else ("NOT_CODER",None)
    )
    plan_link=None
    if (row["component"]=="empire_coder"
        and row["adapter"]=="empire_coder_plan_bridge"
        and coder_outcome[0]=="COMPLETED_CODER_PLAN_JOB"):
        plan_link=(
            result["coder_job_id"],
            result["coder_task_id"],
            work["id"],
        )
    return tuple(hashes),context,coder_outcome,plan_link


def review_independent_skill_evidence(root: str | Path, *,
                                      max_observations: int = MAX_OBSERVATIONS) -> dict[str, Any]:
    """Classify original-source *diversity* without claiming verified skill quality.

    It is not valid to count N completed queue items as N independent proofs,
    especially when they all reuse an unversioned latest.json reference.
    """
    if type(max_observations) is not int or not 1 <= max_observations <= MAX_OBSERVATIONS:
        raise ValueError("invalid bounded observation review")
    root=Path(root).resolve()
    validated, invalid, truncated = _verified_learning_observations(
        root,max_observations=max_observations)
    done=root/"runtime/departments/work/done"
    if done.is_symlink():
        raise ValueError("unsafe canonical work directory")
    work_index:dict[str,Path]={}
    if done.is_dir():
        for path in done.glob("dept_work_*.json"):
            if WORK_ID.fullmatch(path.stem) and not path.is_symlink():
                work_index[_sha(path.stem)]=path

    groups:dict[tuple[str,str],dict[str,Any]]=defaultdict(
        lambda: {"records":0,"refs":set(),"plans":set(),"goals":set(),
                 "workers":set(),"work_sources":set(),"missing_plan_count":0,
                 "missing_worker_count":0,
                 "coder_plan_scheduler_correlated":0,
                 "coder_plan_scheduler_uncorrelated":0,
                 "coder_plan_scheduler_failed":0,
                 "coder_plan_failure_reasons":defaultdict(int),
                 "coder_completed_plan_job_sources":{}})
    rejected=0
    for row in validated:
        try:
            ref_hashes,ctx,(coder_state,coder_reason),plan_link=_source_context(root,row,work_index)
        except (OSError,ValueError,UnicodeError,TypeError,OverflowError):
            rejected+=1
            continue
        key=(row["component"],row["adapter"])
        data=groups[key]
        data["records"]+=1
        data["work_sources"].add(row["source_work_sha256"])
        data["refs"].update(ref_hashes)
        if key==("empire_coder","empire_coder_plan_bridge"):
            data["coder_plan_scheduler_correlated"]+=int(coder_state=="COMPLETED_CODER_PLAN_JOB")
            data["coder_plan_scheduler_failed"]+=int(coder_state=="FAILED_CODER_PLAN_JOB")
            data["coder_plan_scheduler_uncorrelated"]+=int(coder_state=="UNRESOLVED_CODER_PLAN_JOB")
            if coder_state=="FAILED_CODER_PLAN_JOB" and coder_reason is not None:
                data["coder_plan_failure_reasons"][coder_reason]+=1
            if plan_link is not None:
                job_id,task_id,work_id=plan_link
                data["coder_completed_plan_job_sources"][job_id]=(task_id,work_id)
        for name,bucket in (("plan_id","plans"),("goal_key","goals"),("worker_id","workers")):
            if name in ctx:
                data[bucket].add(ctx[name])
            elif name=="plan_id":
                data["missing_plan_count"]+=1
            elif name=="worker_id":
                data["missing_worker_count"]+=1

    # Downstream VERIFY work is advisory evidence only, not implementation.
    coder_jobs_incomplete=False
    for key,group in groups.items():
        if key!=("empire_coder","empire_coder_plan_bridge"):
            continue
        counts,coder_jobs_incomplete=_verify_coder_job_outcome(
            root,group["coder_completed_plan_job_sources"])
        group["downstream_verify_receipts"]=counts
    families=[]
    for (component,adapter),data in sorted(groups.items()):
        distinct=len(data["refs"])
        family={
            "component":component,"adapter":adapter,
            "canonical_done_observation_count":data["records"],
            "distinct_canonical_work_count":len(data["work_sources"]),
            "distinct_evidence_reference_string_count":distinct,
            "distinct_plan_context_count":len(data["plans"]),
            "distinct_goal_context_count":len(data["goals"]),
            "distinct_worker_context_count":len(data["workers"]),
            "missing_plan_context_count":data["missing_plan_count"],
            "missing_worker_context_count":data["missing_worker_count"],
            "original_coder_plan_scheduler_pairs_correlated":data["coder_plan_scheduler_correlated"],
            "original_coder_plan_scheduler_pairs_uncorrelated":data["coder_plan_scheduler_uncorrelated"],
            "original_coder_plan_jobs_failed":data["coder_plan_scheduler_failed"],
            "original_coder_plan_failure_reason_counts":dict(sorted(data["coder_plan_failure_reasons"].items())),
            "department_done_is_not_coder_job_success":True,
            "coder_plan_scheduler_correlation_is_not_implementation_proof":True,
            "independently_verified_code_implementations":0,
            "downstream_coder_verify_jobs":dict(data.get("downstream_verify_receipts") or {
                "completed_verify_job_receipts":0,
                "completed_verify_report_pass":0,
                "completed_verify_report_fail":0,
                "completed_verify_pass_with_internal_test_receipt":0,
                "completed_verify_pass_without_sufficient_test_receipt":0,
                "internal_test_receipts_all_named_test_paths_present":0,
                "internal_test_receipts_one_or_more_test_paths_missing":0,
                "failed_verify_job_receipts":0,
                "untrusted_or_inconsistent_verify_job_receipts":0,
            }),
            "verify_report_pass_is_not_independent_outcome_proof":True,
            "test_path_availability_is_not_test_reexecution":True,
            "reference_diversity_status":(
                "REUSED_SINGLE_REFERENCE_STRING" if distinct<=1
                else "MULTIPLE_REFERENCE_STRINGS_CUSTODY_UNVERIFIED"),
            "original_referenced_artifacts_independently_authenticated":False,
            "independently_verified_successful_agent_outcomes":0,
            "independent_holdout_verified":False,
            "skill_approval_authorized":False,
            "review_only":True,
        }
        families.append(family)

    audit_complete=(invalid==0 and rejected==0 and truncated==0
                    and not coder_jobs_incomplete)
    return {
        "schema_version":"empire.skillforge.independent_evidence_review.v1",
        "mode":"OBSERVE","status":(
            "SOURCE_DIVERSITY_REVIEW_ONLY" if audit_complete
            else "SOURCE_INTEGRITY_OR_COVERAGE_HOLD"),
        "canonical_observations_reviewed":sum(x["canonical_done_observation_count"] for x in families),
        "original_skillforge_invalid_observations":invalid,
        "second_read_rejected_observations":rejected,
        "inventory_truncated":bool(truncated),
        "coder_downstream_job_inventory_incomplete":bool(coder_jobs_incomplete),
        "family_count":len(families),
        "families_with_single_shared_reference":sum(
            x["reference_diversity_status"]=="REUSED_SINGLE_REFERENCE_STRING"
            for x in families),
        "independently_authenticated_source_events":0,
        "independently_verified_skill_outcomes":0,
        "promotion_ready_skill_count":0,
        "families":families,
        "raw_identifiers_disclosed":False,
        "department_queue_mutated":False,
        "automatic_promotion":False,
        "execution_authority":"none",
    }
