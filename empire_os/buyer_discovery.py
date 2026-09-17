"""OBSERVE-only real-business buyer discovery for Phase 3E.

This module ranks canonical prospects and public-site decision-maker evidence.
It performs no sending, buyer activation, CRM mutation, payment or revenue writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Mapping
from uuid import UUID
from urllib.parse import urlparse

ECONOMIC_BUYER_TERMS = (
    "founder", "co-founder", "owner", "chief executive", "ceo",
    "managing director", "president", "principal", "chief revenue", "cro",
    "chief commercial", "cco",
)
FUNCTIONAL_BUYER_TERMS = (
    "vp sales", "vice president sales", "sales director", "head of sales",
    "head of growth", "growth director", "revenue operations", "revops",
    "commercial director", "business development director",
)
WHITE_LABEL_TERMS = (
    "agency owner", "agency founder", "partnerships director",
    "managing director", "founder", "owner",
)

NON_PERSON_NAME_TERMS = {
    "membership", "pricing", "price", "guide", "award", "awards", "multiple",
    "services", "service", "contact", "team", "company", "solutions", "quote",
    "estimate", "schedule", "booking", "maintenance", "support", "office",
    "owner", "founder", "president", "principal", "manager", "director", "ceo",
    "lorem", "ipsum", "himself", "herself", "itself", "who", "what", "when",
    "where", "why", "how", "was", "were", "is", "are", "does", "did", "not",
    "after", "before", "through", "each", "very", "exceptional", "needed", "came",
    "ship", "club", "engineer",
}


@dataclass(frozen=True)
class BuyerCandidate:
    prospect_id: str
    entity_id: str | None
    business_name: str
    niche: str
    metro: str
    website: str
    phone: str
    contact_name: str
    contact_title: str
    contact_source: str
    decision_role: str
    decision_score: float
    company_score: float
    offer_key: str
    evidence: dict[str, Any]
    mode: str = "OBSERVE"
    write_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return str(value or "").strip()


def looks_like_person_name(value: Any) -> bool:
    name = _text(value)
    if not name or "@" in name or any(ch.isdigit() for ch in name):
        return False
    words = [w.strip(".,()[]{}") for w in name.split() if w.strip(".,()[]{}") ]
    if not 2 <= len(words) <= 5:
        return False
    lowered = {w.lower().strip("'\"-") for w in words}
    if lowered & NON_PERSON_NAME_TERMS:
        return False
    for word in words:
        cleaned = word.replace("'", "").replace("-", "").replace(".", "")
        if not cleaned.isalpha():
            return False
        if len(cleaned) == 1:
            if not cleaned.isupper():
                return False
            continue
        if not word[0].isupper():
            return False
    return True


def _uuid_or_none(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("canonical UUID required") from exc


def classify_decision_role(title: Any) -> tuple[str, float]:
    value = _text(title).lower()
    if not value:
        return "unknown", 0.0
    if any(term in value for term in ECONOMIC_BUYER_TERMS):
        return "economic_buyer", 1.0
    if any(term in value for term in FUNCTIONAL_BUYER_TERMS):
        return "functional_buyer", 0.8
    if "general manager" in value:
        return "functional_buyer", 0.7
    if any(term in value for term in ("director", "head", "manager")):
        return "influencer", 0.5
    return "other", 0.2


def _host(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "https://" + text)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _email_domain(value: Any) -> str:
    text = _text(value).lower()
    return text.rsplit("@", 1)[-1] if "@" in text else ""


def _bounded(value: Any, low: float = 0.0, high: float = 100.0) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def choose_offer(record: Mapping[str, Any], decision_role: str) -> str:
    niche = _text(record.get("niche")).lower()
    name = _text(record.get("business_name")).lower()
    text = f"{niche} {name} {_text(record.get('notes')).lower()}"
    if any(term in text for term in ("agency", "marketing", "seo", "advertising", "lead gen")):
        return "white_label"
    if decision_role == "economic_buyer" and any(
        term in text for term in ("software", "saas", "technology", "consulting", "finance", "recruit")
    ):
        return "high_ticket"
    if any(term in text for term in ("roof", "hvac", "plumb", "solar", "contractor", "restoration")):
        return "managed_service"
    if decision_role in {"economic_buyer", "functional_buyer"}:
        return "software_mrr"
    return "software_mrr"


def score_company(record: Mapping[str, Any], *, entity_linked: bool = False) -> float:
    score = 0.0
    if _text(record.get("business_name")): score += 10
    if _text(record.get("website")): score += 20
    if _text(record.get("phone")): score += 10
    if _text(record.get("niche")): score += 5
    if _text(record.get("metro")): score += 5
    if entity_linked: score += 15
    score += min(20.0, _bounded(record.get("buy_signal_score")) * 0.20)
    valid_person = looks_like_person_name(record.get("contact_name"))
    role, role_score = classify_decision_role(record.get("contact_title")) if valid_person else ("unknown", 0.0)
    if valid_person: score += 5
    score += role_score * 10
    return round(min(100.0, score), 2)


def build_candidate(record: Mapping[str, Any], *, entity_id: str | None = None,
                    entity_linked: bool = False) -> BuyerCandidate:
    valid_person = looks_like_person_name(record.get("contact_name"))
    role, decision_score = classify_decision_role(record.get("contact_title")) if valid_person else ("unknown", 0.0)
    score = score_company(record, entity_linked=entity_linked)
    offer = choose_offer(record, role)
    return BuyerCandidate(
        prospect_id=_text(record.get("id")),
        entity_id=_text(entity_id) or None,
        business_name=_text(record.get("business_name")),
        niche=_text(record.get("niche")),
        metro=_text(record.get("metro")),
        website=_text(record.get("website")),
        phone=_text(record.get("phone")),
        contact_name=_text(record.get("contact_name")) if valid_person else "",
        contact_title=_text(record.get("contact_title")) if valid_person else "",
        contact_source=_text(record.get("contact_source")),
        decision_role=role,
        decision_score=round(decision_score, 4),
        company_score=score,
        offer_key=offer,
        evidence={
            "buy_signal_score": _bounded(record.get("buy_signal_score")),
            "entity_linked": bool(entity_linked),
            "has_website": bool(_text(record.get("website"))),
            "has_phone": bool(_text(record.get("phone"))),
            "has_named_contact": valid_person,
            "raw_contact_name_present": bool(_text(record.get("contact_name"))),
            "contact_personhood_valid": valid_person,
        },
    )


def select_candidates(rows: Iterable[Mapping[str, Any]], *, min_score: float = 45.0,
                      limit: int = 100) -> list[BuyerCandidate]:
    if limit < 1 or limit > 10000:
        raise ValueError("limit must be between 1 and 10000")
    selected = []
    for row in rows:
        candidate = build_candidate(
            row,
            entity_id=_text(row.get("entity_id")) or None,
            entity_linked=bool(row.get("entity_id")),
        )
        if candidate.company_score >= min_score and candidate.website:
            selected.append(candidate)
    selected.sort(key=lambda c: (c.company_score, c.decision_score), reverse=True)
    return selected[:limit]


def reconcile_decision_maker(candidate: BuyerCandidate, official_people: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Reconcile canonical authority against current official-site person evidence."""
    ranked = rank_site_people(official_people)
    matches = [p for p in ranked if _text(p.get("name")).casefold() == candidate.contact_name.casefold()]
    if not candidate.contact_name or not matches:
        return {
            "status": "unconfirmed",
            "review_required": False,
            "decision_maker": None,
        }
    current = matches[0]
    conflict = float(current.get("decision_score") or 0.0) + 0.2 < float(candidate.decision_score or 0.0)
    return {
        "status": "role_conflict" if conflict else "confirmed",
        "review_required": conflict,
        "decision_maker": {**current, "source": "official_site_current"},
    }


