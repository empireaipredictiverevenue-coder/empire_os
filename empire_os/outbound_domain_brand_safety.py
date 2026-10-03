"""Brand-safety policy for Empire-owned outreach domains.

Reputation isolation is allowed; deceptive identity is not. The policy consumes explicit
ownership/disclosure evidence and conservative lexical checks. It never registers,
redirects, or mutates DNS.
"""
from __future__ import annotations

from typing import Any, Mapping


def evaluate_domain_brand_safety(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    domain = str(context.get("domain") or "").strip().lower().rstrip(".")
    purpose = str(context.get("purpose") or "").strip().lower()
    primary_brand_domain = str(
        context.get("primary_brand_domain") or ""
    ).strip().lower().rstrip(".")

    owned = context.get("empire_owned") is True
    registrar_controlled = context.get("registrar_controlled") is True
    third_party_impersonation = context.get("third_party_impersonation") is True
    typo_variant = context.get("deceptive_typo_variant") is True
    brand_disclosure = context.get("brand_disclosure_present") is True
    relationship_disclosed = context.get("relationship_to_empire_disclosed") is True
    idn_reviewed = context.get("idn_reviewed") is True

    hard_holds: list[str] = []
    warnings: list[str] = []

    if not domain or "." not in domain:
        hard_holds.append("domain_missing_or_invalid")
    if not owned:
        hard_holds.append("domain_not_empire_owned")
    if not registrar_controlled:
        hard_holds.append("domain_registrar_control_unverified")
    if third_party_impersonation:
        hard_holds.append("third_party_impersonation_forbidden")
    if typo_variant:
        hard_holds.append("deceptive_typo_variant_forbidden")

    is_idn = domain.startswith("xn--") or ".xn--" in domain
    if is_idn and not idn_reviewed:
        hard_holds.append("idn_domain_requires_manual_review")

    if purpose in {"prospecting", "cold_outbound", "promotional"}:
        if not brand_disclosure:
            warnings.append("outreach_domain_brand_disclosure_missing")
        if (
            primary_brand_domain
            and domain != primary_brand_domain
            and not relationship_disclosed
        ):
            warnings.append("outreach_domain_empire_relationship_not_disclosed")

    if primary_brand_domain and domain == primary_brand_domain:
        warnings.append("primary_brand_domain_reputation_exposure")

    if hard_holds:
        posture = "HOLD"
    elif warnings:
        posture = "REMEDIATE"
    else:
        posture = "SAFE"

    return {
        "domain": domain,
        "purpose": purpose,
        "primary_brand_domain": primary_brand_domain or None,
        "posture": posture,
        "hard_holds": hard_holds,
        "warnings": warnings,
        "is_idn": is_idn,
        "mutation_authorized": False,
    }
