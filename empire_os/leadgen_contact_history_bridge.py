"""Read-only bridge to the EXISTING EmpireOS commercial relationship registry.

The registry provides affirmative prior-contact/opt-out evidence. Missing
history never clears a domain for outreach; only the canonical suppression
governor and founder approval can do that. Registry may be stale.
No private addresses, names, email bodies or thread IDs are returned.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import re
from typing import Any

SCHEMA = "empire.leadgen_contact_history_bridge.v1"
REGISTRY_SCHEMA = "empire.commercial_relationship_registry.v1"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
TECHNICAL_HOSTS = (".ingest.us.sentry.io",)
MAX_RELATIONSHIPS = 3000
MAX_TARGETS = 100


def _date(v: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def build_contact_history_review(
    registry: Mapping[str, Any],
    target_domains: Sequence[str],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (not isinstance(registry, Mapping)
            or registry.get("schema_version") != REGISTRY_SCHEMA
            or str(registry.get("execution_authority")).upper() != "NONE"
            or registry.get("outbound_authorized") is not False):
        raise ValueError("existing_relationship_registry_contract_unverified")
    now = now or datetime.now(timezone.utc)
    stamp = _date(registry.get("generated_at"))
    if not stamp or stamp > now.astimezone(timezone.utc):
        raise ValueError("invalid_existing_relationship_snapshot_timestamp")
    rows = registry.get("relationships")
    if not isinstance(rows, list) or len(rows) > MAX_RELATIONSHIPS:
        raise ValueError("unbounded_existing_relationship_registry")
    if (not isinstance(target_domains, (list, tuple))
            or len(target_domains) > MAX_TARGETS or len(set(target_domains)) != len(target_domains)
            or not all(isinstance(d, str) and DOMAIN.fullmatch(d) for d in target_domains)):
        raise ValueError("unbounded_or_invalid_shortlist")
    wanted = set(target_domains)
    evidence = {}
    for relationship in rows:
        if not isinstance(relationship, Mapping):
            raise ValueError("invalid_existing_relationship_row")
        ids = relationship.get("identity_domains")
        if not isinstance(ids, list) or len(ids) > 30:
            raise ValueError("invalid_existing_relationship_identity_domains")
        matching = wanted.intersection(x for x in ids if isinstance(x, str))
        if not matching:
            continue
        outgoing = _date(relationship.get("last_outbound_at")) if relationship.get("last_outbound_at") else None
        incoming = _date(relationship.get("last_inbound_at")) if relationship.get("last_inbound_at") else None
        if (relationship.get("last_outbound_at") and outgoing is None
                or relationship.get("last_inbound_at") and incoming is None
                or outgoing and outgoing > now.astimezone(timezone.utc)
                or incoming and incoming > now.astimezone(timezone.utc)):
            raise ValueError("relationship_timestamps_untrusted")
        for domain in matching:
            prior = evidence.setdefault(domain, {
                "has_prior_outbound": False, "has_prior_inbound": False,
                "do_not_pursue": False, "last_outbound": None, "last_inbound": None,
                "related_thread_count": 0,
            })
            prior["has_prior_outbound"] |= outgoing is not None
            prior["has_prior_inbound"] |= incoming is not None
            prior["do_not_pursue"] |= relationship.get("do_not_pursue") is True
            prior["related_thread_count"] += 1
            if outgoing and (prior["last_outbound"] is None or outgoing > prior["last_outbound"]):
                prior["last_outbound"] = outgoing
            if incoming and (prior["last_inbound"] is None or incoming > prior["last_inbound"]):
                prior["last_inbound"] = incoming
    result = {}
    counts = {"existing_thread_review": 0, "history_unverified": 0,
              "do_not_pursue": 0, "technical_host_hold": 0, "inbound_review": 0}
    for domain in target_domains:
        row = evidence.get(domain, {})
        if row.get("do_not_pursue"):
            state, next_action = "DO_NOT_PURSUE", "Preserve existing suppression or manual hold"
            counts["do_not_pursue"] += 1
        elif domain.endswith(TECHNICAL_HOSTS):
            state, next_action = "NON_BUYER_TECHNICAL_HOST", "Remove technical ingestion host from commercial targeting"
            counts["technical_host_hold"] += 1
        elif row.get("has_prior_outbound") or row.get("has_prior_inbound"):
            state = "EXISTING_THREAD_REVIEW"
            next_action = (
                "Review existing inbound thread and canonical suppression before any reply draft"
                if row.get("has_prior_inbound")
                else "Review existing contact history and last reply; no duplicate first introduction"
            )
            counts["existing_thread_review"] += 1
            if row.get("has_prior_inbound"):
                counts["inbound_review"] += 1
        else:
            state, next_action = (
                "HISTORY_UNVERIFIED",
                "Check every existing mailbox and canonical suppression before considering new outreach"
            )
            counts["history_unverified"] += 1
        result[domain] = {
            "contact_state": state,
            "existing_thread_review_required": state == "EXISTING_THREAD_REVIEW",
            "last_outbound_observed_at": (
                row["last_outbound"].isoformat() if row.get("last_outbound") else None
            ),
            "last_inbound_observed_at": (
                row["last_inbound"].isoformat() if row.get("last_inbound") else None
            ),
            "historical_relationship_count": row.get("related_thread_count", 0),
            "next_contact_history_action": next_action,
            "canonical_suppression_cleared": False,
            "new_first_touch_authorized": False,
            "followup_authorized": False,
        }
    return {
        "schema_version": SCHEMA,
        "source": "existing_empireos_commercial_relationship_registry",
        "registry_observed_at": stamp.isoformat(),
        "mailbox_snapshot_fresh": registry.get("gmail_snapshot_fresh") is True,
        "history_coverage_complete": False,
        "source_populations_not_merged": True,
        "counts": counts,
        "by_domain": result,
        "canonical_suppression_cleared": False,
        "outbound_authorized": False,
        "execution_authority": "none",
    }
