"""Domain fleet continuity and sovereignty risk checks."""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping


def evaluate_domain_continuity(
    context: Mapping[str, Any],
    *,
    today: date,
) -> dict[str, Any]:
    warnings: list[str] = []
    hard_holds: list[str] = []

    purpose = str(context.get("purpose") or "unknown").lower()
    days_to_expiry = context.get("days_to_expiry")
    registrar_owned = context.get("registrar_owned") is True
    dns_owned = context.get("dns_owned") is True
    registrar_lock = context.get("registrar_lock") is True
    auto_renew = context.get("auto_renew") is True
    nameserver_drift = context.get("nameserver_drift") is True
    dnssec_valid = context.get("dnssec_valid")
    dkim_selector_count = int(context.get("dkim_selector_count") or 0)
    dmarc_rua_owned = context.get("dmarc_rua_owned") is True

    if not registrar_owned:
        hard_holds.append("registrar_not_empire_controlled")
    if not dns_owned:
        hard_holds.append("dns_not_empire_controlled")
    if nameserver_drift:
        hard_holds.append("unexpected_nameserver_drift")

    if days_to_expiry is None:
        warnings.append("expiry_evidence_missing")
    else:
        days = int(days_to_expiry)
        if days <= 14:
            hard_holds.append("domain_expiry_critical")
        elif days <= 60:
            warnings.append("domain_expiry_near")

    if not registrar_lock:
        warnings.append("registrar_lock_missing")
    if not auto_renew:
        warnings.append("auto_renew_missing")
    if dnssec_valid is False:
        warnings.append("dnssec_invalid_or_disabled")
    elif dnssec_valid is None:
        warnings.append("dnssec_unverified")
    if dkim_selector_count < 1:
        hard_holds.append("no_active_dkim_selector")
    if not dmarc_rua_owned:
        warnings.append("dmarc_reporting_not_empire_controlled")

    if purpose in {"prospecting", "cold_outbound", "promotional"} and context.get("is_primary_brand_domain") is True:
        warnings.append("primary_brand_reputation_blast_radius")

    if hard_holds:
        posture = "HOLD"
    elif warnings:
        posture = "REMEDIATE"
    else:
        posture = "HEALTHY"

    return {
        "domain": str(context.get("domain") or ""),
        "purpose": purpose,
        "posture": posture,
        "hard_holds": hard_holds,
        "warnings": warnings,
        "evaluated_on": today.isoformat(),
    }
