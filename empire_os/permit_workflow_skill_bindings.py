"""SkillForge-aware stages in ONE existing Permit Intelligence review workflow.

Reads the existing canonical Empire-authored skill catalogue, static review
and explicit SHA256-pinned SkillForge trust registry. Never executes a skill,
scripts, downloads, outbound tools, or user-provided email instructions.
Selecting a skill is advisory only, even when explicitly trust-pinned.

A catalogued skill is NOT approved by presence alone. The original trust
registry is empty at time of implementation; don't pretend it is populated.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime,timezone
from hashlib import sha256
import re
from pathlib import Path
from typing import Any

from empire_os.permit_multimarket_registry import digest
from empire_os.skill_exchange import (
    TASK_SKILLS,discover_task_skills,recommend_work_item_skills,
)
from empire_os.skill_review import review_local_skill
from empire_os.skill_trust import SkillTrustError,load_pinned_skill,read_trust_registry

SCHEMA="empire.permit_intelligence.original_skillforge_workflow_bindings.v1"
# Match the ORIGINAL SkillForge task map; no fuzzy mapping derived from
# untrusted Gmail text, contractor domains or user-generated ad copy.
STAGES=(
    ("prospect_source", "lead_generation"),
    ("canonical_identity", "entity_resolution"),
    ("permit_source_truth", "evidence_analysis"),
    ("first_touch_copy", "email_drafting"),
    ("reply_intelligence", "commercial_reply"),
    ("commercial_release", "revenue_readiness"),
)
# Skill documentation is guidance only. The actual checks are the current
# executed deterministic code, the original CRM governor, and the founder.
STAGE_COMPONENTS={
    "prospect_source":"permit_public_signal_research",
    "canonical_identity":"permit_contact_identity_review",
    "permit_source_truth":"permit_source_evidence_review",
    "first_touch_copy":"permit_commercial_email_copy_review",
    "reply_intelligence":"permit_buyer_reply_triage",
    "commercial_release":"permit_commercial_release_review",
}
CONTROLS={
    "prospect_source":"PUBLIC_BUSINESS_SOURCE_AND_RIGHTS_REVIEW",
    "canonical_identity":"CANONICAL_RECIPIENT_EXACT_AND_COMPANY_IDENTITY",
    "permit_source_truth":"ORIGINAL_PROVENANCE_FRESHNESS_UNKNOWN_NOT_PASS",
    "first_touch_copy":"ORIGINAL_COPYWRITER_AND_COMPLIANCE_AGENT_REVIEW",
    "reply_intelligence":"UNTRUSTED_INBOUND_CANNOT_AUTHORISE_ACTION",
    "commercial_release":"FOUNDER_AND_GOVERNOR_SEND_HOLD",
}


def _now(now:datetime)->str:
    if not isinstance(now,datetime) or now.utcoffset() is None:
        raise ValueError("SKILLFORGE_WORKFLOW_REQUIRES_AWARE_CLOCK")
    return now.astimezone(timezone.utc).isoformat()


def bind_existing_skills(*,repo_root:Path,
                         now:datetime,
                         library_root:Path|None=None,
                         trust_registry:Path|None=None)->dict:
    from empire_os.skills_library import SKILLS_ROOT
    root=repo_root.resolve()
    library=(library_root or root/"empire_os/skills_library/skills").resolve()
    registry_file=trust_registry or root/"config/skill_trust_registry.json"
    # Explicit root and existing local skill directory required. NO external
    # plugin install, config rewrite or fallback to an untrusted repo.
    if not library.is_dir() or library.is_symlink():
        raise ValueError("ORIGINAL_SKILLFORGE_LIBRARY_MISSING_OR_UNSAFE")
    try:
        trust=read_trust_registry(registry_file)
    except SkillTrustError:
        trust=None
    if trust is not None and (
        trust.get("schema_version")!="empire.skill_trust.v1"
        or not isinstance(trust.get("approved_skills"),dict)):
        raise ValueError("ORIGINAL_SKILLFORGE_TRUST_REGISTRY_INVALID")

    stages=[]
    all_pinned=True
    seen=set()
    for stage,task in STAGES:
        if task not in TASK_SKILLS:
            raise ValueError("ORIGINAL_SKILLFORGE_UNMAPPED_STAGE")
        # SkillForge's existing work-item selector must agree with the
        # workflow's exact task identity, not infer from prospect prose.
        component=STAGE_COMPONENTS[stage]
        routed=recommend_work_item_skills({
            "id":f"original-permit:{stage}",
            "department_keys":["email"],
            "target_component":component,
        },root=library)
        routed_row=routed["skill_recommendations"][0]
        if (routed_row.get("selection_basis")!="component_allowlist"
            or routed_row.get("task")!=task
            or routed_row.get("execution_authority")!="none"):
            raise ValueError("ORIGINAL_SKILLFORGE_COMPONENT_ROUTING_MISMATCH")
        result=discover_task_skills(task,root=library)
        candidates=result["skills"]
        if len(candidates)!=1 or result["status"]!="local_candidates":
            raise ValueError("ORIGINAL_SKILLFORGE_SKILL_NOT_FOUND")
        entry=candidates[0]
        name=entry["name"]
        if name in seen:
            raise ValueError("ORIGINAL_SKILLFORGE_DUPLICATE_STAGE_SKILL")
        seen.add(name)
        original_file=library/name/"SKILL.md"
        review=review_local_skill(name,root=library)
        if review["status"]=="blocked":
            raise ValueError("ORIGINAL_SKILLFORGE_SKILL_FAILED_STATIC_REVIEW")
        # Only the exact existing original skill file is examined. The
        # read-only static review cannot approve a skill by itself.
        file_sha=sha256(original_file.read_bytes()).hexdigest()
        if entry["sha256"]!=file_sha:
            raise ValueError("ORIGINAL_SKILLFORGE_SKILL_CHANGED_DURING_BIND")
        trust_state="CANDIDATE_NOT_APPROVED"
        try:
            pinned=load_pinned_skill(name,root=library,registry=trust)
            if pinned["sha256"]!=file_sha or pinned["execution_authority"]!="none":
                raise ValueError("ORIGINAL_SKILLFORGE_PINNED_SKILL_UNTRUSTED")
            trust_state="APPROVED_DIGEST_PINNED"
        except SkillTrustError:
            all_pinned=False
        stages.append({
            "stage":stage,
            "skillforge_task":task,
            "original_work_item_component":component,
            "skill_name":name,
            "skill_document_sha256":file_sha,
            "skillforge_status":trust_state,
            "policy_control":CONTROLS[stage],
            "static_skill_review":"MANUAL_SECURITY_REVIEW_REQUIRED",
            "documentation_loaded_as_agent_authority":False,
            "skill_scripts_executed":False,
            "permission_to_send":False,
        })
    report={
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "observed_at_utc":_now(now),
        "original_stack":"ONE_EMPIREOS_ONE_EMPIREDB_ONE_SMART_CRM",
        "skills_root_type":"ORIGINAL_LOCAL_SKILL_LIBRARY",
        "registry_status":"VALID_ORIGINAL_TRUST_REGISTRY" if trust else
            "REGISTRY_UNAVAILABLE_HELD",
        "skillforge_stages":stages,
        "skills_discovered":len(stages),
        "skills_approved_pinned":sum(
            x["skillforge_status"]=="APPROVED_DIGEST_PINNED" for x in stages),
        "workflow_skill_authority_state":(
            "PINNED_SKILL_CONTEXT_ONLY_NOT_EXECUTION_AUTHORITY" if all_pinned
            else "CANDIDATE_REVIEW_ONLY_UNAPPROVED_SKILLS_HELD"),
        "execution_authority":"none",
        "email_send_authorized":False,
        "source_distribution_authorized":False,
        "original_canonical_governor_overridden":False,
        "production_database_writes":0,
        "scripts_or_skills_executed":False,
    }
    report["skill_bindings_sha256"]=digest(report)
    validate_bindings(report)
    return report


def validate_bindings(report:Mapping[str,Any])->None:
    if (not isinstance(report,Mapping)
        or report.get("schema_version")!=SCHEMA
        or report.get("skill_bindings_sha256")!=digest({
            k:v for k,v in report.items() if k!="skill_bindings_sha256"})
        or report.get("skills_discovered")!=len(STAGES)
        or report.get("execution_authority")!="none"
        or report.get("email_send_authorized") is not False
        or report.get("source_distribution_authorized") is not False
        or report.get("original_canonical_governor_overridden") is not False
        or report.get("production_database_writes")!=0
        or report.get("scripts_or_skills_executed") is not False):
        raise ValueError("PERMIT_SKILLFORGE_WORKFLOW_AUTHORITY_INVALID")
    rows=report.get("skillforge_stages")
    if not isinstance(rows,list) or len(rows)!=len(STAGES):
        raise ValueError("PERMIT_SKILLFORGE_STAGE_COUNT_UNTRUSTED")
    for expected,row in zip(STAGES,rows):
        if (row.get("stage")!=expected[0]
            or row.get("skillforge_task")!=expected[1]
            or row.get("original_work_item_component")!=STAGE_COMPONENTS[expected[0]]
            or row.get("skill_name")!=TASK_SKILLS[expected[1]][1][0]
            or not re.fullmatch(r"[a-f0-9]{64}",str(row.get("skill_document_sha256") or ""))
            or row.get("skillforge_status") not in (
                "CANDIDATE_NOT_APPROVED","APPROVED_DIGEST_PINNED")
            or row.get("documentation_loaded_as_agent_authority") is not False
            or row.get("skill_scripts_executed") is not False
            or row.get("permission_to_send") is not False):
            raise ValueError("PERMIT_SKILLFORGE_STAGE_MUTATED_OR_ESCALATED")
    pinned=sum(x["skillforge_status"]=="APPROVED_DIGEST_PINNED" for x in rows)
    if (report.get("skills_approved_pinned")!=pinned
        or report.get("workflow_skill_authority_state")!=(
            "PINNED_SKILL_CONTEXT_ONLY_NOT_EXECUTION_AUTHORITY" if pinned==len(STAGES)
            else "CANDIDATE_REVIEW_ONLY_UNAPPROVED_SKILLS_HELD")):
        raise ValueError("PERMIT_SKILLFORGE_APPROVAL_CLAIM_UNTRUSTED")