def rank_site_people(people: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for person in people or []:
        name = _text(person.get("name"))
        title = _text(person.get("title"))
        if not looks_like_person_name(name) or not title:
            continue
        role, authority = classify_decision_role(title)
        ranked.append({
            "name": name,
            "title": title,
            "email": _text(person.get("email")),
            "url": _text(person.get("url")),
            "decision_role": role,
            "decision_score": authority,
        })
    ranked.sort(key=lambda p: p["decision_score"], reverse=True)
    return ranked


def enrich_candidate(candidate: BuyerCandidate, site_evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(site_evidence, Mapping) or site_evidence.get("ok") is not True:
        return {"candidate": candidate.to_dict(), "site_evidence": {}, "decision_maker": None,
                "contact_candidates": [], "contact_email_candidates": [],
                "mode": "OBSERVE", "write_authorized": False}
    expected_domain = _host(candidate.website)
    observed_domain = _host(site_evidence.get("domain"))
    domain_match = bool(expected_domain and observed_domain and expected_domain == observed_domain)
    raw_people = site_evidence.get("people") or []
    people = rank_site_people(raw_people) if domain_match else []
    reconciliation = (
        reconcile_decision_maker(candidate, raw_people)
        if domain_match else {"status": "unconfirmed", "review_required": False, "decision_maker": None}
    )
    named = None
    matching_person = None
    if candidate.contact_name and candidate.contact_title:
        if reconciliation.get("decision_maker"):
            named = dict(reconciliation["decision_maker"])
            matching_person = next(
                (person for person in people if _text(person.get("name")).casefold() == candidate.contact_name.casefold()),
                None,
            )
        else:
            named = {
                "name": candidate.contact_name,
                "title": candidate.contact_title,
                "decision_role": candidate.decision_role,
                "decision_score": candidate.decision_score,
                "source": candidate.contact_source or "canonical_prospect",
            }
    elif people:
        matching_person = people[0]
        named = {**matching_person, "source": "website_structured_data"}

    contacts = []
    for email in site_evidence.get("emails") or []:
        value = _text(email).lower()
        if value and domain_match and _email_domain(value) == expected_domain:
            contacts.append({"email": value, "source": "site_observed",
                             "bound_to_decision_maker": False})
    if matching_person and _text(matching_person.get("email")) and domain_match:
        value = _text(matching_person.get("email")).lower()
        if _email_domain(value) == expected_domain:
            contacts.insert(0,{"email":value,"source":"person_structured_data",
                               "bound_to_decision_maker":True})
    dedup = {}
    for item in contacts:
        email = item["email"]
        previous = dedup.get(email)
        if previous is None or item["bound_to_decision_maker"]:
            dedup[email] = item
    contacts = list(dedup.values())
    return {
        "candidate": candidate.to_dict(),
        "site_evidence": {
            "domain": _text(site_evidence.get("domain")),
            "expected_domain": expected_domain,
            "domain_match": domain_match,
            "evidence_score": site_evidence.get("evidence_score"),
            "pages_checked": site_evidence.get("pages_checked") or [],
        },
        "decision_maker": named,
        "decision_reconciliation": reconciliation,
        "contact_candidates": contacts,
        "contact_email_candidates": [item["email"] for item in contacts],
        "mode": "OBSERVE",
        "write_authorized": False,
    }


def generate_work_email_candidates(person_name: Any, company_website: Any) -> list[str]:
    """Generate deterministic work-email patterns; candidates are not verification."""
    name = _text(person_name)
    if not looks_like_person_name(name):
        return []
    host = _host(company_website)
    if not host:
        return []
    parts = [re.sub(r"[^a-z]", "", part.lower()) for part in name.replace("-", " ").replace("'", " ").split()]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return []
    first, last = parts[0], parts[-1]
    local_parts = [
        f"{first}.{last}", f"{first}{last}", f"{first[0]}{last}",
        f"{first[0]}.{last}", f"{first}{last[0]}", f"{first}.{last[0]}",
        first, last,
    ]
    return list(dict.fromkeys(f"{local}@{host}" for local in local_parts if local))


def validate_email_candidates(candidates: Iterable[str], validator: Any, *, require_smtp: bool = False) -> list[dict[str, Any]]:
    """Validate candidates while preserving the strongest evidence actually observed."""
    results = []
    for email in list(candidates)[:12]:
        outcome = validator.validate(email)
        state = "invalid"
        if getattr(outcome, "is_valid", False):
            state = "smtp_valid" if getattr(outcome, "smtp_accepts", False) else "mx_valid"
        elif getattr(outcome, "has_mx", False) and not getattr(outcome, "is_role_address", False):
            state = "mx_observed"
        if require_smtp and state != "smtp_valid":
            continue
        results.append({
            "email": email,
            "verification_state": state,
            "confidence": float(getattr(outcome, "confidence", 0.0) or 0.0),
            "has_mx": bool(getattr(outcome, "has_mx", False)),
            "smtp_accepts": bool(getattr(outcome, "smtp_accepts", False)),
            "is_role_address": bool(getattr(outcome, "is_role_address", False)),
            "is_disposable": bool(getattr(outcome, "is_disposable", False)),
            "source": "generated_pattern",
        })
    return results

def merge_generated_contact_evidence(enriched: Mapping[str, Any], validated: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    result = dict(enriched)
    contacts = [dict(item) for item in (result.get("contact_candidates") or [])]
    for item in validated or []:
        if item.get("verification_state") != "smtp_valid":
            continue
        email = _text(item.get("email")).lower()
        if not email:
            continue
        contacts.append({
            "email": email,
            "source": "generated_pattern_smtp_verified",
            "bound_to_decision_maker": True,
        })
    dedup = {}
    for item in contacts:
        email = _text(item.get("email")).lower()
        if not email:
            continue
        previous = dedup.get(email)
        if previous is None or item.get("bound_to_decision_maker"):
            dedup[email] = item
    result["contact_candidates"] = list(dedup.values())
    result["contact_email_candidates"] = list(dedup.keys())
    return result


def verify_contact_plan(enriched: Mapping[str, Any], *, validator: Any) -> dict[str, Any]:
    decision = enriched.get("decision_maker") if isinstance(enriched, Mapping) else None
    reconciliation = enriched.get("decision_reconciliation") if isinstance(enriched, Mapping) else None
    raw_contacts = list(enriched.get("contact_candidates") or []) if isinstance(enriched, Mapping) else []
    if not raw_contacts and isinstance(enriched, Mapping):
        raw_contacts = [
            {"email": email, "source": "legacy_unbound", "bound_to_decision_maker": False}
            for email in (enriched.get("contact_email_candidates") or [])
        ]
    verified = []
    for contact in raw_contacts:
        email = _text(contact.get("email")).lower()
        if not email:
            continue
        try:
            result = validator.validate(email)
        except Exception:
            continue
        verified.append({
            "email": _text(getattr(result, "email", email)).lower(),
            "is_valid": bool(getattr(result, "is_valid", False)),
            "confidence": float(getattr(result, "confidence", 0.0) or 0.0),
            "is_role_address": bool(getattr(result, "is_role_address", False)),
            "is_disposable": bool(getattr(result, "is_disposable", False)),
            "has_mx": bool(getattr(result, "has_mx", False)),
            "smtp_accepts": bool(getattr(result, "smtp_accepts", False)),
            "source": contact.get("source") or "unknown",
            "bound_to_decision_maker": bool(contact.get("bound_to_decision_maker")),
        })
    eligible = [
        item for item in verified
        if item["is_valid"] and not item["is_role_address"] and not item["is_disposable"]
        and item["bound_to_decision_maker"]
    ]
    decision_score = float((decision or {}).get("decision_score") or 0.0)
    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "decision_maker": decision,
        "verified_contacts": verified,
        "preferred_email": eligible[0]["email"] if eligible else None,
        "outreach_ready": bool(
            decision and decision_score >= 0.5 and eligible
            and not bool((reconciliation or {}).get("review_required"))
        ),
    }


def build_candidate_review_plan(candidate: BuyerCandidate, contact_plan: Mapping[str, Any], *,
                                idempotency_key: str) -> dict[str, Any]:
    if not contact_plan.get("outreach_ready"):
        raise ValueError("verified outreach-ready contact required")
    email = _text(contact_plan.get("preferred_email")).lower()
    decision = contact_plan.get("decision_maker") or {}
    name = _text(decision.get("name"))
    title = _text(decision.get("title"))
    decision_score = float(decision.get("decision_score") or candidate.decision_score or 0.0)
    idem = _text(idempotency_key)
    if not email or not looks_like_person_name(name) or not title or decision_score < 0.5:
        raise ValueError("verified decision maker required")
    if len(idem) < 8:
        raise ValueError("candidate review idempotency key required")
    evidence = {
        **candidate.evidence,
        "decision_role": decision.get("decision_role") or candidate.decision_role,
        "contact_source": decision.get("source") or candidate.contact_source,
        "verified_contacts": contact_plan.get("verified_contacts") or [],
        "source": "buyer_discovery_v2",
    }
    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "rpc": "propose_buyer_candidate_review",
        "params": {
            "p_prospect_id": _uuid_or_none(candidate.prospect_id),
            "p_entity_id": _uuid_or_none(candidate.entity_id),
            "p_contact_name": name,
            "p_contact_title": title,
            "p_contact_email": email,
            "p_offer_key": candidate.offer_key,
            "p_company_score": candidate.company_score,
            "p_decision_score": decision_score,
            "p_evidence": evidence,
            "p_idempotency_key": idem,
        },
    }


def build_reviewed_outbound_intent_plan(review_id: str, *, subject: str, body_text: str,
                                        proposed_by: str, expires_at: str,
                                        idempotency_key: str, postal_address: str,
                                        body_html: str | None = None,
                                        metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    review_uuid = _uuid_or_none(review_id)
    if not review_uuid:
        raise ValueError("approved buyer candidate review id required")
    subject_text = _text(subject)
    body = _text(body_text)
    actor = _text(proposed_by)
    postal = _text(postal_address)
    idem = _text(idempotency_key)
    if not subject_text or not body or not actor or not postal or len(idem) < 8:
        raise ValueError("complete governed outbound terms required")
    lower_body = body.lower()
    if not any(token in lower_body for token in ("unsubscribe", "opt out", "opt-out")):
        raise ValueError("outbound body requires opt-out wording")
    if postal.lower() not in lower_body:
        raise ValueError("outbound body requires configured postal address")
    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "rpc": "propose_reviewed_outbound_intent",
        "params": {
            "p_review_id": review_uuid,
            "p_subject": subject_text,
            "p_body_text": body,
            "p_body_html": body_html,
            "p_idempotency_key": idem,
            "p_proposed_by": actor,
            "p_expires_at": expires_at,
            "p_metadata": {"source": "buyer_discovery_v2", **dict(metadata or {})},
        },
    }
