"""Domain sovereignty policy for Empire-owned outbound infrastructure."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class DomainSovereigntyPolicy:
    sovereign_score: int = 85
    minimum_score: int = 65


_CONTROLS = (
    ("registrar_account_owned", 20, "registrar_control_unverified"),
    ("dns_authority_owned", 20, "dns_authority_unverified"),
    ("mfa_enabled", 10, "registrar_mfa_unverified"),
    ("domain_lock_enabled", 5, "domain_lock_unverified"),
    ("auto_renew_enabled", 5, "auto_renew_unverified"),
    ("dns_zone_exported", 10, "dns_zone_backup_unverified"),
    ("dmarc_rua_empire_owned", 10, "dmarc_reporting_not_empire_owned"),
    ("provider_portable_sender_identity", 10, "sender_identity_provider_locked"),
    ("recovery_path_verified", 10, "domain_recovery_path_unverified"),
)


def evaluate_domain_sovereignty(
    context: Mapping[str, Any] | None,
    *,
    policy: DomainSovereigntyPolicy | None = None,
) -> dict[str, Any]:
    """Score whether Empire can retain its domain identity when vendors are replaced."""

    policy = policy or DomainSovereigntyPolicy()
    context = dict(context or {})
    score = 0
    evidence_holds: list[str] = []
    hard_holds: list[str] = []
    warnings: list[str] = []

    for key, weight, reason in _CONTROLS:
        value = context.get(key)
        if value is True:
            score += weight
        elif value is False and key in {"registrar_account_owned", "dns_authority_owned"}:
            hard_holds.append(reason)
        else:
            evidence_holds.append(reason)

    purpose = str(context.get("purpose") or "unknown").lower()
    if context.get("uses_primary_brand_root") is True and purpose in {
        "prospecting",
        "cold_outbound",
        "promotional",
    }:
        warnings.append("primary_brand_reputation_exposure")

    if context.get("provider_managed_dkim_only") is True:
        warnings.append("provider_managed_dkim_dependency")

    if context.get("single_transport_dependency") is True:
        warnings.append("single_transport_dependency")

    if hard_holds:
        status = "HOLD"
    elif score >= policy.sovereign_score and not evidence_holds:
        status = "SOVEREIGN"
    elif score >= policy.minimum_score:
        status = "PARTIAL"
    else:
        status = "WEAK"

    return {
        "status": status,
        "score": score,
        "hard_holds": hard_holds,
        "evidence_holds": evidence_holds,
        "warnings": warnings,
        "domain": str(context.get("domain") or ""),
        "purpose": purpose,
    }
