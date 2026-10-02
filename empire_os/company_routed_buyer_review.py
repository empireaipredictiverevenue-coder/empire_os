"""Prepare founder-review candidates for verified company-routed outreach."""
from __future__ import annotations

from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from empire_os.buyer_discovery import (
    classify_decision_role,
    looks_like_person_name,
)


_ALLOWED_ROUTE_SOURCES = {
    "first_party_site",
    "first_party_contact_page",
    "first_party_privacy_policy",
    "official_site",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _host(value: Any) -> str:
    text = _text(value).lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        return (urlparse(text).hostname or "").removeprefix("www.")
    except ValueError:
        return ""


def _email_domain(value: Any) -> str:
    email = _text(value).lower()
    return email.rsplit("@", 1)[-1] if "@" in email else ""


def _authority_rank(title: str) -> int:
    value = _text(title).casefold()
    if "founder" in value or "chief executive" in value or "ceo" in value:
        return 4
    if "president" in value:
        return 3
    if "managing partner" in value or "managing director" in value:
        return 2
    return 1


def _eligible_people(
    row: Mapping[str, Any],
    *,
    company_domain: str,
) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for raw in row.get("target_people") or []:
        if not isinstance(raw, Mapping):
            continue
        name = _text(raw.get("name"))
        title = _text(raw.get("title"))
        evidence_url = _text(raw.get("evidence_url"))
        if not looks_like_person_name(name):
            continue
        role, score = classify_decision_role(title)
        if role != "economic_buyer" or score < 0.70:
            continue
        if _host(evidence_url) != company_domain:
            continue
        people.append({
            "name": name,
            "title": title,
            "decision_role": role,
            "decision_score": score,
            "authority_rank": _authority_rank(title),
            "evidence_url": evidence_url,
            "source": _text(raw.get("source")) or None,
        })
    return people


def _eligible_routes(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for raw in row.get("company_contact_routes") or []:
        if not isinstance(raw, Mapping):
            continue
        email = _text(raw.get("value")).lower()
        source = _text(raw.get("source"))
        evidence_url = _text(raw.get("evidence_url"))
        if (
            raw.get("verified") is not True
            or _text(raw.get("channel")) != "email"
            or "@" not in email
            or not evidence_url
            or source not in _ALLOWED_ROUTE_SOURCES
        ):
            continue
        domain = _email_domain(email)
        if not domain or _host(evidence_url) != domain:
            continue
        routes.append({
            "email": email,
            "email_domain": domain,
            "source": source,
            "evidence_url": evidence_url,
            "person_bound": False,
        })
    return routes


def build_company_routed_review_queue(
    rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    counts = {
        "review_ready": 0,
        "ambiguous_person": 0,
        "no_same_domain_person": 0,
    }

    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        routes = _eligible_routes(raw)
        if not routes:
            continue

        # Keep each company on one route domain. Different route domains are
        # not automatically reconciled.
        route_domains = {route["email_domain"] for route in routes}
        if len(route_domains) != 1:
            continue
        company_domain = next(iter(route_domains))
        people = _eligible_people(raw, company_domain=company_domain)
        if not people:
            counts["no_same_domain_person"] += 1
            continue

        highest = max(person["authority_rank"] for person in people)
        top = [
            person for person in people
            if person["authority_rank"] == highest
        ]
        if len(top) != 1:
            counts["ambiguous_person"] += 1
            items.append({
                "prospect_id": _text(raw.get("prospect_id")),
                "business_name": _text(raw.get("business_name")),
                "offer_key": _text(raw.get("offer_key")) or None,
                "priority_score": raw.get("priority_score"),
                "state": "AMBIGUOUS_PERSON",
                "candidate_people": top,
                "company_routes": routes,
                "person_bound": False,
                "outbound_authorized": False,
                "founder_gate_required": True,
            })
            continue

        counts["review_ready"] += 1
        items.append({
            "prospect_id": _text(raw.get("prospect_id")),
            "business_name": _text(raw.get("business_name")),
            "offer_key": _text(raw.get("offer_key")) or None,
            "priority_score": raw.get("priority_score"),
            "state": "FOUNDER_REVIEW_READY",
            "routing_person": top[0],
            "company_routes": routes,
            "person_bound": False,
            "outbound_authorized": False,
            "founder_gate_required": True,
            "copy_instruction": (
                "Address the named buyer in the message body while explicitly "
                "treating the destination as a company-routed inbox."
            ),
        })

    items.sort(key=lambda row: (
        row["state"] != "FOUNDER_REVIEW_READY",
        -(float(row.get("priority_score") or 0)),
        row.get("business_name") or "",
    ))
    return {
        "schema_version": "empire.company-routed-buyer-review.v1",
        "candidate_count": len(items),
        "review_ready_count": counts["review_ready"],
        "ambiguous_person_count": counts["ambiguous_person"],
        "no_same_domain_person_count": counts["no_same_domain_person"],
        "items": items,
        "execution_authority": "none",
        "outbound_authorized": False,
        "database_write_performed": False,
        "payment_action": False,
        "actual_revenue": False,
    }
