"""Read-only join from ORIGINAL buyer relationship/buybox owner to Buyer Team.

Authoritative demand and buyer acceptance are never inferred from a proposed
corridor, a sent request, a website claim or a two-way Gmail thread. Only exact,
unambiguous canonical company-domain and original-thread matches are admitted.
No network calls or writes; all actions remain with their original owner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import re

REGISTRY = Path("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
SCHEMA = "empire.commercial_relationship_registry.v1"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
THREAD = re.compile(r"^[a-f0-9]{12,30}$")
TTL = 3 * 3600

def _timestamp(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return at.astimezone(timezone.utc) if at.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None

def load_registry(root: Path, *, now: datetime) -> tuple[dict, str]:
    path = root / REGISTRY
    try:
        if path.is_symlink() or not 100 <= path.stat().st_size <= 1_200_000:
            return {}, "UNVERIFIED_MISSING_OR_UNSAFE_REGISTRY"
        raw = json.loads(path.read_text(encoding="utf8"))
        at = _timestamp(raw.get("generated_at")) if isinstance(raw, dict) else None
        if (not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA
                or raw.get("mode") != "OBSERVE"
                or raw.get("execution_authority") != "NONE"
                or raw.get("outbound_authorized") is not False
                or raw.get("outbound_sent") is not False
                or raw.get("next_actions_automatic_sends") is not False
                or raw.get("founder_actions_are_draft_only") is not True
                or raw.get("partner_pilot_readiness_is_activation_authority") is not False
                or at is None or not -300 <= (now-at).total_seconds() <= TTL
                or not isinstance(raw.get("relationships"), list)
                or len(raw["relationships"]) > 500
                or not isinstance(raw.get("partner_pilot_readiness_queue"), list)
                or len(raw["partner_pilot_readiness_queue"]) > 50):
            return {}, "UNVERIFIED_MISSING_OR_UNSAFE_REGISTRY"
        return raw, ("PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY"
                     if raw.get("gmail_snapshot_fresh") is not True
                     else "CURRENT_REGISTRY_REVIEW_ONLY")
    except (OSError, ValueError, UnicodeError):
        return {}, "UNVERIFIED_MISSING_OR_UNSAFE_REGISTRY"


def match_partner_buyboxes(raw: dict, *, allowed_domains: set[str],
                           source_state: str) -> dict[str, dict]:
    if (source_state not in ("CURRENT_REGISTRY_REVIEW_ONLY",
                             "PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY")
            or not isinstance(raw.get("relationships"), list)
            or not isinstance(raw.get("partner_pilot_readiness_queue"), list)):
        return {}
    # Domains which occur in multiple relationship identities are ambiguous,
    # even when an entity key or a later record appears to match.
    domain_to_rel: dict[str, list[dict]] = {}
    by_entity: dict[str, list[dict]] = {}
    for rel in raw["relationships"]:
        if not isinstance(rel, dict):
            continue
        key = rel.get("entity_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 110:
            continue
        by_entity.setdefault(key, []).append(rel)
        domains = rel.get("identity_domains")
        if not isinstance(domains, list) or len(domains) > 20:
            continue
        for domain in set(d for d in domains if isinstance(d, str)):
            if DOMAIN.fullmatch(domain) and domain in allowed_domains:
                domain_to_rel.setdefault(domain, []).append(rel)
    matches: dict[str, dict] = {}
    seen_partners: set[str] = set()
    for pilot in raw["partner_pilot_readiness_queue"]:
        if not isinstance(pilot, dict):
            continue
        entity = pilot.get("entity_key")
        if (not isinstance(entity, str) or entity in seen_partners
                or len(by_entity.get(entity, [])) != 1):
            continue
        seen_partners.add(entity)
        rel = by_entity[entity][0]
        thread = pilot.get("reviewed_gmail_thread_id")
        threads = rel.get("gmail_thread_ids")
        gates = pilot.get("activation_gates")
        intake = pilot.get("single_pass_buyer_intake")
        if (not isinstance(thread, str) or not THREAD.fullmatch(thread)
                or not isinstance(threads, list) or thread not in threads
                or not isinstance(gates, dict)
                or any(type(v) is not bool for v in gates.values())
                or not isinstance(intake, dict)
                or pilot.get("execution_authority") != "NONE"
                or pilot.get("outbound_authorized") is not False
                or pilot.get("live_traffic_authorized") is not False
                or intake.get("execution_authority") != "NONE"
                or intake.get("outbound_authorized") is not False
                or rel.get("outbound_authorized") is not False
                or rel.get("commercial_buyer_approved") is not False):
            continue
        # No lower-authority source gets to assert accepted geography,
        # pilot readiness or contractual acceptance.
        if (gates.get("current_target_geography_verified") is True
                and gates.get("buyer_buybox_received_and_verified") is True):
            geography_state = "GEO_GATE_REPORTED_SCOPE_NOT_INDEPENDENTLY_MATCHED"
        else:
            geography_state = "NO_CURRENT_VERIFIED_BUYER_GEO_SCOPE"
        repeat_guard = intake.get("repeat_full_request_blocked") is True
        next_action = intake.get("next_action")
        for domain in rel.get("identity_domains") or []:
            if (domain not in allowed_domains
                    or len(domain_to_rel.get(domain, [])) != 1):
                continue
            if rel.get("do_not_pursue") is True:
                status = "SUPPRESSION_POLICY_HOLD"
            elif source_state == "PARTIAL_GMAIL_SNAPSHOT_REVIEW_ONLY":
                status = "HISTORICAL_THREAD_CONTEXT_SOURCE_REFRESH_REQUIRED"
            elif pilot.get("mailbox_snapshot_fresh") is True and rel.get("gmail_snapshot_fresh") is True:
                status = "CURRENT_THREAD_PENDING_VERIFIED_BUYBOX"
            else:
                status = "THREAD_SOURCE_NOT_CURRENT"
            requested = pilot.get("partner_requirement_evidence_requested")
            requested = requested if isinstance(requested, list) else []
            requirements = [s for s in requested if isinstance(s, str) and
                            re.fullmatch("[a-z0-9_]{3,100}", s)][:12]
            matches[domain] = {
                "source": "original_commercial_relationship_registry",
                "source_state": status,
                "entity_key": entity,
                "original_thread_ref": "gmail:" + thread,
                "relationship_stage": str(rel.get("stage") or "")[:60],
                "requirements_requested_not_verified": requirements,
                "outstanding_requirement_count": len(requirements),
                "full_request_already_known": repeat_guard,
                "next_original_owner_action": (str(next_action)[:100] if
                                               isinstance(next_action, str) else None),
                "geography_state": geography_state,
                "geography_independently_verified": False,
                "buyer_pilot_qualified": False,
                "automatic_followup_authorized": False,
            }
    return matches
