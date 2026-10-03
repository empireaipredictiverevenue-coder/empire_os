"""Destination-scoped reputation decisions for Ringleader."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.google_postmaster_v2 import normalize_compliance_status
from empire_os.microsoft_outlook_evidence import normalize_outlook_delivery_evidence
from empire_os.outbound_yahoo_evidence import normalize_yahoo_delivery_evidence
from empire_os.outbound_apple_evidence import normalize_apple_delivery_evidence


def evaluate_destination_reputation(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    family = str(context.get("mx_family") or "UNKNOWN").upper()
    seed = dict(context.get("seed_placement") or {})

    evidence: dict[str, Any] = {}
    holds: list[str] = []
    warnings: list[str] = []

    if family == "GOOGLE":
        google_payload = context.get("google_compliance")
        if isinstance(google_payload, Mapping):
            google = normalize_compliance_status(google_payload)
            evidence["google"] = google
            if google["posture"] == "HOLD_GMAIL":
                holds.append("google_destination_hold")
            elif google["posture"] in {"LIMIT_GMAIL", "OBSERVE"}:
                warnings.append("google_destination_limited_or_sparse")
        else:
            warnings.append("google_compliance_unavailable")

    elif family == "MICROSOFT":
        microsoft_payload = context.get("microsoft_delivery")
        if isinstance(microsoft_payload, Mapping):
            microsoft = normalize_outlook_delivery_evidence(microsoft_payload)
            evidence["microsoft"] = microsoft
            if microsoft["posture"] in {"HOLD_MICROSOFT", "HOLD_RECIPIENT"}:
                holds.append("microsoft_destination_hold")
            elif microsoft["posture"] == "BACKOFF_MICROSOFT":
                warnings.append("microsoft_destination_backoff")
        else:
            warnings.append("microsoft_delivery_evidence_unavailable")

    elif family == "YAHOO":
        yahoo_payload = context.get("yahoo_delivery")
        if isinstance(yahoo_payload, Mapping):
            yahoo = normalize_yahoo_delivery_evidence(yahoo_payload)
            evidence["yahoo"] = yahoo
            if yahoo["posture"] in {"HOLD_YAHOO", "HOLD_RECIPIENT"}:
                holds.append("yahoo_destination_hold")
            elif yahoo["posture"] in {"BACKOFF_YAHOO", "LIMIT_YAHOO"}:
                warnings.append("yahoo_destination_limited_or_backoff")
        else:
            warnings.append("yahoo_delivery_evidence_unavailable")

    elif family == "APPLE":
        apple_payload = context.get("apple_delivery")
        if isinstance(apple_payload, Mapping):
            apple = normalize_apple_delivery_evidence(apple_payload)
            evidence["apple"] = apple
            if apple["posture"] == "HOLD_RECIPIENT":
                holds.append("apple_destination_hold")
            elif apple["posture"] == "BACKOFF_APPLE":
                warnings.append("apple_destination_backoff")
        else:
            warnings.append("apple_delivery_evidence_unavailable")

    placement_rate = seed.get("inbox_placement_rate")
    if placement_rate is not None:
        value = float(placement_rate)
        evidence["seed_inbox_placement_rate"] = value
        if value < 0.90:
            holds.append("destination_seed_placement_low")
        elif value < 0.95:
            warnings.append("destination_seed_placement_degraded")
    else:
        warnings.append("destination_seed_placement_unmeasured")

    if holds:
        posture = "HOLD_DESTINATION"
        cap_multiplier = 0.0
    elif warnings:
        posture = "LIMIT_DESTINATION"
        cap_multiplier = 0.5
    else:
        posture = "GREEN"
        cap_multiplier = 1.0

    return {
        "mx_family": family,
        "posture": posture,
        "capacity_multiplier": cap_multiplier,
        "holds": holds,
        "warnings": warnings,
        "evidence": evidence,
        "scope": "recipient_mx_family",
    }
