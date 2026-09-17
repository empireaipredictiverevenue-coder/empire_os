"""Isolated public-site probe worker for Phase 3E buyer review."""
from __future__ import annotations

import json
import sys

from empire_os.buyer_discovery import build_candidate, enrich_candidate, verify_contact_plan
from empire_os.mx_validator import MxValidator
from empire_os.search_fabric.site_probe import probe_site


def run(row: dict, *, max_pages: int = 2, request_timeout: float = 3.0,
        time_budget_seconds: float = 6.0) -> dict:
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
    )
    enriched = enrich_candidate(candidate, evidence)
    contact = verify_contact_plan(enriched, validator=MxValidator(do_smtp_probe=False))
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
