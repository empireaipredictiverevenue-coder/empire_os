"""Founder-review trial-to-paid evidence adapter for existing EmpireOS.

Never initiates trials, outreach, fulfilment, invoicing, or payments. A proposed
trial is distinct from an accepted buyer relationship or settled revenue.
"""
from collections.abc import Mapping

SCHEMA = "empire.commercial_trial_conversion.v1"
STAGES = ("prospect_qualified", "terms_accepted", "trial_scope_approved",
          "trial_result_verified", "buyer_acceptance_verified",
          "invoice_verified", "settlement_verified")


def review_trial(evidence: Mapping[str, object]) -> dict:
    if not isinstance(evidence, Mapping):
        raise ValueError("evidence mapping required")
    proof = {stage: evidence.get(stage) is True for stage in STAGES}
    stage = "DISCOVERY"
    blockers = []
    for name in STAGES:
        if proof[name] and not blockers:
            stage = name.upper()
        elif not proof[name]:
            blockers.append(name)
    # Never claim payment from a Boolean supplied by an unverified owner.
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "owner_asserted_stage": stage,
        "unmet_evidence": blockers,
        "proposed_trial_limit": "One narrow, buyer-approved result; no open-ended free delivery",
        "next_review": blockers[0] if blockers else "Independent canonical settlement reconciliation",
        "source_verification": "UNVERIFIED_OWNER_INPUT",
        "contact_authorized": False,
        "trial_activated": False,
        "lead_delivered": False,
        "crm_writes": False,
        "invoice_issued": False,
        "payment_execution": False,
        "realised_revenue": None,
    }
