"""OBSERVE-only real-business buyer discovery for Phase 3E.

This module ranks canonical prospects and public-site decision-maker evidence.
It performs no sending, buyer activation, CRM mutation, payment or revenue writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
import re
from typing import Any, Iterable, Mapping
from uuid import UUID
from urllib.parse import urlparse

from empire_os.buyer_allocation import buyer_activation_decision
from empire_os.locale_intelligence import resolve_locale
from empire_os.market_pricing import (
    infer_country_code,
    market_price,
)
from empire_os.search_fabric.verification import is_directory_url

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
    "ship", "club", "engineer", "your", "referral", "program", "email",
    "learn", "more", "strategic", "operations", "leadership", "about",
    "read", "meet", "turnpoint", "thats", "that's",
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
    final_word = (
        words[-1]
        .replace("'", "")
        .replace("-", "")
        .replace(".", "")
    )
    if len(final_word) < 2:
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


def _title_has(value: str, term: str) -> bool:
    return bool(
        re.search(
            rf"(?<!\w){re.escape(term.lower())}(?!\w)",
            value,
        )
    )


def classify_decision_role(title: Any) -> tuple[str, float]:
    value = _text(title).lower()
    if not value:
        return "unknown", 0.0

    # "Vice President" must be classified before the bare "president"
    # economic-buyer term. Substring matching otherwise overstates VP
    # authority and can incorrectly promote functional leaders.
    if "vice president" in value or re.search(r"\bvp\b", value):
        functional_remits = (
            "sales", "revenue", "growth", "marketing",
            "business development", "corporate development",
            "operations", "analytics", "strategy", "technology",
            "data", " ai", "transformation", "commercial",
        )
        if any(_title_has(value, term) for term in functional_remits):
            return "functional_buyer", 0.8
        return "influencer", 0.6

    if any(_title_has(value, term) for term in ECONOMIC_BUYER_TERMS):
        return "economic_buyer", 1.0

    functional_c_suite_phrases = (
        "chief strategy",
        "chief marketing",
        "chief technology",
        "chief information",
        "chief data",
        "chief ai",
        "chief artificial intelligence",
        "chief digital",
        "chief transformation",
        "chief operating",
    )
    functional_c_suite_acronyms = (
        "coo",
        "cto",
        "cmo",
        "cio",
        "cdo",
    )
    if (
        any(_title_has(value, term) for term in functional_c_suite_phrases)
        or any(
            re.search(rf"\b{re.escape(term)}\b", value)
            for term in functional_c_suite_acronyms
        )
    ):
        return "functional_buyer", 0.8

    if any(_title_has(value, term) for term in FUNCTIONAL_BUYER_TERMS):
        return "functional_buyer", 0.8
    if _title_has(value, "general manager"):
        return "functional_buyer", 0.7
    if any(_title_has(value, term) for term in ("director", "head", "manager")):
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


_COMPANY_ROUTING_PREFIXES = {
    "info", "contact", "hello", "office", "reception",
    "enquiries", "enquiry", "sales", "team", "general",
    "support", "customerservice", "customer.service", "mail",
}


def _is_company_routing_email(value: Any) -> bool:
    text = _text(value).lower()
    if "@" not in text:
        return False
    local, domain = text.rsplit("@", 1)
    return (
        local in _COMPANY_ROUTING_PREFIXES
        and bool(domain)
        and "." in domain
    )


def _publication_is_recent(value: Any, *, max_age_days: int = 730) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        published = datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            published = date.fromisoformat(text[:10])
        except ValueError:
            return False
    age = (date.today() - published).days
    return 0 <= age <= max_age_days


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
    if "solar" in niche:
        country_code = infer_country_code(
            country_code=record.get("country_code"),
            source=record.get("_acquisition_source"),
            metro=record.get("metro"),
            address=record.get("address"),
        )
        if country_code:
            try:
                return market_price(country_code).product_code
            except KeyError:
                pass
        return "solar_opportunity_map"
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


def _first_party_website(value: Any) -> str:
    website = _text(value)
    if not website or is_directory_url(website):
        return ""
    return website


def accepted_acquisition_website(evidence: Any) -> str:
    if not isinstance(evidence, Mapping):
        return ""
    quality = evidence.get("quality")
    if not isinstance(quality, Mapping):
        return ""
    if quality.get("accepted") is not True:
        return ""
    if _text(quality.get("source_role")) != "identity_or_direct":
        return ""

    raw = evidence.get("raw")
    if not isinstance(raw, Mapping):
        return ""

    website = _first_party_website(raw.get("business_website"))
    if website:
        return website

    tags = raw.get("osm_tags")
    if isinstance(tags, Mapping):
        return _first_party_website(tags.get("website"))
    return ""


def _candidate_website(record: Mapping[str, Any]) -> tuple[str, str]:
    canonical = _first_party_website(record.get("website"))
    if canonical:
        return canonical, "canonical_prospect"

    acquired = accepted_acquisition_website(
        record.get("_acquisition_evidence")
    )
    if acquired:
        return acquired, "accepted_acquisition"

    return "", ""


def score_company(record: Mapping[str, Any], *, entity_linked: bool = False) -> float:
    score = 0.0
    if _text(record.get("business_name")): score += 10
    if _candidate_website(record)[0]: score += 20
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
    raw_website = _text(record.get("website"))
    first_party_website, website_source = _candidate_website(record)
    acquisition_evidence = record.get("_acquisition_evidence")
    acquisition_evidence = (
        acquisition_evidence
        if isinstance(acquisition_evidence, Mapping)
        else {}
    )
    existing_locale = acquisition_evidence.get("locale")
    locale_input = (
        dict(existing_locale)
        if isinstance(existing_locale, Mapping)
        else {}
    )
    locale_input.setdefault("metro", _text(record.get("metro")))
    locale_input.setdefault(
        "state",
        _text(record.get("state") or acquisition_evidence.get("state")),
    )
    locale = resolve_locale(locale_input)
    return BuyerCandidate(
        prospect_id=_text(record.get("id")),
        entity_id=_text(entity_id) or None,
        business_name=_text(record.get("business_name")),
        niche=_text(record.get("niche")),
        metro=_text(record.get("metro")),
        website=first_party_website,
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
            "has_website": bool(first_party_website),
            "website_source": website_source or None,
            "directory_website_rejected": bool(
                raw_website and is_directory_url(raw_website)
            ),
            "acquisition_website_accepted": bool(
                website_source == "accepted_acquisition"
            ),
            "has_phone": bool(_text(record.get("phone"))),
            "has_named_contact": valid_person,
            "raw_contact_name_present": bool(_text(record.get("contact_name"))),
            "contact_personhood_valid": valid_person,
            "locale": locale.as_dict(),
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
    if not candidate.website or is_directory_url(candidate.website):
        return {"candidate": candidate.to_dict(), "site_evidence": {}, "decision_maker": None,
                "contact_candidates": [], "contact_email_candidates": [],
                "mode": "OBSERVE", "write_authorized": False}
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
    decision_first = ""
    if named and looks_like_person_name(named.get("name")):
        decision_first = re.sub(r"[^a-z]", "", _text(named.get("name")).split()[0].lower())
    for email in site_evidence.get("emails") or []:
        value = _text(email).lower()
        if value and domain_match and _email_domain(value) == expected_domain:
            local = value.split("@", 1)[0]
            first_name_match = bool(
                decision_first and local == decision_first and local not in {"info", "contact", "sales", "hello", "support"}
            )
            contacts.append({
                "email": value,
                "source": "site_observed_first_name_match" if first_name_match else "site_observed",
                "bound_to_decision_maker": first_name_match,
            })
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
    website = _first_party_website(company_website)
    host = _host(website)
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

def merge_public_decision_maker_evidence(
    enriched: Mapping[str, Any],
    evidence: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Accept a public decision maker only with first-party or corroborated evidence."""
    result = dict(enriched)
    allowed_sources = {
        "official_site",
        "public_business_directory",
        "public_government_record",
        "company_press_release",
        "professional_profile",
    }
    candidates: list[dict[str, Any]] = []

    for item in evidence or []:
        if not isinstance(item, Mapping):
            continue
        name = _text(item.get("name"))
        title = _text(item.get("title"))
        source_url = _text(item.get("source_url"))
        source_kind = _text(item.get("source_kind")).lower()
        if (
            not looks_like_person_name(name)
            or not title
            or not source_url
            or source_kind not in allowed_sources
        ):
            continue

        identity_correlated = (
            source_kind == "official_site"
            or item.get("business_identity_correlated") is True
        )
        if not identity_correlated:
            continue

        role, decision_score = classify_decision_role(title)
        if decision_score < 0.5:
            continue

        published_at = _text(item.get("published_at"))
        if (
            source_kind in {
                "public_government_record",
                "company_press_release",
            }
            and not _publication_is_recent(published_at)
        ):
            continue

        candidates.append({
            "name": name,
            "title": title,
            "decision_role": role,
            "decision_score": decision_score,
            "source_kind": source_kind,
            "source_url": source_url,
            "source_domain": _host(source_url),
            "published_at": published_at,
            "business_identity_correlated": identity_correlated,
        })

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        grouped.setdefault(item["name"].casefold(), []).append(item)

    corroborated_groups: list[list[dict[str, Any]]] = []
    for items in grouped.values():
        official = [
            item for item in items
            if item["source_kind"] == "official_site"
        ]
        domains = {
            item["source_domain"]
            for item in items
            if item["source_domain"]
        }
        economic = [
            item for item in items
            if item["decision_role"] == "economic_buyer"
        ]
        functional = [
            item for item in items
            if item["decision_role"] == "functional_buyer"
        ]

        corroborated = (
            bool(official)
            or (
                len(domains) >= 2
                and (len(economic) >= 2 or len(functional) >= 2)
            )
        )
        if not corroborated:
            continue

        corroborated_groups.append(sorted(
            items,
            key=lambda item: (
                item["decision_score"],
                item["source_kind"] == "official_site",
            ),
            reverse=True,
        ))

    if not corroborated_groups:
        result["public_decision_maker_evidence_accepted"] = 0
        return result

    if len(corroborated_groups) != 1:
        result["decision_reconciliation"] = {
            "status": "ambiguous_public_identity",
            "review_required": True,
            "decision_maker": result.get("decision_maker"),
        }
        result["public_decision_maker_evidence_accepted"] = 0
        return result

    accepted_evidence = corroborated_groups[0]
    accepted = accepted_evidence[0]

    existing = result.get("decision_maker")
    if isinstance(existing, Mapping) and _text(existing.get("name")):
        existing_name = _text(existing.get("name"))
        if existing_name.casefold() != accepted["name"].casefold():
            result["decision_reconciliation"] = {
                "status": "identity_conflict",
                "review_required": True,
                "decision_maker": dict(existing),
                "public_candidate": accepted,
            }
            result["public_decision_maker_evidence_accepted"] = 0
            return result

    result["decision_maker"] = {
        "name": accepted["name"],
        "title": accepted["title"],
        "decision_role": accepted["decision_role"],
        "decision_score": accepted["decision_score"],
        "source": "public_web_corroborated",
    }
    result["decision_reconciliation"] = {
        "status": "public_corroborated",
        "review_required": False,
        "decision_maker": result["decision_maker"],
    }
    result["public_decision_maker_evidence"] = accepted_evidence
    result["public_decision_maker_evidence_accepted"] = len(
        accepted_evidence
    )
    return result


