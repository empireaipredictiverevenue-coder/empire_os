"""Read-only commercial response holds for *automated* outbound.

Never turn an adverse buyer/publisher reply into a send suggestion.
The source is the existing private, atomically materialised relationship
registry; no new agent, provider, scheduler or authoritative buyer account.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[1]
    / "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
)
DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,250}[a-z0-9])?$")
MAX_REGISTRY_BYTES = 2_000_000
PAID_ONLY_HOLD = "HOLD_PERFORMANCE_PARTNERSHIP_NO_REPEAT_EMAIL"
PAID_ONLY_CONSTRAINT = "SPONSORED_PLACEMENTS_ONLY_REPORTED"


class CommercialOutboundHoldError(RuntimeError):
    """Missing or unsafe commercial state must never grant outbound authority."""


def commercial_outbound_hold(recipient: str, *, path: str | Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    """Return enforced no-send state for the exact recipient domain.

    This remains a *commercial* constraint and not a false unsubscribe: a
    later explicit, founder-reviewed exception needs a separately approved
    process. No override is granted by caller-supplied metadata.
    """
    value = str(recipient or "").strip().lower()
    if value.count("@") != 1 or len(value) > 254:
        raise CommercialOutboundHoldError("invalid_commercial_recipient")
    domain = value.rsplit("@", 1)[-1]
    if not DOMAIN.fullmatch(domain) or domain.startswith(".") or ".." in domain:
        raise CommercialOutboundHoldError("invalid_commercial_recipient_domain")

    source = Path(path)
    try:
        if source.is_symlink() or not source.is_file():
            raise CommercialOutboundHoldError("commercial_review_source_missing_or_unsafe")
        stat = source.stat()
        if (stat.st_size > MAX_REGISTRY_BYTES or stat.st_size == 0
                or stat.st_mode & 0o077):
            raise CommercialOutboundHoldError("commercial_review_source_missing_or_unsafe")
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise CommercialOutboundHoldError("commercial_review_source_unavailable") from exc

    if (not isinstance(payload, dict)
            or payload.get("schema_version") != "empire.commercial_relationship_registry.v1"
            or payload.get("execution_authority") != "NONE"
            or payload.get("outbound_authorized") is not False
            or not isinstance(payload.get("new_engaged_publisher_supply_review_queue"), list)
            or len(payload["new_engaged_publisher_supply_review_queue"]) > 48):
        raise CommercialOutboundHoldError("commercial_review_source_invalid")
    matched = []
    for record in payload["new_engaged_publisher_supply_review_queue"]:
        if not isinstance(record, dict):
            raise CommercialOutboundHoldError("commercial_review_entry_invalid")
        d = record.get("domain")
        if (not isinstance(d, str) or len(d) > 253
                or not DOMAIN.fullmatch(d) or ".." in d
                or record.get("outbound_authorized") is not False
                or record.get("execution_authority") != "NONE"):
            raise CommercialOutboundHoldError("commercial_review_entry_invalid")
        if d != domain:
            continue
        if (record.get("next_action") == PAID_ONLY_HOLD
                and record.get("reported_constraint") == PAID_ONLY_CONSTRAINT):
            matched.append(record)
        elif record.get("next_action") == PAID_ONLY_HOLD:
            raise CommercialOutboundHoldError("commercial_hold_provenance_inconsistent")
    if len(matched) > 1:
        raise CommercialOutboundHoldError("commercial_hold_ambiguous")
    row = matched[0] if matched else None
    if row is not None and (
        not isinstance(row.get("last_reply_id"), str)
        or not re.fullmatch(r"[0-9a-f]{16,32}", row["last_reply_id"])
        or row.get("role_hypothesis") != "TRAFFIC_SUPPLY_HYPOTHESIS_NOT_VERIFIED"
    ):
        raise CommercialOutboundHoldError("commercial_hold_provenance_inconsistent")
    return {
        "schema_version": "empire.commercial_outbound_hold_decision.v1",
        "recipient_domain": domain,
        "blocked": row is not None,
        "reason_code": "PUBLISHER_PAID_ONLY_NO_REPEAT_CONTACT" if row else None,
        "evidence_ref": ("gmail:" + row["last_reply_id"]) if row else None,
        "commercial_role": "PUBLISHER_SUPPLY_HYPOTHESIS" if row else None,
        "send_authorized": False,
    }


def require_no_commercial_hold(recipient: str, *, path: str | Path = DEFAULT_REGISTRY) -> None:
    status = commercial_outbound_hold(recipient, path=path)
    if status["blocked"]:
        raise CommercialOutboundHoldError("commercial_fit_no_repeat_outbound")
