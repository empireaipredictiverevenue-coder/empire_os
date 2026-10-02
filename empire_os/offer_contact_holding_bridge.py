"""Bridge verified offer-book contacts into Buyer Scout holding evidence."""
from __future__ import annotations

from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from empire_os.buyer_discovery import looks_like_person_name


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


def build_holding_candidates(
    recovery: Mapping[str, Any],
    *,
    mx_rows: Iterable[Mapping[str, Any]],
    suppressed_emails: Iterable[str] = (),
) -> dict[str, Any]:
    mx_by_email = {
        _text(row.get("email")).lower(): dict(row)
        for row in mx_rows
        if isinstance(row, Mapping) and _text(row.get("email"))
    }
    suppressed = {
        _text(value).lower()
        for value in suppressed_emails
        if _text(value)
    }

    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for raw in recovery.get("items") or []:
        if not isinstance(raw, Mapping):
            continue
        company = _text(raw.get("company"))
        domain = _host(raw.get("domain"))
        if not company or not domain:
            continue

        accepted: list[dict[str, Any]] = []
        reasons: set[str] = set()
        for contact in raw.get("person_bound_candidates") or []:
            if not isinstance(contact, Mapping):
                continue
            name = _text(contact.get("person_name"))
            title = _text(contact.get("person_title"))
            email = _text(contact.get("email")).lower()
            source_url = _text(contact.get("source_url"))
            mx = mx_by_email.get(email, {})

            if (
                contact.get("person_explicitly_named") is not True
                or contact.get("email_directly_bound_to_person") is not True
                or not looks_like_person_name(name)
            ):
                reasons.add("person_binding_invalid")
                continue
            if _host(source_url) != domain:
                reasons.add("source_domain_mismatch")
                continue
            if _email_domain(email) != domain:
                reasons.add("email_domain_mismatch")
                continue
            if email in suppressed:
                reasons.add("recipient_suppressed")
                continue
            if (
                mx.get("is_valid") is not True
                or mx.get("has_mx") is not True
                or mx.get("is_role_address") is True
                or mx.get("is_disposable") is True
            ):
                reasons.add("mx_verification_failed")
                continue

            accepted.append({
                "name": name,
                "title": title,
                "email": email,
                "source_url": source_url,
                "source": _text(contact.get("source")) or "first_party_site",
                "mx_verified": True,
                "mx_confidence": float(mx.get("confidence") or 0.0),
                "smtp_status": _text(mx.get("smtp_status")) or "not_run",
                "person_explicitly_named": True,
                "email_directly_bound_to_person": True,
            })

        if not accepted:
            blocked.append({
                "company": company,
                "domain": domain,
                "reasons": sorted(reasons) or ["no_eligible_contacts"],
            })
            continue

        product_codes = [
            _text(code)
            for code in raw.get("ready_product_codes") or []
            if _text(code)
        ]
        query_evidence = []
        for product_code in product_codes or [None]:
            for contact in accepted:
                query_evidence.append({
                    "query": "first_party_contact_recovery",
                    "source": "commercial_offer_book",
                    "source_url": contact["source_url"],
                    "buyer_pool": "enterprise_and_data_buyers",
                    "product_code": product_code,
                    "person_name": contact["name"],
                    "email": contact["email"],
                    "mx_verified": True,
                })

        candidate = {
            "domain": domain,
            "business_name": company,
            "website": f"https://{domain}/",
            "description": "First-party commercial contact evidence recovered.",
            "buyer_type": "research_candidate",
            "direct_buyer_score": 0,
            "explicit_direct_buyer_evidence": False,
            "target_buyer_pools": ["enterprise_and_data_buyers"],
            "target_product_codes": product_codes,
            "target_corridor_keys": [],
            "query_evidence": query_evidence,
            "site_evidence": {
                "business_name_source": "commercial_offer_book_first_party_probe",
                "canonical_seed_identity_corroborated": False,
                "site_business_names": [company],
                "site_evidence_score": 1.0,
                "first_party_email_count": len(accepted),
                "first_party_phone_count": 0,
                "people_count": len(accepted),
                "first_party_emails": [row["email"] for row in accepted],
                "first_party_phones": [],
                "first_party_people": accepted,
                "budget_verified": False,
            },
            "provenance": {
                "source": "commercial_offer_book_contact_recovery",
                "source_generated_at": recovery.get("generated_at"),
                "person_bound_contact_count": len(accepted),
                "mx_verified_contact_count": len(accepted),
                "canonical_identity_verified": False,
                "commercial_terms_verified": False,
                "outreach_authorized": False,
                "buy_signal_score_state": "UNKNOWN",
            },
        }
        candidates.append(candidate)

    candidates.sort(key=lambda row: row["domain"])
    blocked.sort(key=lambda row: row["domain"])
    return {
        "schema_version": "empire.offer-contact-holding-bridge.v1",
        "candidate_count": len(candidates),
        "verified_contact_count": sum(
            len(row["site_evidence"]["first_party_people"])
            for row in candidates
        ),
        "blocked_company_count": len(blocked),
        "candidates": candidates,
        "blocked": blocked,
        "holding_area_only": True,
        "canonical_promotion_performed": False,
        "outbound_authorized": False,
        "execution_authority": "internal_holding_write_only",
        "payment_action": False,
        "actual_revenue": False,
    }
