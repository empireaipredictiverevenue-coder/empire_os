"""Diff local research pick-ups across hourly runs without reissuing work."""
from __future__ import annotations
from typing import Any, Mapping
import re

from empire_os.a2a_owner_research_protocol_v1 import OUTBOX_SCHEMA, OWNERS

SCHEMA = "empire.a2a.owner_pickup_change_tracking.v1"
_HEX = re.compile(r"^[a-f0-9]{24}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _map(value: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    if (not isinstance(value, Mapping) or value.get("schema_version") != OUTBOX_SCHEMA
            or value.get("execution_authority") != "NONE"
            or value.get("owner_dispatches") != 0
            or value.get("messages_sent") != 0):
        raise ValueError("UNTRUSTED_OWNER_PICKUP_SNAPSHOT")
    owners = value.get("pickup_by_owner")
    if not isinstance(owners, Mapping) or set(owners) != set(OWNERS):
        raise ValueError("INVALID_OWNER_PICKUP_OWNERS")
    data = {}
    for owner, items in owners.items():
        if not isinstance(items, list) or len(items) > 10:
            raise ValueError("INVALID_OWNER_PICKUP_ITEMS")
        for x in items:
            if not isinstance(x, Mapping):
                raise ValueError("INVALID_OWNER_PICKUP_RECORD")
            key = x.get("ticket_id")
            digest = x.get("ticket_sha256")
            if not isinstance(key, str) or not _HEX.fullmatch(key):
                raise ValueError("INVALID_OWNER_PICKUP_TICKET")
            if not isinstance(digest, str) or not _SHA.fullmatch(digest):
                raise ValueError("INVALID_OWNER_PICKUP_DIGEST")
            if key in data:
                raise ValueError("DUPLICATE_OWNER_PICKUP_TICKET")
            if x.get("execution_state") != "PICKUP_AVAILABLE_NOT_DELIVERED":
                raise ValueError("UNTRUSTED_OWNER_PICKUP_EXECUTION")
            data[key] = (digest, owner)
    if value.get("pickup_count") != len(data):
        raise ValueError("INVALID_OWNER_PICKUP_COUNT")
    return data


def review_pickup_changes(
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    new = _map(current)
    older = _map(previous) if previous is not None else {}
    added = sorted(set(new) - set(older))
    missing = sorted(set(older) - set(new))
    modified = sorted(k for k in set(new) & set(older) if new[k] != older[k])
    repeat = sorted(k for k in set(new) & set(older) if new[k] == older[k])
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE", "execution_authority": "NONE",
        "current_owner_requests": len(new),
        "new_request_ids_for_owner_pickup": added,
        "changed_request_ids_require_owner_recheck": modified,
        "previously_seen_not_reissued": repeat,
        "previous_request_ids_no_longer_in_current": missing,
        "new_request_count": len(added),
        "changed_request_count": len(modified),
        "unchanged_request_count": len(repeat),
        "no_longer_current_request_count": len(missing),
        "discovery_cycle_did_not_dispatch": True,
        "buyer_leads_created": 0, "messages_sent": 0,
        "owner_acks_created": 0,
    }
