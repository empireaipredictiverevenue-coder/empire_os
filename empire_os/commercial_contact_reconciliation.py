"""Read-only reconciliation of verified first-party contacts into review rows.

This module does not authorize outreach, write to the database, mutate product
readiness, accept terms, move funds, or recognize revenue. It only upgrades
contact evidence when a target domain has exactly one unambiguous contact that
has already passed the bounded first-party + MX observation gates.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit


def _domain(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    try:
        return (urlsplit(text).hostname or "").removeprefix("www.")
    except ValueError:
        return ""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _email_domain(value: Any) -> str:
    email = _clean(value).lower()
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].removeprefix("www.")


def _verified_contacts(
    snapshot: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}

    for company in snapshot.get("items") or []:
        if not isinstance(company, Mapping):
            continue

        domain = _domain(company.get("domain"))
        if not domain:
            continue

        for contact in company.get("contacts") or []:
            if not isinstance(contact, Mapping):
                continue
            if contact.get("contact_verification_ready") is not True:
                continue
            if contact.get("person_explicitly_named") is not True:
                continue
            if contact.get("email_directly_bound_to_person") is not True:
                continue

            name = _clean(contact.get("person_name"))
            email = _clean(contact.get("email")).lower()
            source_url = _clean(contact.get("source_url"))

            if not name or not email or not source_url:
                continue
            if _email_domain(email) != domain:
                continue
            if _domain(source_url) != domain:
                continue

            grouped.setdefault(domain, []).append({
                **dict(contact),
                "person_name": name,
                "email": email,
                "source_url": source_url,
            })

    for domain, contacts in grouped.items():
        deduped: dict[tuple[str, str], dict[str, Any]] = {}
        for contact in contacts:
            key = (
                _clean(contact.get("person_name")).casefold(),
                _clean(contact.get("email")).casefold(),
            )
            deduped[key] = contact
        grouped[domain] = list(deduped.values())

    return grouped


def reconcile_review_contacts(
    review_rows: Iterable[Mapping[str, Any]],
    mx_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay only unique, current, verified contact evidence onto review rows."""
    grouped = _verified_contacts(mx_snapshot)

    rows: list[dict[str, Any]] = []
    promoted_domains: list[str] = []
    ambiguous_domains: list[str] = []

    for source in review_rows:
        if not isinstance(source, Mapping):
            continue

        row = deepcopy(dict(source))
        domain = _domain(row.get("domain"))
        contacts = grouped.get(domain, [])

        if len(contacts) == 1:
            contact = contacts[0]
            evidence_refs = list(row.get("evidence_refs") or [])
            source_url = contact["source_url"]
            if source_url not in evidence_refs:
                evidence_refs.append(source_url)

            contact_evidence = list(row.get("contact_evidence") or [])
            contact_evidence.append({
                "source_kind": "first_party_site_current",
                "source_url": source_url,
                "person_name": contact["person_name"],
                "person_title": _clean(contact.get("person_title")),
                "email": contact["email"],
                "person_explicitly_named": True,
                "email_directly_bound_to_person": True,
                "mx_verified": True,
                "execution_authority": "none",
                "outreach_authorized": False,
            })

            row.update({
                "person_name": contact["person_name"],
                "job_title": _clean(contact.get("person_title")) or row.get("job_title"),
                "person_verified": True,
                "email": contact["email"],
                "email_verified": True,
                "email_verification_scope":
                    "CURRENT_FIRST_PARTY_PERSON_BOUND_MX_OBSERVED",
                "person_evidence_state":
                    "FIRST_PARTY_PERSON_BOUND_MX_VERIFIED",
                "contact_evidence": contact_evidence,
                "evidence_refs": evidence_refs,
                "execution_authority": "none",
                "outreach_authorized": False,
            })
            promoted_domains.append(domain)

        elif len(contacts) > 1:
            ambiguous_domains.append(domain)

        # Never inherit execution authority from evidence artifacts.
        row["execution_authority"] = "none"
        row["outreach_authorized"] = False
        rows.append(row)

    return {
        "schema_version": "empire.commercial-contact-reconciliation.v1",
        "review_rows": rows,
        "promoted_domains": sorted(set(promoted_domains)),
        "promoted_count": len(set(promoted_domains)),
        "ambiguous_domains": sorted(set(ambiguous_domains)),
        "ambiguous_count": len(set(ambiguous_domains)),
        "execution_authority": "none",
        "outreach_authority": "none",
        "database_write_performed": False,
        "payment_action": False,
        "actual_revenue": False,
    }
