"""Isolated public-site probe worker for Phase 3E buyer review."""
from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from empire_os.buyer_discovery import (
    build_candidate,
    enrich_candidate,
    generate_work_email_candidates,
    merge_generated_contact_evidence,
    merge_public_web_contact_evidence,
    rank_site_people,
    validate_email_candidates,
    verify_contact_plan,
)
from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.models import VerificationState
from empire_os.hunter.verification_mesh import VerificationMesh
from empire_os.mx_validator import MxValidator
from empire_os.search_fabric.site_probe import probe_site



def _smtp_verified_generated_contacts(
    enriched: dict,
    website: str,
    *,
    smtp_timeout: int = 2,
) -> tuple[list[dict], dict]:
    decision = enriched.get("decision_maker")
    if not isinstance(decision, dict):
        return [], {"attempted": False, "reason": "missing_decision_maker"}
    name = str(decision.get("name") or "").strip()
    try:
        score = float(decision.get("decision_score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if not name or score < 0.70:
        return [], {"attempted": False, "reason": "decision_score_below_floor"}

    candidates = generate_work_email_candidates(name, website)
    if not candidates:
        return [], {"attempted": False, "reason": "no_generated_candidates"}
    domain = candidates[0].rsplit("@", 1)[-1]
    token = hashlib.sha256((name + "|" + domain).encode()).hexdigest()[:14]
    sentinel = f"empire-probe-{token}@{domain}"

    catch_validator = MxValidator(
        smtp_timeout=smtp_timeout,
        do_smtp_probe=True,
    )
    catch = catch_validator.validate(sentinel)
    if catch.smtp_accepts:
        return [], {
            "attempted": True,
            "catch_all": True,
            "sentinel": sentinel,
            "candidates": len(candidates),
        }

    def check(email: str) -> list[dict]:
        validator = MxValidator(
            smtp_timeout=smtp_timeout,
            do_smtp_probe=True,
        )
        return validate_email_candidates(
            [email],
            validator,
            require_smtp=True,
        )

    valid: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
        futures = {pool.submit(check, email): email for email in candidates}
        for future in as_completed(futures):
            try:
                valid.extend(future.result())
            except Exception:
                continue

    valid.sort(
        key=lambda item: candidates.index(item["email"])
        if item.get("email") in candidates
        else 999
    )
    return valid, {
        "attempted": True,
        "catch_all": False,
        "sentinel": sentinel,
        "candidates": len(candidates),
        "smtp_valid": len(valid),
    }

def run(row: dict, *, max_pages: int = 9, request_timeout: float = 4.0,
        time_budget_seconds: float = 22.0) -> dict:
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

    generated_validated = []
    generated_probe = {"attempted": False, "reason": "not_needed"}
    has_bound = any(
        isinstance(item, dict)
        and item.get("bound_to_decision_maker") is True
        for item in (enriched.get("contact_candidates") or [])
    )
    if not has_bound:
        generated_validated, generated_probe = (
            _smtp_verified_generated_contacts(
                enriched,
                candidate.website,
            )
        )
        if generated_validated:
            enriched = merge_generated_contact_evidence(
                enriched,
                generated_validated,
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
        "generated_smtp_contacts": generated_validated,
        "generated_smtp_probe": generated_probe,
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
