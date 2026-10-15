"""Read-only, bounded business relationship summary. Not evidence of new replies."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

EXPECTED_SCHEMA = "empire.commercial_relationship_registry.v1"
STAGES = frozenset({
    "RESEARCH_ONLY", "CONTACTED_AWAITING_RESPONSE", "INBOUND_REVIEW_REQUIRED",
    "AWAITING_BUYER", "EVIDENCE_HOLD", "DELIVERY_HOLD",
})


def _parsed(value: Any) -> datetime | None:
    try:
        x = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return x.astimezone(timezone.utc) if x.tzinfo else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def summarize_relationship_registry(
    data: Mapping[str, Any] | None, *, as_of: datetime,
) -> dict[str, Any]:
    if as_of.tzinfo is None:
        raise ValueError("aware clock required")
    now = as_of.astimezone(timezone.utc)
    base = {
        "schema_version": "empire.executive.relationship_registry.v1",
        "mode": "OBSERVE", "status": "UNAVAILABLE", "registry_fresh": False,
        "mailbox_current": False, "new_replies_verified": False,
        "send_authority": False, "revenue_verified": False,
        "total_relationships": None, "counts_by_stage": {},
        "suppression_review_count": None, "review_queue": [],
        "queue_truncated": False,
    }
    if data is None:
        return base
    stamp = _parsed(data.get("generated_at"))
    if (data.get("schema_version") != EXPECTED_SCHEMA
            or data.get("mode") != "OBSERVE"
            or data.get("outbound_authorized") is not False
            or data.get("outbound_sent") is not False
            or data.get("execution_authority") not in ("none", "NONE")
            or not isinstance(data.get("relationships"), list)
            or len(data["relationships"]) > 1000):
        return {**base, "status": "INVALID_HELD"}
    if not stamp or not timedelta(0) <= now - stamp <= timedelta(hours=1):
        return {**base, "status": "STALE_HELD", "generated_at": stamp.isoformat() if stamp else None}
    rows = data["relationships"]
    counts: Counter[str] = Counter()
    cases = []
    seen = set()
    suppressed_count = 0
    for item in rows:
        if not isinstance(item, Mapping):
            return {**base, "status": "INVALID_HELD"}
        name, entity, stage = (
            str(item.get("company") or "").strip(),
            str(item.get("entity_key") or "").strip(),
            str(item.get("stage") or "").strip(),
        )
        if not name or not entity or len(name) > 200 or len(entity) > 200 or stage not in STAGES or entity in seen:
            return {**base, "status": "INVALID_HELD"}
        seen.add(entity)
        counts[stage] += 1
        bounced = item.get("bounced_addresses") or []
        if not isinstance(bounced, list):
            return {**base, "status": "INVALID_HELD"}
        held = item.get("do_not_pursue") is True or bool(bounced)
        if held:
            suppressed_count += 1
        if stage == "RESEARCH_ONLY" and not held:
            continue
        cases.append({
            "company": name, "entity_key": entity, "stage": stage,
            "prior_outbound_observed": bool(item.get("last_outbound_at")),
            "suppression_or_bounce_hold": held,
            "next_review": "NO_CONTACT" if held else "RECONCILE_CURRENT_PARTNER_EVIDENCE",
            "source_ref": f"commercial_registry:{entity}",
            "external_action_authorized": False,
        })
    cases.sort(key=lambda x: (
        not x["suppression_or_bounce_hold"],
        x["stage"] != "INBOUND_REVIEW_REQUIRED",
        x["entity_key"],
    ))
    gmail_time = _parsed(data.get("gmail_snapshot_captured_at"))
    gmail_current = bool(
        data.get("gmail_snapshot_fresh") is True
        and data.get("automatic_live_gmail_ingest_configured") is True
        and gmail_time is not None
        and timedelta(0) <= now - gmail_time <= timedelta(hours=1)
    )
    return {
        **base, "status": "OBSERVE_REVIEW" if gmail_current else "GMAIL_SNAPSHOT_HOLD",
        "registry_fresh": True, "generated_at": stamp.isoformat(),
        "mailbox_current": gmail_current,
        "gmail_snapshot_captured_at": gmail_time.isoformat() if gmail_time else None,
        "total_relationships": len(rows),
        "counts_by_stage": dict(sorted(counts.items())),
        "suppression_review_count": suppressed_count,
        "review_queue": cases[:12],
        "queue_truncated": len(cases) > 12,
    }