def merge_public_web_contact_evidence(
    enriched: Mapping[str, Any], evidence: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Bind explicit public-web contacts only with identity and role corroboration."""
    result = dict(enriched)
    decision = result.get("decision_maker") or {}
    decision_name = _text(decision.get("name"))
    contacts = [dict(item) for item in (result.get("contact_candidates") or [])]
    accepted = []
    for item in evidence or []:
        name = _text(item.get("name"))
        email = _text(item.get("email")).lower()
        source_url = _text(item.get("source_url"))
        source_kind = _text(item.get("source_kind")).lower()
        if not decision_name or name.casefold() != decision_name.casefold():
            continue
        if not email or "@" not in email or not source_url:
            continue
        allowed_sources = {
            "official_site", "public_business_directory",
            "public_government_record", "company_press_release",
        }
        if source_kind not in allowed_sources:
            continue
        role_corroborated = bool(item.get("role_corroborated"))
        published_at = _text(item.get("published_at"))
        if source_kind != "official_site" and not role_corroborated:
            continue
        if source_kind in {"public_government_record", "company_press_release"} and not _publication_is_recent(published_at):
            continue
        accepted.append({
            "email": email,
            "source": source_kind,
            "bound_to_decision_maker": True,
            "source_url": source_url,
            "role_corroborated": role_corroborated,
            "direct_publication": bool(item.get("direct_publication", True)),
            "published_at": published_at,
        })
    contacts.extend(accepted)
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
    result["public_web_evidence_accepted"] = len(accepted)
    return result


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
            "verification_state": "smtp_valid",
            "smtp_accepts": True,
            "has_mx": bool(item.get("has_mx", True)),
            "confidence": float(item.get("confidence", 0.95) or 0.95),
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


def verify_contact_plan(
    enriched: Mapping[str, Any],
    *,
    validator: Any,
    allow_company_routed: bool = False,
) -> dict[str, Any]:
    decision = enriched.get("decision_maker") if isinstance(enriched, Mapping) else None
    reconciliation = enriched.get("decision_reconciliation") if isinstance(enriched, Mapping) else None
    raw_contacts = list(enriched.get("contact_candidates") or []) if isinstance(enriched, Mapping) else []
    if not raw_contacts and isinstance(enriched, Mapping):
        raw_contacts = [
            {"email": email, "source": "legacy_unbound", "bound_to_decision_maker": False}
            for email in (enriched.get("contact_email_candidates") or [])
        ]

    site_evidence = (
        enriched.get("site_evidence")
        if isinstance(enriched, Mapping)
        else None
    )
    site_domain_match = bool(
        isinstance(site_evidence, Mapping)
        and site_evidence.get("domain_match") is True
    )

    verified = []
    for contact in raw_contacts:
        email = _text(contact.get("email")).lower()
        if not email:
            continue
        try:
            result = validator.validate(email)
        except Exception:
            continue
        prior_smtp = bool(
            contact.get("smtp_accepts") is True
            and contact.get("verification_state") == "smtp_valid"
        )
        verified.append({
            "email": _text(getattr(result, "email", email)).lower(),
            "is_valid": bool(
                getattr(result, "is_valid", False) or prior_smtp
            ),
            "confidence": max(
                float(getattr(result, "confidence", 0.0) or 0.0),
                float(contact.get("confidence", 0.0) or 0.0),
            ),
            "is_role_address": bool(getattr(result, "is_role_address", False)),
            "is_disposable": bool(getattr(result, "is_disposable", False)),
            "has_mx": bool(
                getattr(result, "has_mx", False)
                or contact.get("has_mx") is True
            ),
            "smtp_accepts": bool(
                getattr(result, "smtp_accepts", False) or prior_smtp
            ),
            "source": contact.get("source") or "unknown",
            "bound_to_decision_maker": bool(contact.get("bound_to_decision_maker")),
        })

    person_bound_eligible = [
        item for item in verified
        if item["is_valid"]
        and not item["is_role_address"]
        and not item["is_disposable"]
        and item["bound_to_decision_maker"]
    ]
    strong_public_sources = {
        "person_structured_data", "official_site",
        "public_government_record", "company_press_release",
    }
    person_bound_outreach = [
        item for item in person_bound_eligible
        if item["smtp_accepts"] or item["source"] in strong_public_sources
    ]

    decision_score = float((decision or {}).get("decision_score") or 0.0)
    decision_role = _text((decision or {}).get("decision_role"))
    if not decision_role and decision:
        decision_role, _ = classify_decision_role(
            (decision or {}).get("title")
        )
    reconciliation_clear = not bool((reconciliation or {}).get("review_required"))

    # A company-routed address is not person-bound. It may only be used when
    # explicitly enabled by the caller, the verified decision maker is an
    # economic buyer, and the role inbox was directly observed on the matched
    # first-party domain. This preserves the distinction between "email belongs
    # to the buyer" and "company inbox can route a message to the buyer".
    company_routed_eligible = []
    if (
        allow_company_routed
        and decision
        and decision_role == "economic_buyer"
        and decision_score >= 0.70
        and reconciliation_clear
        and site_domain_match
    ):
        company_routed_eligible = [
            item for item in verified
            if (
                item["is_role_address"]
                or _is_company_routing_email(item["email"])
            )
            and not item["is_disposable"]
            and item["source"] in {"site_observed", "official_site"}
            and not item["bound_to_decision_maker"]
        ]

    if person_bound_eligible:
        preferred = person_bound_eligible[0]
        contact_route = "person_bound"
    elif company_routed_eligible:
        preferred = company_routed_eligible[0]
        contact_route = "company_routed"
    else:
        preferred = None
        contact_route = None

    review_ready = bool(
        decision
        and decision_score >= 0.5
        and preferred
        and reconciliation_clear
    )
    if contact_route == "person_bound":
        outreach_ready = bool(
            decision
            and decision_score >= 0.5
            and person_bound_outreach
            and reconciliation_clear
        )
    elif contact_route == "company_routed":
        # Publication on the verified first-party site is the routing evidence.
        # Human review still remains mandatory before any outbound intent.
        outreach_ready = review_ready
    else:
        outreach_ready = False

    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "decision_maker": decision,
        "decision_reconciliation": reconciliation,
        "verified_contacts": verified,
        "preferred_email": preferred["email"] if preferred else None,
        "contact_route": contact_route,
        "person_bound": contact_route == "person_bound",
        "routing_name": (
            _text((decision or {}).get("name"))
            if contact_route == "company_routed"
            else None
        ),
        "routing_title": (
            _text((decision or {}).get("title"))
            if contact_route == "company_routed"
            else None
        ),
        "review_ready": review_ready,
        "outreach_ready": outreach_ready,
    }


def build_buyer_readiness_dossier(
    candidate: BuyerCandidate,
    contact_plan: Mapping[str, Any],
    *,
    buyer_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize buyer-side readiness without creating any authority."""
    if not isinstance(contact_plan, Mapping):
        raise ValueError("contact plan mapping required")

    decision = contact_plan.get("decision_maker")
    if not isinstance(decision, Mapping):
        decision = {}
    reconciliation = contact_plan.get("decision_reconciliation")
    if not isinstance(reconciliation, Mapping):
        reconciliation = {}

    try:
        decision_score = float(decision.get("decision_score") or 0.0)
    except (TypeError, ValueError):
        decision_score = 0.0

    decision_maker_ready = bool(
        decision
        and decision_score >= 0.5
        and not bool(reconciliation.get("review_required"))
    )
    review_ready = contact_plan.get("review_ready") is True
    outreach_ready = contact_plan.get("outreach_ready") is True

    if isinstance(buyer_row, Mapping):
        activation_ready, activation_reason = buyer_activation_decision(
            dict(buyer_row)
        )
        buyer_record_present = True
    else:
        activation_ready = False
        activation_reason = "missing_buyer"
        buyer_record_present = False

    blockers: list[str] = []
    if not candidate.entity_id:
        blockers.append("canonical_identity_missing")
    if not candidate.website:
        blockers.append("first_party_website_missing")
    if not decision_maker_ready:
        if reconciliation.get("review_required"):
            blockers.append("decision_maker_reconciliation_required")
        else:
            blockers.append("decision_maker_missing")
    elif not review_ready:
        blockers.append("verified_person_bound_contact_missing")
    elif not outreach_ready:
        blockers.append("outreach_evidence_below_floor")

    if not buyer_record_present:
        blockers.append("buyer_record_missing")
    elif not activation_ready:
        blockers.append(activation_reason)

    return {
        "mode": "OBSERVE",
        "write_authorized": False,
        "prospect_id": candidate.prospect_id,
        "entity_id": candidate.entity_id,
        "business_name": candidate.business_name,
        "website": candidate.website,
        "website_source": candidate.evidence.get("website_source"),
        "company_score": candidate.company_score,
        "decision_maker": dict(decision) if decision else None,
        "decision_maker_ready": decision_maker_ready,
        "review_ready": review_ready,
        "outreach_ready": outreach_ready,
        "buyer_record_present": buyer_record_present,
        "buyer_activation_ready": bool(activation_ready),
        "buyer_activation_reason": activation_reason,
        "allocation_ready": bool(activation_ready),
        "blockers": blockers,
        "next_required": blockers[0] if blockers else None,
    }


def build_candidate_review_plan(candidate: BuyerCandidate, contact_plan: Mapping[str, Any], *,
                                idempotency_key: str) -> dict[str, Any]:
    if not contact_plan.get("review_ready"):
        raise ValueError("verified review-ready contact required")
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
    source_aliases = {
        "person_structured_data": "official_site",
        "public_government_record": "public_record",
        "company_press_release": "press_release",
    }
    verified_contacts = []
    for raw_contact in contact_plan.get("verified_contacts") or []:
        item = dict(raw_contact)
        original_source = _text(item.get("source"))
        normalized_source = source_aliases.get(
            original_source,
            original_source,
        )
        if original_source and normalized_source != original_source:
            item["source_detail"] = original_source
            item["source"] = normalized_source
        verified_contacts.append(item)
    preferred_contact = next(
        (item for item in verified_contacts if _text(item.get("email")).lower() == email),
        {},
    )
    contact_source = _text(preferred_contact.get("source"))
    decision_source = _text(decision.get("source") or candidate.contact_source)
    evidence = {
        **candidate.evidence,
        "business_name": candidate.business_name,
        "niche": candidate.niche,
        "metro": candidate.metro,
        "website": candidate.website,
        "decision_role": decision.get("decision_role") or candidate.decision_role,
        "decision_source": decision_source or None,
        "contact_source": contact_source or None,
        "contact_route": _text(contact_plan.get("contact_route")) or None,
        "person_bound": bool(contact_plan.get("person_bound")),
        "routing_name": _text(contact_plan.get("routing_name")) or None,
        "routing_title": _text(contact_plan.get("routing_title")) or None,
        "verified_contacts": verified_contacts,
        "review_ready": bool(contact_plan.get("review_ready")),
        "outreach_ready": bool(contact_plan.get("outreach_ready")),
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
            "p_offer_key": (
            _text(contact_plan.get("offer_key"))
            or candidate.offer_key
        ),
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
