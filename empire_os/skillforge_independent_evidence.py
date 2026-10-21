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
from typing import Any

from empire_os.skillforge_learning import (
    MAX_RECORD, WORK_ID, _verified_learning_observations,
)

MAX_OBSERVATIONS = 5000
MAX_OBSERVATION_BYTES = 64_000


def _sha(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _read_safe(path: Path, limit: int) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("missing or unsafe original evidence packet")
    item=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(item,dict):
        raise ValueError("evidence packet must be an object")
    return item


def _source_context(root: Path, row: dict[str, str],
                    indexed_done: dict[str, Path]) -> tuple[tuple[str, ...], dict[str, str]]:
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
    return tuple(hashes),context


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
                 "missing_worker_count":0})
    rejected=0
    for row in validated:
        try:
            ref_hashes,ctx=_source_context(root,row,work_index)
        except (OSError,ValueError,UnicodeError,TypeError,OverflowError):
            rejected+=1
            continue
        key=(row["component"],row["adapter"])
        data=groups[key]
        data["records"]+=1
        data["work_sources"].add(row["source_work_sha256"])
        data["refs"].update(ref_hashes)
        for name,bucket in (("plan_id","plans"),("goal_key","goals"),("worker_id","workers")):
            if name in ctx:
                data[bucket].add(ctx[name])
            elif name=="plan_id":
                data["missing_plan_count"]+=1
            elif name=="worker_id":
                data["missing_worker_count"]+=1

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

    audit_complete=invalid==0 and rejected==0 and truncated==0
    return {
        "schema_version":"empire.skillforge.independent_evidence_review.v1",
        "mode":"OBSERVE","status":(
            "SOURCE_DIVERSITY_REVIEW_ONLY" if audit_complete
            else "SOURCE_INTEGRITY_OR_COVERAGE_HOLD"),
        "canonical_observations_reviewed":sum(x["canonical_done_observation_count"] for x in families),
        "original_skillforge_invalid_observations":invalid,
        "second_read_rejected_observations":rejected,
        "inventory_truncated":bool(truncated),
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
