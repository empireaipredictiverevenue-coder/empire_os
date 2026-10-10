"""Rapport-first outbound planning for EmpireOS.

Pure planning/gating only. This module never sends, writes canonical state,
accepts terms, moves funds, or recognizes revenue. Astra may recommend an
action, but deterministic evidence and governance decide what can be proposed.
"""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Any, Iterable, Mapping

from empire_os.outreach_message_optimizer import human_copy_gate


RELATIONSHIP_STATES = (
    "COLD_VERIFIED",
    "RAPPORT_STARTED",
    "RAPPORT_BUILDING",
    "VALUE_ESTABLISHED",
    "ENGAGED",
    "CONVERSATION",
    "COMMERCIAL_READY",
    "SUPPRESSED",
)

NEXT_ACTIONS = (
    "RESEARCH",
    "WAIT",
    "DRAFT_RAPPORT_TOUCH",
    "DRAFT_VALUE_TOUCH",
    "DRAFT_NURTURE_TOUCH",
    "DRAFT_SOFT_CONVERSATION_OPENER",
    "HANDOFF_TO_CLOSER",
    "SUPPRESS",
    "BLOCK",
)

ROLE_INBOX_PREFIXES = {
    "admin", "contact", "hello", "info", "office", "sales", "support", "team",
}

# These are status labels, not independently identified real people.
# A placeholder must never satisfy the decision-maker identity prerequisite.
UNKNOWN_PERSON_LABELS = frozenset({
    "unknown", "not known", "unverified", "tbd", "tbc", "n/a",
    "na", "none", "not identified", "not verified",
    "to be determined", "to be confirmed",
    "decision maker", "decision-maker", "owner unknown",
})

GENERIC_OPENERS = (
    "i hope this email finds you well",
    "i hope you're well",
    "i hope you are well",
    "just reaching out",
    "just following up",
    "checking in",
    "touching base",
    "circling back",
    "circle back",
    "bumping this",
)

FAKE_FAMILIARITY = (
    "as we discussed",
    "following our conversation",
    "following our chat",
    "great speaking with you",
    "great chatting with you",
    "nice speaking with you",
)

CTA_PATTERN = re.compile(
    r"(?:\?|\bbook\b|\bschedule\b|\bcalendar\b|\bdemo\b|"
    r"\bmeeting\b|\bcall\b|want me to|would you like|shall i|"
    r"can i send|happy to show|if useful[, ]+i can show)",
    flags=re.IGNORECASE,
)

SOFT_CTA_PATTERN = re.compile(
    r"(?:\bhappy to (?:show|share)\b|"
    r"\bif useful\b|\bif that's useful\b|\bif that is useful\b|"
    r"\bi can (?:show|share) you what\b|"
    r"\bif this is something\b|"
    r"\bif you're actively looking\b|\bif you are actively looking\b)",
    flags=re.IGNORECASE,
)

HARD_CTA_PATTERN = re.compile(
    r"(?:\bbook(?:ing)?\b|\bschedul(?:e|ing)\b|\bcalendar\b|"
    r"\bdemo\b|\bmeeting\b|\bappointment\b|"
    r"\bquick call\b|\bjump on (?:a )?call\b|\bhop on (?:a )?call\b|"
    r"\b(?:15|20|30|45|60)\s*(?:min|mins|minute|minutes)\b|"
    r"\bchoose (?:a )?time\b|\bpick (?:a )?time\b)",
    flags=re.IGNORECASE,
)

PRICE_PATTERN = re.compile(
    r"(?:[£$€]\s*\d|\bprice\b|\bpricing\b|\bper month\b|"
    r"\b/month\b|\bmonthly fee\b|\bimplementation fee\b)",
    flags=re.IGNORECASE,
)

