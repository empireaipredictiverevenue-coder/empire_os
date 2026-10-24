"""Original EmpireOS PRIME: expressed concern and objection review, OBSERVE only.

Current, single inbound reply text is untrusted. Do not claim mind-reading,
emotional diagnosis, private personality traits, hidden motivations, deception,
purchasing intent, or causal efficacy. No contact-level longitudinal scoring.
Reuse original Conversation OS person/thread-bound structural preflight; a
caller-asserted preflight is NOT independent provider/tenant/source authority.
This module reads/writes no external systems and emits no raw message content.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import re

from empire_os.rapport_intent_cta import _buyer_text, _preflight

SCHEMA = "empire.prime.conversation_objection_expression_shadow.v1"
FOUNDER_SCHEMA = "empire.prime.founder_conversation_objection_status.v1"
MAX_BODY = 5000
# Stable, non-sensitive labels on CURRENT expressed statements alone.
CUES: tuple[tuple[str, str, str], ...] = (
    ("PRICE_OR_BUDGET_QUESTION",
     r"\b(?:how much|what(?:'s| is) (?:the |your )?(?:price|cost)|pricing|"
     r"cost breakdown|what does (?:this|it) cost|within (?:our |my )?budget|too expensive|over budget|"
     r"can't afford|cannot afford)\b",
     "ANSWER_PRICE_WITH_VERIFIED_TERMS_OR_MARK_UNAVAILABLE"),
    ("TRUST_OR_PROOF_QUESTION",
     r"\b(?:case stud(?:y|ies)|proof|references|how do we know|"
     r"how can (?:we|i) verify|evidence of (?:results|claims)|"
     r"is this legitimate|is this legit|can you demonstrate)\b",
     "OFFER_VERIFIABLE_EVIDENCE_WITHOUT_GUARANTEES"),
    ("TIMING_OR_CAPACITY_CONCERN",
     r"\b(?:not (?:right )?now|next (?:month|quarter|year)|"
     r"don't have (?:the )?time|no capacity|too busy|"
     r"not ready (?:yet|to proceed)|not (?:a|the) priority)\b",
     "RESPECT_TIMING_AND_ASK_IF_A_FUTURE_REPLY_IS_WELCOME"),
    ("DECISION_AUTHORITY_QUESTION",
     r"\b(?:need (?:to (?:check|speak|discuss)|approval|sign[ -]?off)|"
     r"my (?:manager|boss|partner)|our (?:board|team) (?:needs|must)|"
     r"decision from (?:our|the) team)\b",
     "SUPPLY_CLEAR_WRITTEN_MATERIAL_FOR_ACTUAL_DECISION_MAKER"),
    ("SCOPE_OR_FIT_QUESTION",
     r"\b(?:how (?:does|would) (?:this|it) (?:work|fit)|"
     r"what(?:'s| is) included|does (?:this|it) cover|"
     r"not (?:a )?good fit|outside our scope|"
     r"what (?:exactly )?do (?:we|i) get)\b",
     "CLARIFY_SCOPE_LIMITATIONS_AND_EXACT_DELIVERABLES"),
    ("INTEGRATION_OR_IMPLEMENTATION_CONCERN",
     r"\b(?:integrat(?:e|ion)|setup effort|implementation|"
     r"how (?:long|hard) (?:is|will) (?:setup|onboarding)|"
     r"switching costs?|migration|technical requirements)\b",
     "EXPLAIN_STEPS_DEPENDENCIES_AND_UNVERIFIED_ITEMS"),
    ("PRIVACY_OR_COMPLIANCE_CONCERN",
     r"\b(?:privacy|personal data|data protect(?:ion)?|gdpr|"
     r"consent|recording notice|delete (?:my|our) data|"
     r"retention policy|security review|compliance)\b",
     "REFER_TO_VERIFIED_PRIVACY_AND_SECURITY_TERMS"),
    ("ATTRIBUTION_OR_DELIVERY_CONCERN",
     r"\b(?:attribution|tracking|postback|reporting|"
     r"payable call|connected seconds?|buyer leg|"
     r"lead quality|call quality|coverage|delivery guarantees?)\b",
     "SEPARATE_TECHNICAL_REPORT_FROM_VERIFIED_DELIVERY"),
)
EXPRESSIONS: tuple[tuple[str, str], ...] = (
    ("FRUSTRATION_EXPLICITLY_EXPRESSED",
     r"\b(?:i(?:'m| am) frustrated|we(?:'re| are) frustrated|"
     r"this is frustrating|i(?:'m| am) disappointed|"
     r"we(?:'re| are) disappointed)\b"),
    ("WORRY_EXPLICITLY_EXPRESSED",
     r"\b(?:i(?:'m| am) worried|we(?:'re| are) worried|"
     r"i(?:'m| am) concerned|we(?:'re| are) concerned|"
     r"i(?:'m| am) nervous about|we(?:'re| are) nervous about)\b"),
    ("CONFUSION_EXPLICITLY_EXPRESSED",
     r"\b(?:i(?:'m| am) confused|we(?:'re| are) confused|"
     r"i don't understand|we don't understand|this is unclear)\b"),
    ("APPRECIATION_EXPLICITLY_EXPRESSED",
     r"\b(?:i appreciate|we appreciate|(?:thanks?|thank you) for (?:explaining|clarifying|"
     r"the update|your patience))\b"),
)
# More important than objection or preference detection: explicit suppression.
NO_CONTACT = re.compile(
    r"\b(?:unsubscribe|opt[ -]?out|remove me(?: from (?:your |this )?list)?|"
    r"stop (?:contacting|emailing|messaging) me|"
    r"do not (?:email|contact|message) me|"
    r"don't (?:email|contact|message) me|"
    r"never contact me again)\b", re.I,
)
REFUSAL = re.compile(
    r"\b(?:not interested|no thanks|no thank you|"
    r"we (?:do not|don't) want (?:this|your service)|"
    r"please don't follow up|please do not follow up)\b", re.I,
)
# Explicit no-problem statements are not purchase or emotional buying signals.
NO_PRICE_OBJECTION = re.compile(
    r"\b(?:no issue with (?:the )?(?:price|pricing|cost)|"
    r"(?:price|cost|pricing) is not (?:a|the) (?:problem|issue)|"
    r"(?:price|cost) isn't (?:a|the) (?:problem|issue))\b", re.I,
)
NEGATED_EMOTION = {
    "FRUSTRATION_EXPLICITLY_EXPRESSED": re.compile(
        r"\b(?:not frustrated|not disappointed)\b", re.I,
    ),
    "WORRY_EXPLICITLY_EXPRESSED": re.compile(
        r"\b(?:not (?:worried|concerned|nervous))\b", re.I,
    ),
    "CONFUSION_EXPLICITLY_EXPRESSED": re.compile(
        r"\b(?:not confused|now (?:i|we) understand)\b", re.I,
    ),
}
PRIORITY = (
    "PRIVACY_OR_COMPLIANCE_CONCERN", "TRUST_OR_PROOF_QUESTION",
    "PRICE_OR_BUDGET_QUESTION", "ATTRIBUTION_OR_DELIVERY_CONCERN",
    "SCOPE_OR_FIT_QUESTION", "INTEGRATION_OR_IMPLEMENTATION_CONCERN",
    "DECISION_AUTHORITY_QUESTION", "TIMING_OR_CAPACITY_CONCERN",
)


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "HOLD_NO_PERMITTED_CANONICAL_CURRENT_REPLY",
        "hold_reason": reason,
        "observed_objection_codes": [],
        "expressed_language_cues_not_emotion_diagnosis": [],
        "priority_response_approach_code": None,
        "suppression_escalation_required": False,
        "no_further_contact_without_new_permission": True,
        "source_owner_live_authenticated_by_this_module": False,
        "personality_profiling": False,
        "unseen_emotions_inferred": False,
        "raw_personal_message_returned": False,
        "verified_buying_intent": False,
        "model_training": False,
        "send_authorized": False,
        "crm_writes": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def review_expressed_objections(
    *, account: Mapping[str, Any], reply: Mapping[str, Any],
    as_of: datetime, processing_purpose_reviewed: bool = False,
) -> dict[str, Any]:
    """Read-only advisory, with caller-declared purpose and canonical preflight.

    Purpose and preflight flags are not source-owner attestation and cannot
    be used as an authorisation input to the original sender or CRM.
    """
    if not isinstance(as_of, datetime) or as_of.utcoffset() is None:
        raise ValueError("trusted_timezone_aware_review_clock_required")
    if type(processing_purpose_reviewed) is not bool:
        raise ValueError("explicit_boolean_review_purpose_required")
    if not isinstance(account, Mapping) or not isinstance(reply, Mapping):
        return _held("canonical_person_bound_reply_missing")
    if not processing_purpose_reviewed:
        return _held("conversation_processing_rights_not_reviewed")
    if not _preflight(account, reply):
        return _held("original_verified_person_bound_reply_preflight_missing")
    raw = reply.get("body_text")
    if type(raw) is not str or not 1 <= len(raw) <= MAX_BODY:
        return _held("bounded_current_inbound_message_required")
    body = _buyer_text(raw)
    if not body:
        return _held("current_unquoted_inbound_text_required")
    observed = reply.get("received_at")
    if type(observed) is not str:
        return _held("original_reply_received_time_missing")
    try:
        timestamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        return _held("invalid_original_reply_received_time")
    if timestamp.utcoffset() is None:
        return _held("timezone_aware_original_reply_required")
    age = as_of.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)
    if age < -timedelta(minutes=5) or age > timedelta(days=30):
        return _held("out_of_window_original_reply")
    # Quoted history and instructions embedded in the email are untrusted
    # source content. Only literal expression patterns are evaluated.
    if NO_CONTACT.search(body):
        result = _held("explicit_contact_suppression_request")
        result.update(
            status="EXPLICIT_OPT_OUT_ESCALATE_TO_ORIGINAL_SUPPRESSION_OWNER",
            suppression_escalation_required=True,
            no_further_contact_without_new_permission=True,
        )
        return result
    if REFUSAL.search(body):
        result = _held("explicit_refusal_or_no_follow_up")
        result.update(
            status="REFUSAL_REQUIRES_HUMAN_SUPPRESSION_REVIEW",
            suppression_escalation_required=True,
            no_further_contact_without_new_permission=True,
        )
        return result
    objections = []
    approaches = {}
    lowered = body.casefold()
    for code, pattern, approach in CUES:
        if re.search(pattern, lowered, re.I):
            if code == "PRICE_OR_BUDGET_QUESTION" and NO_PRICE_OBJECTION.search(body):
                continue
            objections.append(code)
            approaches[code] = approach
    expressed = [
        code for code, pattern in EXPRESSIONS
        if re.search(pattern, lowered, re.I)
        and not (code in NEGATED_EMOTION and NEGATED_EMOTION[code].search(body))
    ]
    ordered = sorted(objections, key=lambda c: PRIORITY.index(c))
    approach = approaches[ordered[0]] if ordered else (
        "ACKNOWLEDGE_EXPRESSED_CONCERN_AND_ASK_WHAT_WOULD_HELP"
        if any(c in expressed for c in (
            "FRUSTRATION_EXPLICITLY_EXPRESSED",
            "WORRY_EXPLICITLY_EXPRESSED",
            "CONFUSION_EXPLICITLY_EXPRESSED",
        )) else "NO_NEW_REPLY_SUGGESTED_FROM_CUES"
    )
    result = _held("independent_owner_proof_and_human_review_still_required")
    result.update(
        status="CURRENT_REPLY_EXPRESSED_CUES_REVIEW_ONLY",
        observed_objection_codes=ordered,
        expressed_language_cues_not_emotion_diagnosis=expressed,
        priority_response_approach_code=approach,
        # No cue may grant contact permission; original suppression/send owner
        # must independently authorise any future communication.
        no_further_contact_without_new_permission=True,
    )
    return result


def founder_conversation_cue_shadow(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Safe optional bridge projection: no transcript or individual scoring."""
    if value is None:
        return {
            "schema_version": FOUNDER_SCHEMA,
            "mode": "OBSERVE",
            "status": "NOT_CONNECTED",
            "objection_categories_observed_for_review": [],
            "self_expressed_emotion_diagnosis": False,
            "source_authenticated": False,
            "verified_buying_intent": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }
    if (type(value) is not dict or value.get("schema_version") != SCHEMA
        or value.get("execution_authority") != "none"
        or value.get("source_owner_live_authenticated_by_this_module") is not False
        or value.get("verified_buying_intent") is not False
        or value.get("personality_profiling") is not False
        or value.get("unseen_emotions_inferred") is not False
        or value.get("raw_personal_message_returned") is not False
        or value.get("send_authorized") is not False
        or value.get("crm_writes") is not False
        or value.get("outbound_sent") is not False
        or value.get("model_training") is not False):
        raise ValueError("original_conversation_objection_shadow_contract_required")
    categories = value.get("observed_objection_codes")
    valid_codes = {x[0] for x in CUES}
    if (type(categories) is not list or len(categories) > len(valid_codes)
        or any(type(c) is not str or c not in valid_codes for c in categories)
        or len(categories) != len(set(categories))):
        raise ValueError("invalid_source_objection_categories")
    status = value.get("status")
    if status not in (
        "HOLD_NO_PERMITTED_CANONICAL_CURRENT_REPLY",
        "EXPLICIT_OPT_OUT_ESCALATE_TO_ORIGINAL_SUPPRESSION_OWNER",
        "REFUSAL_REQUIRES_HUMAN_SUPPRESSION_REVIEW",
        "CURRENT_REPLY_EXPRESSED_CUES_REVIEW_ONLY",
    ):
        raise ValueError("unknown_source_objection_review_status")
    # Do not disclose private per-person emotion labels to the broad Founder
    # bridge. A specialist can review them only inside authorised case scope.
    return {
        "schema_version": FOUNDER_SCHEMA,
        "mode": "OBSERVE",
        "status": status,
        "objection_categories_observed_for_review": sorted(categories),
        "self_expressed_emotion_diagnosis": False,
        "source_authenticated": False,
        "verified_buying_intent": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }
