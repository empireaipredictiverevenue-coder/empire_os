"""Isolated public-site probe worker for Phase 3E buyer review."""
from __future__ import annotations

import json
import sys

from empire_os.buyer_discovery import (
    build_candidate,
    enrich_candidate,
    merge_public_web_contact_evidence,
    rank_site_people,
    verify_contact_plan,
)
from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.models import VerificationState
from empire_os.hunter.verification_mesh import VerificationMesh
from empire_os.mx_validator import MxValidator
from empire_os.search_fabric.site_probe import probe_site


def run(row: dict, *, max_pages: int = 5, request_timeout: float = 4.0,
        time_budget_seconds: float = 15.0) -> dict:
    candidate = build_candidate(
        row,
        entity_id=row.get("entity_id") or None,
        entity_linked=bool(row.get("entity_id")),
    )
    evidence = probe_site(
        candidate.website,
        max_pages=max_pages,
        request_timeout=request_timeout,
        time_budget_seconds=time_budget_seconds,
        page_priority="people",
    )
    enriched = enrich_candidate(candidate, evidence)

    # Prefer current first-party structured person+email evidence when the
    # canonical contact does not yield a bound email. This lets stale contact
    # names self-heal without weakening identity or source requirements.
    bound_now = any(
        item.get("bound_to_decision_maker") is True
        for item in (enriched.get("contact_candidates") or [])
        if isinstance(item, dict)
    )
    if not bound_now:
        official_people = [
            item for item in rank_site_people(evidence.get("people") or [])
            if item.get("email")
            and float(item.get("decision_score") or 0.0) >= 0.70
        ]
        if official_people:
            person = official_people[0]
            enriched = dict(enriched)
            enriched["decision_maker"] = {
                **person,
                "source": "website_structured_data",
            }
            enriched["decision_reconciliation"] = {
                "status": "official_site_current",
                "review_required": False,
                "decision_maker": enriched["decision_maker"],
            }
            enriched["contact_candidates"] = [
                {
                    "email": str(person.get("email") or "").strip().lower(),
                    "source": "person_structured_data",
                    "bound_to_decision_maker": True,
                }
            ]
            enriched["contact_email_candidates"] = [
                str(person.get("email") or "").strip().lower()
            ]

    decision = enriched.get("decision_maker")
    known_people = (
        (dict(decision),)
        if isinstance(decision, dict)
        and decision.get("name")
        else ()
    )
    hunter = analyze_domain(
        candidate.website,
        mesh=VerificationMesh(
            mx_validator=MxValidator(do_smtp_probe=False)
        ),
        probe=lambda *args, **kwargs: evidence,
        known_people=known_people,
        max_pages=max_pages,
        request_timeout=request_timeout,
        time_budget_seconds=time_budget_seconds,
    )
    hunter_first_party = [
        {
            "name": item.person_name,
            "email": item.email,
            "source_url": item.source_url or candidate.website,
            "source_kind": "official_site",
            "role_corroborated": True,
            "direct_publication": True,
        }
        for item in hunter.confirmed_contacts
        if item.state is VerificationState.CONFIRMED
        and item.person_name
    ]
    if hunter_first_party:
        enriched = merge_public_web_contact_evidence(
            enriched,
            hunter_first_party,
        )

    contact = verify_contact_plan(
        enriched,
        validator=MxValidator(do_smtp_probe=False),
    )

    return {
        "prospect_id": candidate.prospect_id,
        "business_name": candidate.business_name,
        "site_ok": bool(evidence.get("ok")),
        "site_evidence_score": evidence.get("evidence_score"),
        "budget_exhausted": bool(evidence.get("budget_exhausted")),
        "decision_maker": enriched.get("decision_maker"),
        "contacts": enriched.get("contact_candidates") or [],
        "verified_contacts": contact.get("verified_contacts") or [],
        "review_ready": bool(contact.get("review_ready")),
        "outreach_ready": bool(contact.get("outreach_ready")),
        "preferred_email": contact.get("preferred_email"),
        "hunter_domain_pattern": hunter.pattern.as_dict(),
        "hunter_confirmed_contacts": [
            item.as_dict() for item in hunter.confirmed_contacts
        ],
        "hunter_probable_contacts": [
            item.as_dict()
            for item in hunter.contacts
            if item.state is VerificationState.PROBABLE
        ],
        "mode": "OBSERVE",
        "write_authorized": False,
    }


def rejection_reason(result: dict) -> str | None:
    if result.get("review_ready"):
        return None
    if not result.get("site_ok"):
        return "site_unavailable"
    if not result.get("decision_maker"):
        return "no_decision_maker"
    contacts = result.get("contacts") or []
    if not contacts:
        return "no_contact_evidence"
    if not any(item.get("bound_to_decision_maker") for item in contacts):
        return "no_bound_contact"
    verified = result.get("verified_contacts") or []
    if verified and all(item.get("is_role_address") for item in verified):
        return "role_address_only"
    return "contact_not_verified"


def main() -> int:
    row = json.loads(sys.stdin.read())
    result = run(row)
    result["rejection_reason"] = rejection_reason(result)
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
