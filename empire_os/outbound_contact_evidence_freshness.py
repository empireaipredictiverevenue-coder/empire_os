"""Freshness and decay policy for outbound recipient/contact evidence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


_DEFAULT_TTL_DAYS = {
    "official_site_current": 14,
    "official_site": 30,
    "public_record": 30,
    "press_release": 60,
    "buyer_stated": 30,
    "provider_event": 14,
    "canonical_commercial_evidence": 90,
}


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_contact_evidence_freshness(
    context: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    source_kind = str(context.get("source_kind") or "").strip().lower()

    verified_at = _parse_ts(
        context.get("verified_at")
        or context.get("observed_at")
    )
    last_success = _parse_ts(context.get("last_successful_delivery_at"))
    hard_bounce_at = _parse_ts(context.get("last_hard_bounce_at"))
    opt_out_at = _parse_ts(context.get("last_opt_out_at"))

    ttl_days_raw = context.get("ttl_days")
    if ttl_days_raw is None:
        ttl_days = _DEFAULT_TTL_DAYS.get(source_kind, 21)
    else:
        ttl_days = max(1, min(int(ttl_days_raw), 365))

    hard_holds: list[str] = []
    warnings: list[str] = []

    if verified_at is None:
        return {
            "decision": "REVERIFY",
            "reason": "verification_timestamp_missing_or_invalid",
            "source_kind": source_kind or None,
            "age_days": None,
            "ttl_days": ttl_days,
            "hard_holds": [],
            "warnings": [],
            "trust_multiplier": 0.0,
            "mutation_authorized": False,
        }

    if hard_bounce_at is not None and hard_bounce_at >= verified_at:
        hard_holds.append("hard_bounce_after_verification")
    if opt_out_at is not None and opt_out_at >= verified_at:
        hard_holds.append("opt_out_after_verification")

    age = timestamp - verified_at
    age_days = max(0.0, age.total_seconds() / 86400.0)
    expiry = verified_at + timedelta(days=ttl_days)

    if timestamp >= expiry:
        decision = "REVERIFY"
        reason = "recipient_evidence_stale"
        trust = 0.25
    else:
        remaining = expiry - timestamp
        remaining_ratio = max(
            0.0,
            remaining.total_seconds()
            / max(1.0, (expiry - verified_at).total_seconds()),
        )
        if remaining_ratio <= 0.20:
            warnings.append("recipient_evidence_near_expiry")
            decision = "VALID"
            reason = "recipient_evidence_near_expiry"
            trust = 0.75
        else:
            decision = "VALID"
            reason = "recipient_evidence_current"
            trust = 1.0

    if last_success is not None and last_success > verified_at:
        # A successful provider delivery can improve confidence in the address
        # being routable, but it never clears suppression/opt-out evidence.
        trust = min(1.0, trust + 0.10)

    if hard_holds:
        decision = "HOLD"
        reason = hard_holds[0]
        trust = 0.0

    return {
        "decision": decision,
        "reason": reason,
        "source_kind": source_kind or None,
        "verified_at": verified_at.isoformat(),
        "age_days": round(age_days, 4),
        "ttl_days": ttl_days,
        "expires_at": expiry.isoformat(),
        "hard_holds": hard_holds,
        "warnings": warnings,
        "trust_multiplier": round(trust, 4),
        "mutation_authorized": False,
    }