COMMERCIAL_REPLY_CLASSES = {
    "positive", "question", "objection",
    "interest", "interested", "commercial",
    "pricing_question", "demo_request", "meeting_request",
}
NEGATIVE_REPLY_CLASSES = {"negative"}
LATER_REPLY_CLASSES = {"later"}
UNSUBSCRIBE_CLASSES = {"unsubscribe", "opt_out", "suppressed", "do_not_contact"}
OOO_CLASSES = {"ooo", "out_of_office", "auto_reply", "autoreply"}
WRONG_PERSON_CLASSES = {"wrong_person", "referral", "not_the_right_person"}
NON_REPLY_CLASSES = {"bounce", "delivery_status", "delivery_failure", "spam_report"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _rows(values: Iterable[Mapping[str, Any]] | None) -> tuple[Mapping[str, Any], ...]:
    return tuple(v for v in (values or ()) if isinstance(v, Mapping))


def _email_prefix(value: Any) -> str:
    email = _text(value).lower()
    if "@" not in email:
        return ""
    return email.split("@", 1)[0]


def _is_role_inbox(value: Any) -> bool:
    return _email_prefix(value) in ROLE_INBOX_PREFIXES


def _history_sent(rows: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    out = []
    for row in rows:
        event = _text(row.get("event_type") or row.get("status") or row.get("kind")).lower()
        if row.get("sent") is True or row.get("delivered") is True or event in {
            "sent", "delivered", "outbound_sent", "message_delivered",
        }:
            out.append(row)
    return tuple(out)


def _history_evidence_refs(rows: tuple[Mapping[str, Any], ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for row in rows:
        values = row.get("evidence_refs") or row.get("used_evidence_refs") or ()
        if isinstance(values, str):
            values = (values,)
        for value in values:
            ref = _text(value)
            if ref and ref not in refs:
                refs.append(ref)
    return tuple(refs)


def _value_touch_count(rows: tuple[Mapping[str, Any], ...]) -> int:
    count = 0
    for row in _history_sent(rows):
        purpose = _text(row.get("touch_purpose") or row.get("purpose")).lower()
        if purpose in {"value", "value_touch", "rapport_value", "nurture_value"}:
            count += 1
    return count


def _reply_signal(replies: tuple[Mapping[str, Any], ...]) -> str | None:
    # Map canonical reply evidence to a bounded outbound control signal.
    for row in reversed(replies):
        classification = _text(
            row.get("classification") or row.get("intent") or row.get("reply_class")
        ).lower()
        if classification in UNSUBSCRIBE_CLASSES:
            return "unsubscribe"
        if classification in OOO_CLASSES:
            return "ooo"
        if classification in WRONG_PERSON_CLASSES:
            return "wrong_person"
        if classification in NON_REPLY_CLASSES:
            continue
        if classification in COMMERCIAL_REPLY_CLASSES:
            return "commercial"
        if classification in NEGATIVE_REPLY_CLASSES:
            return "negative"
        if classification in LATER_REPLY_CLASSES:
            return "later"
        if row.get("reply_id") and row.get("real_reply") is not False:
            return "unclassified_real_reply"
    return None


def _suppressed(suppressions: tuple[Mapping[str, Any], ...]) -> bool:
    for row in suppressions:
        if row.get("suppressed") is True:
            return True
        state = _text(row.get("status") or row.get("state") or row.get("reason")).lower()
        if state in {"suppressed", "unsubscribe", "opt_out", "do_not_contact"}:
            return True
    return False


def _evidence_ref(row: Mapping[str, Any]) -> str:
    return _text(
        row.get("evidence_ref")
        or row.get("ref")
        or row.get("source_ref")
        or row.get("id")
    )


def _evidence_summary(row: Mapping[str, Any]) -> str:
    return _text(
        row.get("summary")
        or row.get("observation")
        or row.get("claim")
        or row.get("text")
    )


def _is_verified(row: Mapping[str, Any]) -> bool:
    if row.get("verified") is True:
        return True
    value = _text(
        row.get("verification_state")
        or row.get("evidence_class")
        or row.get("status")
    ).lower()
    return value in {"verified", "observed", "first_party_verified"}


def _is_fresh(row: Mapping[str, Any]) -> bool:
    if row.get("fresh") is True:
        return True
    value = _text(row.get("freshness") or row.get("freshness_state")).lower()
    return value in {"fresh", "current"}


def _is_account_bound(row: Mapping[str, Any], account: Mapping[str, Any]) -> bool:
    if row.get("account_bound") is True:
        return True
    prospect_id = _text(account.get("prospect_id"))
    if prospect_id and _text(row.get("prospect_id")) == prospect_id:
        return True
    company = _text(account.get("company_name")).casefold()
    return bool(company and _text(row.get("company_name")).casefold() == company)


def _usable_evidence(
    evidence: tuple[Mapping[str, Any], ...],
    account: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows = []
    for row in evidence:
        if row.get("contradicted") is True:
            continue
        if _text(row.get("verification_state")).lower() == "contradicted":
            continue
        if not _evidence_ref(row) or not _evidence_summary(row):
            continue
        if not _is_verified(row) or not _is_fresh(row):
            continue
        if not _is_account_bound(row, account):
            continue
        rows.append(row)
    rows.sort(key=lambda r: _evidence_ref(r))
    return tuple(rows)


def _base_missing(account: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if not _text(account.get("company_name")):
        missing.append("company_name")
    if account.get("company_name_verified") is not True:
        missing.append("verified_company_name")
    if not _text(account.get("contact_route")):
        missing.append("contact_route")
    decision_maker = _text(account.get("decision_maker"))
    if not decision_maker or decision_maker.casefold() in UNKNOWN_PERSON_LABELS:
        missing.append("decision_maker")
    review_state = _text(account.get("buyer_review_status")).lower()
    if review_state not in {"pending", "approved", "review_ready"} and account.get("verified_prospect") is not True:
        missing.append("verified_buyer_review")
    return missing


def derive_relationship_state(
    account: Mapping[str, Any],
    *,
    history: Iterable[Mapping[str, Any]] = (),
    replies: Iterable[Mapping[str, Any]] = (),
    suppressions: Iterable[Mapping[str, Any]] = (),
) -> str:
    h = _rows(history)
    r = _rows(replies)
    s = _rows(suppressions)

    if _suppressed(s) or _reply_signal(r) == "unsubscribe":
        return "SUPPRESSED"
    if account.get("commercial_ready") is True:
        return "COMMERCIAL_READY"
    reply_signal = _reply_signal(r)
    if reply_signal == "commercial":
        return "CONVERSATION"
    if reply_signal in {"negative", "later", "unclassified_real_reply"}:
        return "ENGAGED"

    sent = _history_sent(h)
    if len(sent) >= 3 and _value_touch_count(h) >= 2:
        return "VALUE_ESTABLISHED"
    if len(sent) >= 2:
        return "RAPPORT_BUILDING"
    if len(sent) == 1:
        return "RAPPORT_STARTED"
    return "COLD_VERIFIED"


def _strategy_id(
    account: Mapping[str, Any],
    stage: str,
    action: str,
    evidence_refs: tuple[str, ...],
) -> str:
    raw = "|".join(
        (
            _text(account.get("prospect_id") or account.get("company_name")),
            stage,
            action,
            ",".join(evidence_refs),
        )
    )
    return "outbound-" + sha256(raw.encode("utf-8")).hexdigest()[:16]


def _result(
    *,
    account: Mapping[str, Any],
    stage: str,
    action: str,
    reason: str,
    touch_number: int,
    evidence_refs: tuple[str, ...] = (),
    used_evidence_refs: tuple[str, ...] = (),
    missing_evidence: tuple[str, ...] = (),
    astra_recommendation: str | None = None,
) -> dict[str, Any]:
    contact_route = _text(account.get("contact_route"))
    person_bound = bool(account.get("person_bound"))
    if contact_route == "company_routed":
        person_bound = False

    touch_purpose = {
        "DRAFT_RAPPORT_TOUCH": "rapport",
        "DRAFT_VALUE_TOUCH": "value",
        "DRAFT_NURTURE_TOUCH": "nurture_value",
        "DRAFT_SOFT_CONVERSATION_OPENER": "soft_conversation_opener",
        "HANDOFF_TO_CLOSER": "conversation_handoff",
        "RESEARCH": "research",
        "WAIT": "wait",
        "SUPPRESS": "suppress",
        "BLOCK": "block",
    }.get(action, "unknown")

    cta_allowed = action == "DRAFT_SOFT_CONVERSATION_OPENER" and stage == "VALUE_ESTABLISHED"
    price_allowed = stage == "COMMERCIAL_READY"

    recommended = _text(astra_recommendation).upper() or None
    return {
        "schema_version": "empire.outbound_department.plan.v1",
        "department_key": "outbound",
        "prospect_id": _text(account.get("prospect_id")) or None,
        "review_id": _text(account.get("review_id")) or None,
        "company_name": _text(account.get("company_name")) or None,
        "relationship_stage": stage,
        "action_type": action,
        "reason": reason,
        "evidence_refs": list(evidence_refs),
        "used_evidence_refs": list(used_evidence_refs),
        "missing_evidence": list(missing_evidence),
        "contact_route": contact_route or None,
        "person_bound": person_bound,
        "touch_number": touch_number,
        "touch_purpose": touch_purpose,
        "strategy_id": _strategy_id(account, stage, action, evidence_refs),
        "cta_allowed": cta_allowed,
        "price_allowed": price_allowed,
        "automated_nurture_allowed": False,
        "deliverability_check_required": action.startswith("DRAFT_"),
        "authority_required": "governed_external",
        "execution_authority": "none",
        "commercial_terms_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "astra_director": {
            "proposed_action": recommended,
            "effective_action": action,
            "recommendation_accepted": bool(recommended and recommended == action),
            "can_grant_send_authority": False,
            "can_expand_authority": False,
        },
        "draft_policy": {
            "full_verified_company_name_required_early": touch_number <= 3,
            "no_ai_slop": True,
            "one_primary_evidence_angle": True,
            "first_touch_cta_allowed": False,
            "company_routed_is_person_bound": False,
            "reply_stops_nurture": True,
        },
    }


def plan_outbound_account(
    account: Mapping[str, Any],
    *,
    history: Iterable[Mapping[str, Any]] = (),
    evidence: Iterable[Mapping[str, Any]] = (),
    replies: Iterable[Mapping[str, Any]] = (),
    suppressions: Iterable[Mapping[str, Any]] = (),
    now: Any = None,
    astra_recommendation: str | None = None,
) -> dict[str, Any]:
    """Return the next permitted outbound proposal. Never executes it."""
    del now  # reserved for a future canonical freshness adapter; no wall-clock inference

    h = _rows(history)
    r = _rows(replies)
    s = _rows(suppressions)
    sent = _history_sent(h)
    touch_number = len(sent) + 1
    used_refs = _history_evidence_refs(h)

    base_missing = _base_missing(account)
    contact_route = _text(account.get("contact_route")).lower()
    person_bound = bool(account.get("person_bound"))
    role_inbox = _is_role_inbox(account.get("contact_email"))

    if contact_route == "company_routed" and person_bound:
        return _result(
            account=account,
            stage="COLD_VERIFIED",
            action="BLOCK",
            reason="company_routed_contact_cannot_be_person_bound",
            touch_number=touch_number,
            used_evidence_refs=used_refs,
            missing_evidence=("contact_route_personhood_conflict",),
            astra_recommendation=astra_recommendation,
        )
    if role_inbox and person_bound:
        return _result(
            account=account,
            stage="COLD_VERIFIED",
            action="BLOCK",
            reason="role_inbox_cannot_be_person_bound",
            touch_number=touch_number,
            used_evidence_refs=used_refs,
            missing_evidence=("role_inbox_personhood_conflict",),
            astra_recommendation=astra_recommendation,
        )

    signal = _reply_signal(r)
    if _suppressed(s) or signal == "unsubscribe":
        return _result(
            account=account, stage="SUPPRESSED", action="SUPPRESS",
            reason="suppression_or_unsubscribe_outweighs_nurture",
            touch_number=touch_number, used_evidence_refs=used_refs,
            astra_recommendation=astra_recommendation,
        )
    if signal == "ooo":
        stage = derive_relationship_state(account, history=h, replies=(), suppressions=s)
        return _result(
            account=account, stage=stage, action="WAIT",
            reason="out_of_office_reply_requires_wait_not_sales_escalation",
            touch_number=touch_number, used_evidence_refs=used_refs,
            astra_recommendation=astra_recommendation,
        )
    if signal == "wrong_person":
        stage = derive_relationship_state(account, history=h, replies=(), suppressions=s)
        return _result(
            account=account, stage=stage, action="RESEARCH",
            reason="wrong_person_or_referral_requires_identity_research",
            touch_number=touch_number, used_evidence_refs=used_refs,
            missing_evidence=("correct_contact_route",),
            astra_recommendation=astra_recommendation,
        )
    if signal == "commercial":
        return _result(
            account=account, stage="CONVERSATION", action="HANDOFF_TO_CLOSER",
            reason="commercial_reply_stops_nurture_and_hands_context_to_existing_closer",
            touch_number=touch_number, used_evidence_refs=used_refs,
            astra_recommendation=astra_recommendation,
        )
    if signal == "later":
        return _result(
            account=account, stage="ENGAGED", action="WAIT",
            reason="later_reply_stops_nurture_until_new_observed_timing_evidence",
            touch_number=touch_number, used_evidence_refs=used_refs,
            astra_recommendation=astra_recommendation,
        )
    if signal == "negative":
        return _result(
            account=account, stage="ENGAGED", action="WAIT",
            reason="negative_reply_stops_nurture_without_inventing_closer_work",
            touch_number=touch_number, used_evidence_refs=used_refs,
            astra_recommendation=astra_recommendation,
        )
    if signal == "unclassified_real_reply":
        return _result(
            account=account, stage="ENGAGED", action="WAIT",
            reason="real_reply_stops_nurture_until_canonical_reply_classification_is_available",
            touch_number=touch_number, used_evidence_refs=used_refs,
            missing_evidence=("reply_classification_review",),
            astra_recommendation=astra_recommendation,
        )

    if _text(account.get("buyer_review_status")).lower() in {"rejected", "blocked"}:
        return _result(
            account=account, stage="COLD_VERIFIED", action="BLOCK",
            reason="buyer_review_blocks_outbound_progression",
            touch_number=touch_number, used_evidence_refs=used_refs,
            missing_evidence=("buyer_review_not_eligible",),
            astra_recommendation=astra_recommendation,
        )

    if base_missing:
        return _result(
            account=account, stage="COLD_VERIFIED", action="RESEARCH",
            reason="verified_account_or_contact_evidence_missing",
            touch_number=touch_number, used_evidence_refs=used_refs,
            missing_evidence=tuple(base_missing),
            astra_recommendation=astra_recommendation,
        )

    usable = _usable_evidence(_rows(evidence), account)
    fresh_new = tuple(row for row in usable if _evidence_ref(row) not in set(used_refs))
    if not fresh_new:
        return _result(
            account=account,
            stage=derive_relationship_state(account, history=h, replies=r, suppressions=s),
            action="RESEARCH",
            reason="new_account_bound_verified_evidence_required_before_next_touch",
            touch_number=touch_number,
            used_evidence_refs=used_refs,
            missing_evidence=("fresh_unused_account_evidence",),
            astra_recommendation=astra_recommendation,
        )

    stage = derive_relationship_state(account, history=h, replies=r, suppressions=s)
    selected = (_evidence_ref(fresh_new[0]),)

    if stage == "COMMERCIAL_READY":
        action = "HANDOFF_TO_CLOSER"
        reason = "canonical_commercial_ready_state_requires_existing_closer"
    elif stage == "VALUE_ESTABLISHED":
        action = "DRAFT_SOFT_CONVERSATION_OPENER"
        reason = "sufficient_prior_value_touches_allow_a_soft_conversation_opener"
    elif stage == "RAPPORT_BUILDING":
        action = "DRAFT_NURTURE_TOUCH"
        reason = "rapport_is_building_and_next_touch_must_add_new_value"
    elif stage == "RAPPORT_STARTED":
        action = "DRAFT_VALUE_TOUCH"
        reason = "first_touch_exists_and_next_touch_must_add_new_value"
    else:
        action = "DRAFT_RAPPORT_TOUCH"
        reason = "verified_cold_account_with_fresh_evidence_requires_rapport_first"

    return _result(
        account=account,
        stage=stage,
        action=action,
        reason=reason,
        touch_number=touch_number,
        evidence_refs=selected,
        used_evidence_refs=used_refs,
        astra_recommendation=astra_recommendation,
    )


def _uses_unverified_company_shortening(
    body: str,
    *,
    full_company: str,
    verified_short_names: tuple[str, ...],
) -> bool:
    # Reject an unverified brand shortening while allowing natural pronouns later.
    lower = body.casefold()
    if not full_company or full_company.casefold() in lower:
        return False
    if any(name.casefold() in lower for name in verified_short_names):
        return False

    words = re.findall(r"[A-Za-z0-9&'-]+", full_company)
    if not words:
        return False
    candidates: list[str] = []
    if words[0].casefold() not in {"the", "a", "an"}:
        candidates.append(words[0])
    if len(words) >= 2:
        candidates.append(" ".join(words[:2]))

    for candidate in sorted(set(candidates), key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", body, flags=re.IGNORECASE):
            return True
    return False


def review_outbound_draft(
    *,
    account: Mapping[str, Any],
    plan: Mapping[str, Any],
    subject: str,
    body: str,
    used_evidence_refs: Iterable[str] = (),
) -> dict[str, Any]:
    """Hard fail-close copy review for a drafted touch."""
    clean_subject = _text(subject)
    clean_body = _text(body)
    lower = clean_body.casefold()
    blockers: list[str] = []

    base_gate = human_copy_gate(subject=clean_subject, body=clean_body)
    for issue in base_gate.get("blockers") or ():
        if issue in {
            "ai_slop_pattern", "vendor_or_ai_sounding_language",
            "brand_monologue", "salesy_exclamation",
        }:
            blockers.append("AI_SLOP_PHRASE")
        else:
            blockers.append("UNSUPPORTED_CLAIM")

    if any(lower.startswith(opener) for opener in GENERIC_OPENERS):
        blockers.append("GENERIC_OPENER")

    stage = _text(plan.get("relationship_stage"))
    if stage not in {"CONVERSATION", "COMMERCIAL_READY"} and any(
        phrase in lower for phrase in FAKE_FAMILIARITY
    ):
        blockers.append("FAKE_FAMILIARITY")

    refs = tuple(dict.fromkeys(_text(v) for v in used_evidence_refs if _text(v)))
    allowed_refs = {_text(v) for v in (plan.get("evidence_refs") or ()) if _text(v)}
    prior_refs = {_text(v) for v in (plan.get("used_evidence_refs") or ()) if _text(v)}

    if not refs:
        blockers.append("EMPTY_PERSONALIZATION")
    if refs and not set(refs).issubset(allowed_refs):
        blockers.append("UNSUPPORTED_CLAIM")
    if refs and set(refs).issubset(prior_refs):
        blockers.append("REPEATED_INSIGHT")

    full_company = _text(account.get("company_name"))
    touch_number = int(plan.get("touch_number") or 1)
    full_name_present = bool(full_company and full_company.casefold() in lower)
    verified_short_names = tuple(
        _text(v) for v in (account.get("verified_company_short_names") or ()) if _text(v)
    )
    verified_short_present = any(v.casefold() in lower for v in verified_short_names)

    if touch_number <= 3 and not full_name_present:
        blockers.append("UNVERIFIED_COMPANY_SHORTENING")
    elif touch_number > 3 and _uses_unverified_company_shortening(
        clean_body,
        full_company=full_company,
        verified_short_names=verified_short_names,
    ):
        blockers.append("UNVERIFIED_COMPANY_SHORTENING")

    if touch_number <= 3 and full_company and not full_name_present:
        blockers.append("EMPTY_PERSONALIZATION")

    contact_route = _text(plan.get("contact_route") or account.get("contact_route")).lower()
    person_bound = bool(plan.get("person_bound"))
    decision_maker = _text(account.get("decision_maker"))
    first_name = decision_maker.split()[0] if decision_maker else ""
    if contact_route == "company_routed" and not person_bound and first_name:
        personal_greeting = re.search(
            rf"(?im)^\s*(?:hi|hello|hey)?\s*{re.escape(first_name)}\s*[,!-]",
            clean_body,
        )
        if personal_greeting or "your email" in lower:
            blockers.append("ROLE_INBOX_PERSONHOOD_CLAIM")

    cta_allowed = bool(plan.get("cta_allowed"))
    action_type = _text(plan.get("action_type"))
    has_soft_cta = SOFT_CTA_PATTERN.search(clean_body) is not None
    has_hard_cta = HARD_CTA_PATTERN.search(clean_body) is not None
    has_cta = (
        CTA_PATTERN.search(clean_body) is not None
        or has_soft_cta
        or has_hard_cta
    )

    if has_hard_cta:
        blockers.append("PREMATURE_CTA")
    elif has_cta and not cta_allowed:
        blockers.append("PREMATURE_CTA")
    elif (
        has_cta
        and action_type == "DRAFT_SOFT_CONVERSATION_OPENER"
        and not has_soft_cta
    ):
        blockers.append("PREMATURE_CTA")

    price_allowed = bool(plan.get("price_allowed"))
    if not price_allowed and PRICE_PATTERN.search(clean_body):
        blockers.append("PREMATURE_PRICE")

    if not clean_body or len(clean_body.split()) < 8:
        blockers.append("EMPTY_PERSONALIZATION")

    blockers = list(dict.fromkeys(blockers))
    return {
        "schema_version": "empire.outbound_department.copy_review.v1",
        "eligible": not blockers,
        "blockers": blockers,
        "policy": "rapport_first_human_specific_v1",
        "relationship_stage": stage or None,
        "touch_number": touch_number,
        "used_evidence_refs": list(refs),
        "full_verified_company_name_present": full_name_present,
        "contact_route": contact_route or None,
        "person_bound": person_bound,
        "execution_authority": "none",
        "send_enabled": False,
    }
