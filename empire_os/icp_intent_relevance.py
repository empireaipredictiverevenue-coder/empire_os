"""ICP fit and problem-to-solution research classification for social signals.

Scores are for ordering human evidence review only, never contact approval.
Keep claims as self-reports. Ignore sales pitches masquerading as buying intent.
"""
from __future__ import annotations
import re
from typing import Any, Mapping

from empire_os.pain_solution_engine import SOLUTION_MAP

PITCH = (
    re.compile(r"\b(?:we|i) (?:help|offer|provide|sell|build|specializ\w* in)\b", re.I),
    re.compile(r"\b(?:dm me|book a call|schedule a demo|contact me|i can help)\b", re.I),
    re.compile(r"\b(?:our (?:agency|clients|service|solution)|free consultation)\b", re.I),
)
DIRECT_REQUEST = (
    re.compile(r"\b(?:looking for|can anyone recommend|seeking|need help (?:with|getting)|want to buy|need to buy)\b", re.I),
    re.compile(r"\b(?:need|looking for).{0,70}\b(?:roofing leads?|appointments?|agency|clients?|customers?|crm|marketing help|software|automation)\b", re.I),
)
OPERATING_PROBLEM = (
    re.compile(r"\b(?:we|i) (?:own|run|manage|operate|started|took over) (?:a|an|my|our)\b", re.I),
    re.compile(r"\b(?:our|my) (?:[a-z-]+ )?(?:business|firm|company|leads|sales|customers|pipeline|marketing)\b", re.I),
    re.compile(r"\b(?:we|i) (?:struggle|struggled|spent|paid|lost|need|can't|cannot|haven't|do not have)\b", re.I),
)
GENERAL_ADVICE = (
    re.compile(r"\b(?:top \d+ tips|here is how to|in this article|let me explain|guide to|case study:)\b", re.I),
)

ALLOWED_PAIN = frozenset(SOLUTION_MAP)


def classify_icp_intent(detail: Mapping[str, Any]) -> dict[str, Any]:
    text = " ".join(str(detail.get(k) or "")[:1500] for k in ("title", "text"))
    if any(p.search(text) for p in PITCH):
        kind = "SELLER_PITCH"
    elif any(p.search(text) for p in DIRECT_REQUEST):
        kind = "EXPLICIT_REQUEST_UNVERIFIED"
    elif any(p.search(text) for p in GENERAL_ADVICE):
        kind = "CONTENT_OR_ADVICE"
    elif any(p.search(text) for p in OPERATING_PROBLEM):
        kind = "OPERATOR_PROBLEM_SELF_REPORTED"
    else:
        kind = "UNATTRIBUTED_DISCUSSION"
    pains = detail.get("pain_points") or []
    if not isinstance(pains, (list, tuple)):
        pains = []
    keys = [x for x in pains if isinstance(x, str) and x in ALLOWED_PAIN]
    proposals = []
    for key in dict.fromkeys(keys):
        m = SOLUTION_MAP[key]
        proposals.append({
            "pain_point": key,
            "offer_key": m["offer_key"],
            "candidate_products": list(m["products"][:3]),
            "review_actions": list(m["next_actions"][:3]),
            "verified_product_fit": False,
            "buyer_willingness_to_pay_verified": False,
        })
    return {
        "intent_class": kind,
        "operator_identity_verified": False,
        "buyer_purchase_intent_verified": False,
        "explicit_request_for_solutions": kind == "EXPLICIT_REQUEST_UNVERIFIED",
        "research_review_priority": (
            "HIGH" if kind == "EXPLICIT_REQUEST_UNVERIFIED"
            else "MEDIUM" if kind == "OPERATOR_PROBLEM_SELF_REPORTED"
            else "LOW"
        ),
        "candidate_offer_hypotheses": proposals,
        "outbound_authorized": False,
    }
