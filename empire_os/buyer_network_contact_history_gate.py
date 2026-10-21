"""Read-only contact-history guard for buyer-network recommendations.

Discovery evidence is never proof that an entity has not been approached.
Combines the existing commercial relationship registry with founder-confirmed
off-platform enquiries. This module does not send, approve or write to EmpireDB.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json

from empire_os.workspace_sent_domain_receipts import (
    WorkspaceSentHistoryError, read_previous,
)


REGISTRY = Path("/srv/empire_os/runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
EXTERNAL_CONTACTS = Path("/srv/empire_os/runtime/buyer_network_intelligence/founder_reported_external_contacts_latest.json")
WORKSPACE_SENT = Path("/srv/empire_os/runtime/buyer_network_intelligence/workspace_sent_domain_receipts_latest.json")


def domain_key(value: object) -> str:
    return str(value or "").strip().lower().rstrip(".").removeprefix("www.")


def load_context(registry_path: Path = REGISTRY, external_path: Path = EXTERNAL_CONTACTS,
                 workspace_path: Path = WORKSPACE_SENT) -> dict:
    """Fail closed when a source cannot be read or has the wrong schema."""
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        external = json.loads(external_path.read_text(encoding="utf-8"))
        if (
            registry.get("schema_version") != "empire.commercial_relationship_registry.v1"
            or not isinstance(registry.get("relationships"), list)
            or external.get("schema_version") != "empire.founder_reported_external_contacts.v1"
            or not isinstance(external.get("observations"), list)
        ):
            raise ValueError("contact_history_source_schema_invalid")
    except (OSError, ValueError, TypeError, AttributeError):
        return {"available": False, "relationships": {}, "observations": {},
                "gmail_snapshot_fresh": False, "source": "UNAVAILABLE"}

    relationships: dict[str, dict] = {}
    for item in registry["relationships"]:
        if not isinstance(item, dict):
            continue
        for identity in [item.get("entity_key"), *(item.get("identity_domains") or [])]:
            key = domain_key(identity)
            if key:
                relationships[key] = item
    observations: dict[str, dict] = {}
    for item in external["observations"]:
        if isinstance(item, dict):
            key = domain_key(item.get("domain"))
            if key:
                observations[key] = item
    # The optional Workspace receipt feed is independently protected. Missing
    # coverage is UNKNOWN, never proof a domain has not been contacted.
    workspace_rows = {}
    workspace_source_available = False
    try:
        workspace = read_previous(workspace_path)
        if workspace is not None:
            workspace_rows = {row["domain"]: row for row in workspace["domains"]}
            workspace_source_available = True
    except WorkspaceSentHistoryError:
        pass
    return {
        "available": True,
        "relationships": relationships,
        "workspace_sent": workspace_rows,
        "workspace_source_available": workspace_source_available,
        "observations": observations,
        "gmail_snapshot_fresh": registry.get("gmail_snapshot_fresh") is True,
        "source": "COMMERCIAL_REGISTRY_AND_FOUNDER_EXTERNAL_CONTACTS",
        "registry_generated_at": registry.get("generated_at"),
    }


def review(domain: str, context: Mapping) -> dict:
    """Conservative identity-level state; safe even with stale Gmail snapshots."""
    key = domain_key(domain)
    relation = context.get("relationships", {}).get(key) or {}
    observation = context.get("observations", {}).get(key) or {}
    workspace_sent = context.get("workspace_sent", {}).get(key) or {}
    have_relation = bool(relation)
    have_form = bool(observation)
    threads = relation.get("gmail_thread_ids") or []
    bounced = relation.get("bounced_addresses") or []
    sent = bool(threads or relation.get("last_outbound_at"))
    inbound = bool(relation.get("last_inbound_at"))
    stale = context.get("gmail_snapshot_fresh") is not True

    if context.get("available") is not True:
        state, action = "SOURCE_UNAVAILABLE", "HOLD_AND_RECONCILE_CONTACT_HISTORY"
    elif relation.get("do_not_pursue") is True:
        state, action = "DO_NOT_PURSUE", "NO_CONTACT"
    elif have_form:
        state, action = "FOUNDER_FORM_SUBMITTED", "FOLLOW_UP_VIA_VERIFIED_EXISTING_CHANNEL"
    elif inbound:
        if bounced:
            state, action = "EXISTING_CONVERSATION_PARTIAL_BOUNCE", "REVIEW_EXISTING_THREAD_AVOID_BOUNCED_ADDRESS"
        else:
            state, action = "EXISTING_CONVERSATION", "REVIEW_EXISTING_THREAD_AND_TERMS"
    elif bounced:
        state, action = "DELIVERY_HOLD", "VERIFY_DIFFERENT_DELIVERY_CHANNEL"
    elif sent:
        state, action = "ALREADY_CONTACTED", "REVIEW_PRIOR_OUTBOUND_BEFORE_FOLLOW_UP"
    elif workspace_sent:
        state, action = "WORKSPACE_SENT_ALREADY_CONTACTED", "REVIEW_WORKSPACE_THREAD_NO_DUPLICATE_INTRO"
    elif have_relation:
        state, action = "DISCOVERED_NO_CONFIRMED_CONTACT", "RECONCILE_FORMS_AND_APPLICATIONS"
    else:
        state, action = "UNKNOWN_HISTORY", "RECONCILE_IDENTITY_AND_CONTACT_SOURCES"

    return {
        "state": state,
        "next_action": action,
        "history_verified_complete": not stale and bool(context.get("available")),
        "gmail_snapshot_fresh": not stale,
        "known_relationship": have_relation,
        "workspace_sent_metadata_observed": bool(workspace_sent),
        "workspace_history_source_available": context.get("workspace_source_available", False),
        "founder_external_contact": have_form,
        "thread_count": len(threads),
        "bounced_addresses": sorted(set(bounced)),
        "last_outbound_at": relation.get("last_outbound_at") or workspace_sent.get("last_sent_at"),
        "last_inbound_at": relation.get("last_inbound_at"),
        "registry_stage": relation.get("stage"),
        "outbound_authorized": False,
        "source": context.get("source", "UNAVAILABLE"),
    }
