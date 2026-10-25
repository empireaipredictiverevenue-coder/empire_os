"""Reuse existing EmpireOS Copywriter optimisation for Permit email draft QA.

Gary Halbert-inspired plain, specific, curiosity-led direct-response writing
principles only; original/copyrighted swipe copy is neither bundled nor
imitated verbatim. Actual content and proof/permission remain founder-reviewed.

Calls the SAME outbound_message_optimizer quality checker used by the
existing canonical EmpireOS copywriter. This is read-only quality intelligence,
not a new copy engine, email sender, permission, or proof of permit jobs.
"""
from __future__ import annotations
from typing import Any

from empire_os.outreach_message_optimizer import (
    human_copy_gate, review_message, build_subject_variants,
)

def check_existing_draft(*,company:str,market:str,subject:str,body:str)->dict[str,Any]:
    if not all(isinstance(x,str) and x.strip() for x in (company,market,subject,body)):
        raise ValueError("PERMIT_EXISTING_COPY_BRIEF_INCOMPLETE")
    if len(subject)>200 or len(body)>20_000:
        raise ValueError("PERMIT_EXISTING_COPY_UNBOUNDED")
    human=human_copy_gate(subject=subject,body=body)
    # CTA syntax is structural; value and verified buyer interest must never be
    # inferred from a rhetorical question. Do not supply fabricated proof.
    first_question=next(
        (line.strip() for line in body.splitlines() if "?" in line),
        "",
    )
    existing=review_message(
        subject=subject,body=body,cta=first_question,evidence={}
    )
    suggestions=build_subject_variants(
        business_name=company,reason_now="permit-stage research",territory=market
    )
    # Subject tests are internal suggestions, never provider edits or approvals.
    return {
        "schema_version":"empire.permit.copywriter.original_quality_review.v1",
        "canonical_engine":"empire_os.outreach_message_optimizer",
        "canonical_human_copy_gate_policy":human["policy"],
        "human_copy_gate_eligible":human["eligible"],
        "human_copy_gate_blockers":list(human["blockers"]),
        "quality_score":existing["structural_score"],
        "quality_issues":list(existing["issues"]),
        "word_count":existing["word_count"],
        "one_primary_question":body.count("?")==1,
        "subject_variant_count":len(suggestions),
        "source_specific_proof_verified":False,
        "original_company_contact_purpose_approved":False,
        "requires_founder_exact_copy_review":True,
        "drafting_or_review_only":True,
        "send_enabled":False,
    }
