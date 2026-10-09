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
    # "Looking for advice about my career" is not a purchase request.
    re.compile(r"\b(?:looking for|seeking|can anyone recommend|want to buy|need to buy|need help (?:with|getting))\b.{0,95}\b(?:qualified leads?|appointments?|customers?|marketing (?:help|agency|services?)|crm|sales automation|lead gen(?:eration)?|software|seo|intake)\b", re.I),
    re.compile(r"\b(?:need|looking for).{0,70}\b(?:roofing leads?|appointments?|agency|clients?|customers?|crm|marketing help|software|automation)\b", re.I),
)
NON_PURCHASE = (
    re.compile(r"\[\s*hiring\s*\]", re.I),
    re.compile(r"\b(?:\[hiring\]|hiring (?:client|sales|marketing|account)|territory account manager|fractional cmo|head of marketing|field sales engineer|looking for (?:an?|our) (?:account|sales|marketing|territory) manager|looking for (?:a|an) (?:client acquisition|business development|sales) partner)\b", re.I),
    re.compile(r"\b(?:we(?:'re| are) hiring|job posting|job opportunity|apply now|send (?:your|a) (?:cv|resume)|careers?@|join our team|vacancy|recruiting)\b", re.I),
    re.compile(r"\b(?:my (?:sales )?career|career growth|career advice|which role should i|where should i take my career|looking for (?:my )?next role|what would you do: stay|need to find a new job)\b", re.I),
)
SELF_PROMOTION = (
    # Recruiting multiple content practitioners as experiment participants
    # is not a request to purchase an SEO service.
    re.compile(r"\blooking for (?:seo )?content editors\b.{0,95}\b(?:agency practitioners|freelancers)\b", re.I),
    re.compile(r"\b(?:i|we) (?:built|launched|created|developed)\b.{0,95}\b(?:saas|tool|platform|product|app|service)\b", re.I),
    re.compile(r"^\s*(?:built|launched|created)\b.{0,95}\b(?:saas|tool|platform|product|app|service)\b", re.I),
    re.compile(r"\b(?:my|our) (?:new )?(?:product|lead service|agency|platform|tool)\b.{0,55}\b(?:offers?|provides?|generates?|customers?|leads?)\b", re.I),
    re.compile(r"\b(?:anyone|are you|who(?:\'s| is)) looking for\b.{0,85}\b(?:seo|marketing|growth|automation|leads?|agency|services?|expert)\b", re.I),
    re.compile(r"\b(?:for free|free trial)\b.{0,70}\b(?:try (?:my|our)|lead finder|mailer|product|tool)\b", re.I),
    re.compile(r"\b(?:we helped|how we helped|we deployed|our clients?|i now get to help)\b.{0,110}\b(?:consultancy|marketing|sales|seo|leads?|business|brands?|clients?)\b", re.I),
)
OPERATING_PROBLEM = (
    re.compile(r"\b(?:we|i) (?:own|run|manage|operate|started|took over) (?:a|an|my|our)\b", re.I),
    re.compile(r"\b(?:our|my) (?:[a-z-]+ )?(?:business|firm|company|leads|sales|customers|pipeline|marketing)\b", re.I),
    re.compile(r"\b(?:we|i) (?:struggle|struggled|spent|paid|lost|need|can't|cannot|haven't|do not have)\b", re.I),
)
GENERAL_ADVICE = (
    re.compile(r"\b(?:top \d+ tips|here is how to|in this article|let me explain|guide to|case study:|handy guide for beginners|sales formula)\b", re.I),
)

ALLOWED_PAIN = frozenset(SOLUTION_MAP)


def classify_icp_intent(detail: Mapping[str, Any]) -> dict[str, Any]:
    text = " ".join(str(detail.get(k) or "")[:1500] for k in ("title", "text"))
    if any(p.search(text) for p in NON_PURCHASE):
        kind = "NON_COMMERCIAL_HIRING_OR_CAREER"
    elif any(p.search(text) for p in PITCH + SELF_PROMOTION):
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
