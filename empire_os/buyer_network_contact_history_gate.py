"""Read-only contact-history guard for buyer-network recommendations.

Discovery evidence is never proof that an entity has not been approached.
Combines the existing commercial relationship registry with founder-confirmed
off-platform enquiries. This module does not send, approve or write to EmpireDB.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import json
import re
import stat

from empire_os.workspace_sent_domain_receipts import (
    WorkspaceSentHistoryError, read_previous,
)


REGISTRY = Path("/srv/empire_os/runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json")
EXTERNAL_CONTACTS = Path("/srv/empire_os/runtime/buyer_network_intelligence/founder_reported_external_contacts_latest.json")
WORKSPACE_SENT = Path("/srv/empire_os/runtime/buyer_network_intelligence/workspace_sent_domain_receipts_latest.json")

FOUNDER_REVIEW = Path("/srv/empire_os/runtime/buyer_network_intelligence/multiformat_publisher_founder_review_latest.json")
GMAIL_ID = re.compile(r"^[0-9a-f]{16,32}$")


def read_confirmed_delivery_failures(path: Path) -> dict[str, dict]:
    """Read a restricted founder-reviewed provider DSN, never infer from SENT.

    An absent optional source is not clearance. A malformed or untrusted source
    fails closed rather than treating hard bounces as successful outreach.
    """
    if not path.exists() and not path.is_symlink():
        return {}
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > 1_000_000 or
            stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise ValueError("FOUNDER_DELIVERY_SOURCE_UNSAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or
                data.get("schema_version") != "empire.buyer_multiformat_founder_review.v1" or
                not isinstance(data.get("companies"), list) or
                len(data["companies"]) > 80):
            raise ValueError("FOUNDER_DELIVERY_SOURCE_SCHEMA_INVALID")
        holds: dict[str, dict] = {}
        for row in data["companies"]:
            if not isinstance(row, dict):
                raise ValueError("FOUNDER_DELIVERY_SOURCE_ROW_INVALID")
            if row.get("provider_delivery_failed") is not True:
                continue
            domain = domain_key(row.get("domain"))
            recipient = str(row.get("delivery_failed_recipient") or "").casefold()
            sent_id = str(row.get("gmail_sent_message_id") or "")
            bounce_id = str(row.get("provider_delivery_failure_message_id") or "")
            if (not domain or domain in holds or
                    recipient != str(row.get("verified_public_contact") or "").casefold() or
                    not recipient.endswith("@" + domain) or
                    row.get("provider_delivery_failure_code") != "550_NO_SUCH_USER_HERE" or
                    row.get("provider_send_confirmed") is not True or
                    row.get("provider_delivery_verified") is not False or
                    row.get("delivery_failed_original_sent_message_id") != sent_id or
                    not GMAIL_ID.fullmatch(sent_id) or
                    not GMAIL_ID.fullmatch(bounce_id) or
                    row.get("outbound_authorized") is not False):
                raise ValueError("FOUNDER_DELIVERY_PROOF_INVALID")
            holds[domain] = {
                "reason": "VERIFIED_PROVIDER_HARD_BOUNCE",
                "delivery_failure_code": "550_NO_SUCH_USER_HERE",
                "gmail_bounce_message_id": bounce_id,
                "failed_recipient": recipient,
            }
        return holds
    except (OSError, UnicodeError, TypeError, AttributeError) as exc:
        raise ValueError("FOUNDER_DELIVERY_SOURCE_UNREADABLE") from exc



def read_founder_reviewed_original_gmail_threads(path: Path) -> dict[str, dict]:
    """Hold repeated first introductions using anchored, owner-reviewed Gmail IDs.

    The primary Gmail importer intentionally covers a bounded set of buyer
    threads. Prior outreach reviewed in Gmail can be held here without
    claiming mailbox-wide completeness or sending authority.
    """
    # Reuse the same private-file and schema checks as hard-bounce evidence.
    read_confirmed_delivery_failures(path)
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("FOUNDER_PRIOR_GMAIL_SOURCE_UNREADABLE") from exc
    prior: dict[str, dict] = {}
    for row in data["companies"]:
        if (row.get("existing_inbound_message_id") is None and
                row.get("existing_sent_message_id") is None):
            continue
        domain = domain_key(row.get("domain"))
        thread_id = str(row.get("existing_thread_id") or "")
        inbound = str(row.get("existing_inbound_message_id") or "")
        outbound = str(row.get("existing_sent_message_id") or "")
        recipient = str(row.get("verified_public_contact") or "").casefold()
        if (not domain or domain in prior or not recipient.endswith("@" + domain)
                or not GMAIL_ID.fullmatch(thread_id)
                or not GMAIL_ID.fullmatch(inbound)
                or not GMAIL_ID.fullmatch(outbound)
                or row.get("provider_send_confirmed") is not True
                or row.get("outbound_authorized") is not False
                or row.get("publisher_approval_verified") is not False):
            raise ValueError("FOUNDER_PRIOR_GMAIL_EVIDENCE_INVALID")
        prior[domain] = {
            "source": "FOUNDER_REVIEWED_ORIGINAL_PERSONAL_GMAIL_THREAD",
            "thread_id": thread_id,
            "last_outbound_message_id": outbound,
            "original_inbound_message_id": inbound,
        }
    return prior


def domain_key(value: object) -> str:
    return str(value or "").strip().lower().rstrip(".").removeprefix("www.")


def load_context(registry_path: Path = REGISTRY, external_path: Path = EXTERNAL_CONTACTS,
                 workspace_path: Path = WORKSPACE_SENT,
                 founder_review_path: Path | None = None) -> dict:
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
    workspace_reciprocal = {}
    workspace_source_available = False
    try:
        workspace = read_previous(workspace_path)
        if workspace is not None:
            workspace_rows = {row["domain"]: row for row in workspace["domains"]}
            workspace_reciprocal = {
                row["domain"]: row
                for row in workspace.get("reciprocal_threads", [])
            }
            workspace_source_available = True
    except WorkspaceSentHistoryError:
        pass
    # Derive the companion review source from the supplied registry directory,
    # so isolated test registries never load production owner data.
    if founder_review_path is None:
        founder_review_path = registry_path.parent / FOUNDER_REVIEW.name
    try:
        delivery_holds = read_confirmed_delivery_failures(founder_review_path)
        prior_founder_gmail = read_founder_reviewed_original_gmail_threads(founder_review_path)
        delivery_source_safe = True
    except ValueError:
        delivery_holds = {}
        prior_founder_gmail = {}
        delivery_source_safe = False
    return {
        "available": delivery_source_safe,
        "confirmed_delivery_holds": delivery_holds,
        "prior_founder_gmail": prior_founder_gmail,
        "founder_review_delivery_source_safe": delivery_source_safe,
        "relationships": relationships,
        "workspace_sent": workspace_rows,
        "workspace_reciprocal": workspace_reciprocal,
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
    workspace_reciprocal = context.get("workspace_reciprocal", {}).get(key) or {}
    confirmed_bounce = context.get("confirmed_delivery_holds", {}).get(key) or {}
    prior_founder_thread = context.get("prior_founder_gmail", {}).get(key) or {}
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
    elif confirmed_bounce:
        state, action = "DELIVERY_HOLD", "NO_RETRY_VERIFIED_HARD_BOUNCE_VERIFY_OFFICIAL_ALTERNATIVE"
    elif bounced:
        state, action = "DELIVERY_HOLD", "VERIFY_DIFFERENT_DELIVERY_CHANNEL"
    elif sent:
        state, action = "ALREADY_CONTACTED", "REVIEW_PRIOR_OUTBOUND_BEFORE_FOLLOW_UP"
    elif prior_founder_thread:
        state, action = "FOUNDER_REVIEWED_PRIOR_GMAIL_THREAD", "REVIEW_ORIGINAL_GMAIL_THREAD_NO_DUPLICATE_FIRST_INTRO"
    elif workspace_reciprocal:
        state, action = "WORKSPACE_RECIPROCAL_THREAD_OBSERVED", "REVIEW_EXISTING_TWO_WAY_WORKSPACE_THREAD_FOR_PILOT_FIT"
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
        "workspace_reciprocal_metadata_observed": bool(workspace_reciprocal),
        "workspace_provider_inbound_observed_at": workspace_reciprocal.get("inbound_at"),
        "workspace_history_source_available": context.get("workspace_source_available", False),
        "founder_external_contact": have_form,
        "thread_count": len(threads),
        "bounced_addresses": sorted(set(bounced)),
        "confirmed_hard_bounce": bool(confirmed_bounce),
        "founder_reviewed_original_gmail_thread": bool(prior_founder_thread),
        "founder_reviewed_gmail_thread_id": prior_founder_thread.get("thread_id"),
        "confirmed_hard_bounce_code": confirmed_bounce.get("delivery_failure_code"),
        "last_outbound_at": relation.get("last_outbound_at") or workspace_sent.get("last_sent_at"),
        "last_inbound_at": relation.get("last_inbound_at"),
        "registry_stage": relation.get("stage"),
        "outbound_authorized": False,
        "source": context.get("source", "UNAVAILABLE"),
    }
