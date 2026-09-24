"""Build a review-only commercial packet for recovered permit-intelligence buyers.

The packet is internal preparation. It reads verified buyer evidence, current
permit recovery supply, and canonical commercial catalog truth. It does not
promote a buyer, send outbound, accept terms, create payment requests, or
recognize revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import json
import re

from empire_os.buyer_deferred_enrichment import canonical_phone


OUTPUT_DIR = Path("runtime/revenue/permit_buyer_packets")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _clean_email(value: Any) -> str | None:
    email = _text(value).lower()
    if not email or "@" not in email:
        return None
    local, domain = email.rsplit("@", 1)
    if not local or "." not in domain:
        return None
    if domain.endswith(("comcall", "comemail", "comphone")):
        return None
    if local.startswith("email") and domain.endswith("call"):
        return None
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_~-]+", local):
        return None
    if not re.fullmatch(r"[a-z0-9.-]+", domain):
        return None
    return email


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _company_routes(
    candidate: Mapping[str, Any],
    public_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    site = (
        dict(candidate.get("site_evidence") or {})
        if isinstance(candidate.get("site_evidence"), Mapping)
        else {}
    )
    route = (
        dict(public_evidence.get("contact_route") or {})
        if isinstance(public_evidence.get("contact_route"), Mapping)
        else {}
    )

    emails = _unique([
        value
        for raw in [
            route.get("email"),
            *(site.get("first_party_emails") or []),
        ]
        if (value := _clean_email(raw))
    ])
    phones = _unique([
        value
        for raw in [
            route.get("phone"),
            route.get("fallback_phone"),
            *(site.get("first_party_phones") or []),
        ]
        if (value := canonical_phone(raw))
    ])
    return {
        "route_type": "company_route",
        "emails": emails,
        "phones": phones,
        "person_bound": False,
    }


def _catalog_price(catalog: Mapping[str, Any]) -> dict[str, Any]:
    price = (
        dict(catalog.get("price_basis") or {})
        if isinstance(catalog.get("price_basis"), Mapping)
        else {}
    )
    return {
        "product_id": catalog.get("product_id"),
        "product_code": catalog.get("product_code"),
        "product_name": catalog.get("product_name"),
        "billing_model": catalog.get("billing_model"),
        "amount_cents": price.get("amount_cents"),
        "currency": price.get("currency") or catalog.get("currency"),
        "unit": price.get("unit"),
        "price_state": price.get("state"),
        "catalog_state": catalog.get("catalog_state"),
        "version_state": catalog.get("version_state"),
        "binding_terms_ready": catalog.get("binding_terms_ready") is True,
        "approval_reference": price.get("approval_reference"),
    }


def build_permit_buyer_packet(
    *,
    candidate: Mapping[str, Any],
    inventory_summary: Mapping[str, Any],
    catalog: Mapping[str, Any],
    public_evidence: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    domain = _text(candidate.get("domain"))
    if not domain:
        raise ValueError("buyer candidate domain required")
    if candidate.get("review_state") != "review_ready":
        raise ValueError("buyer candidate must be review_ready")
    if candidate.get("reconciliation_state") != "REVIEW_READY":
        raise ValueError("buyer candidate reconciliation must be REVIEW_READY")

    products = {
        _text(value)
        for value in (candidate.get("target_product_codes") or [])
        if _text(value)
    }
    if "permit_intelligence" not in products:
        raise ValueError("permit_intelligence target evidence required")

    site = (
        dict(candidate.get("site_evidence") or {})
        if isinstance(candidate.get("site_evidence"), Mapping)
        else {}
    )
    if site.get("permit_territory_state") != "NYC_FIRST_PARTY_EVIDENCE":
        raise ValueError("NYC first-party territory evidence required")

    if _text(catalog.get("product_code")) != "permit_intelligence":
        raise ValueError("permit_intelligence catalog row required")
    if catalog.get("binding_terms_ready") is not True:
        raise ValueError("permit_intelligence catalog must be terms-ready")

    evidence_domain = _text(public_evidence.get("domain")).lower()
    if evidence_domain != domain.lower():
        raise ValueError("public buyer evidence domain mismatch")

    decision_makers = [
        dict(row)
        for row in (public_evidence.get("decision_maker_priority") or [])
        if isinstance(row, Mapping)
        and _text(row.get("name"))
        and _text(row.get("role"))
    ]
    routes = _company_routes(candidate, public_evidence)
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    verified_current = int(
        inventory_summary.get("verified_current_inventory") or 0
    )
    owner_identified = int(
        inventory_summary.get("verified_current_owner_identified") or 0
    )
    project_only = int(
        inventory_summary.get("verified_current_project_only") or 0
    )
    niche_counts = dict(inventory_summary.get("niche_counts") or {})

    price = _catalog_price(catalog)
    conversation_ready = bool(
        verified_current > 0
        and decision_makers
        and (routes["emails"] or routes["phones"])
        and price["binding_terms_ready"]
    )

    packet = {
        "schema_version": "empire.permit-buyer-commercial-packet.v1",
        "mode": "REVIEW_ONLY",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "buyer": {
            "candidate_id": candidate.get("id"),
            "domain": domain,
            "business_name": candidate.get("business_name"),
            "website": candidate.get("website"),
            "buyer_type": candidate.get("buyer_type"),
            "review_state": candidate.get("review_state"),
            "reconciliation_state": candidate.get("reconciliation_state"),
            "territory_state": site.get("permit_territory_state"),
            "territory_evidence": list(
                site.get("permit_territory_evidence") or []
            ),
        },
        "decision_makers": decision_makers,
        "contact_routes": routes,
        "supply": {
            "source": "legacy_permit_recovery_observer_v5",
            "territory": "NYC",
            "verified_current_inventory": verified_current,
            "verified_current_owner_identified": owner_identified,
            "verified_current_project_only": project_only,
            "niche_counts": niche_counts,
            "full_scan_complete": bool(
                inventory_summary.get("full_scan_complete")
            ),
            "commercial_ready_claimed": False,
        },
        "offer": price,
        "commercial_angle": {
            "problem_hypothesis": (
                "Surface current NYC permit/project-start opportunities "
                "relevant to the buyer's service territory before they are "
                "obvious through slower manual prospecting."
            ),
            "evidence_basis": (
                "current source-revalidated NYC permit inventory plus "
                "first-party buyer territory evidence"
            ),
            "positioning": (
                "Permit Intelligence monthly subscription; use a genuine "
                "buyer conversation to confirm desired project types, "
                "territories, delivery cadence and capacity before terms."
            ),
        },
        "conversation_objectives": [
            "Confirm which NYC project and permit types are commercially relevant.",
            "Confirm borough or territory coverage.",
            "Confirm desired alert/feed cadence and delivery route.",
            "Confirm daily or weekly capacity for opportunities.",
            "Confirm whether the verified catalog price basis is acceptable.",
        ],
        "known_blockers_before_binding_terms": [
            "genuine_buyer_conversation_missing",
            "buyer_capacity_not_confirmed",
            "buyer_delivery_preference_not_confirmed",
            "buyer_price_acceptance_not_observed",
        ],
        "conversation_ready": conversation_ready,
        "outreach_draft_allowed": conversation_ready,
        "live_outbound_send": False,
        "buyer_activation_performed": False,
        "terms_accepted": False,
        "payment_request_created": False,
        "actual_revenue": False,
        "execution_authority": "review_packet_only",
    }
    return packet


def write_permit_buyer_packet(
    repo_root: str | Path,
    payload: Mapping[str, Any],
) -> Path:
    root = Path(repo_root).resolve()
    domain = re.sub(
        r"[^a-z0-9.-]+",
        "_",
        _text((payload.get("buyer") or {}).get("domain")).lower(),
    )
    if not domain:
        raise ValueError("packet buyer domain required")
    path = root / OUTPUT_DIR / f"{domain}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path
