"""V3 owner-fed quote funnel observability. Read-only, aggregate, no PII.

Existing website, matching, canonical EmpireDB and outcome owners remain authoritative.
This module does not create customers, mutate records or assert settlement.
"""
from __future__ import annotations
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from empire_os.quote_acquisition_v2 import rank_quote_buyers

SCHEMA = "empire.quote_acquisition.v3"
STAGES = ("captured", "qualified", "matched", "buyer_accepted",
          "appointment_booked", "job_completed", "settled")


def review_quote_funnel(*, enquiries: Sequence[Mapping[str, Any]],
                        buyer_candidates: Mapping[str, Sequence[Mapping[str, Any]]]
                        ) -> dict[str, Any]:
    """Owner-fed, bounded batch; stage requires successive independent receipts.

    Customer contact fields are ignored, never echoed. Stage counters only mean
    received owner-asserted evidence, not independent canonical verification.
    """
    if not isinstance(enquiries, (tuple, list)) or len(enquiries) > 100:
        raise ValueError("bounded enquiries required")
    if not isinstance(buyer_candidates, Mapping):
        raise ValueError("candidate mapping required")
    counts = Counter()
    results = []
    seen = set()
    for row in enquiries:
        if not isinstance(row, Mapping):
            raise ValueError("enquiry mapping required")
        ref = row.get("enquiry_ref")
        if not isinstance(ref, str) or not ref or len(ref) > 120 or ref in seen:
            raise ValueError("unique opaque enquiry_ref required")
        seen.add(ref)
        evidence = row.get("evidence")
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence mapping required")
        candidates = buyer_candidates.get(ref, ())
        review = rank_quote_buyers(vertical=row.get("vertical"),
                                   request=evidence, candidates=candidates)
        ready = [c for c in review["ranked_candidates"]
                 if c["status"] == "READY_FOR_HUMAN_REVIEW"]
        # A progressed stage cannot skip prior proof; owner receipts must be
        # explicit booleans, not a forecast score or a status label.
        proof = {
            "captured": evidence.get("first_party_request") is True,
            "qualified": all(evidence.get(k) is True for k in (
                "first_party_request", "contact_permission",
                "privacy_notice_acknowledged", "service_scope_present",
                "location_present", "genuine_customer_intent")),
            "matched": bool(ready),
            "buyer_accepted": evidence.get("canonical_buyer_acceptance_verified") is True,
            "appointment_booked": evidence.get("canonical_appointment_verified") is True,
            "job_completed": evidence.get("canonical_completion_verified") is True,
            "settled": evidence.get("canonical_settlement_verified") is True,
        }
        stage = "held"
        for name in STAGES:
            if not proof[name]:
                break
            counts[name] += 1
            stage = name
        results.append({
            "enquiry_ref": ref, "vertical": review["vertical"],
            "stage": stage,
            "reviewable_buyer_count": len(ready),
            "recommended_buyer_ref": ready[0]["buyer_ref"] if ready else None,
            "blockers": review["ranked_candidates"][0]["missing_evidence"]
                        if review["ranked_candidates"] and not ready else [],
        })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "enquiries_reviewed": len(results),
        "stage_counts_owner_asserted": {s: counts[s] for s in STAGES},
        "queue": results, "dashboard_contract_only": True,
        "source_verification": "UNVERIFIED_OWNER_INPUT",
        "outbound_authorized": False, "customer_data_disclosed": False,
        "crm_writes": False, "payment_execution": False,
        "realised_revenue": None,
    }
