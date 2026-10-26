"""Reconcile the existing partner pilot records with original Gmail metadata.

No mailbox calls, new contacts, automatic sends, buyer terms, campaign activation,
or inferred accepted geography. Original entity/thread identity is separate from
membership in the buyer research cohort. A changed Gmail message ID is only a
review signal, never confirmation that terms were accepted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from empire_os.buyer_qualification_evidence_bridge import _timestamp, DOMAIN, THREAD

GMAIL = Path("runtime/buyer_network_intelligence/gmail_relationship_evidence_latest.json")
GMAIL_SCHEMA = "empire.buyer_mail_relationship_summary.v1"
MAX_PARTNERS = 20
MAX_AGE_SECONDS = 3 * 3600


def read_original_gmail_metadata(root: Path, *, now: datetime) -> tuple[dict, str]:
    path = root / GMAIL
    try:
        stat = path.lstat()
        if (path.is_symlink() or not stat.st_size in range(100, 1_000_001)
                or stat.st_mode & 0o077):
            return {}, "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE"
        doc = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(doc, dict) or doc.get("schema_version") != GMAIL_SCHEMA
                or doc.get("origin") != "connected_gmail_connector_read_only"
                or not isinstance(doc.get("threads"), list)
                or len(doc["threads"]) > 500
                or not isinstance(doc.get("partial_updated_thread_ids"), list)
                or len(doc["partial_updated_thread_ids"]) > 500):
            return {}, "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE"
        refreshed_at = _timestamp(doc.get("partial_update_at"))
        captured_at = _timestamp(doc.get("captured_at"))
        if (refreshed_at is None or captured_at is None
                or not -300 <= (now-refreshed_at).total_seconds() <= MAX_AGE_SECONDS):
            return {}, "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE"
        bridge = doc.get("connected_gmail_bridge")
        if (not isinstance(bridge, dict)
                or bridge.get("read_only") is not True
                or bridge.get("outbound_authorized") is not False
                or bridge.get("execution_authority") != "NONE"
                or bridge.get("schema_version") != "empire.connected_gmail_metadata_bridge.v1"
                or bridge.get("collected_at") != doc["partial_update_at"]):
            return {}, "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE"
        return doc, ("PARTIAL_METADATA_REFRESH_ORIGINAL_THREAD_CAPTURE_OLD"
                     if (now-captured_at).total_seconds() > MAX_AGE_SECONDS
                     else "FULL_GMAIL_CAPTURE_CURRENT_REVIEW_ONLY")
    except (OSError, ValueError, UnicodeError, TypeError):
        return {}, "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE"


def review_partner_replies(registry: dict, gmail: dict,
                           *, cohort_matches: dict[str, dict],
                           prior_message_ids: dict[str, str] | None,
                           gmail_source_state: str) -> tuple[dict, dict[str, str]]:
    """Only original partner records with identical entity, domain and thread."""
    pilots = registry.get("partner_pilot_readiness_queue")
    relationships = registry.get("relationships")
    if not isinstance(pilots, list) or not isinstance(relationships, list):
        return {"status": "PARTNER_SOURCE_UNAVAILABLE", "partners": []}, {}
    if len(pilots) > MAX_PARTNERS or len(relationships) > 500:
        return {"status": "PARTNER_SOURCE_UNAVAILABLE", "partners": []}, {}
    previous = prior_message_ids if isinstance(prior_message_ids, dict) else {}
    if len(previous) > MAX_PARTNERS or any(
        not isinstance(k, str) or not isinstance(v, str) or not THREAD.fullmatch(v)
        for k, v in previous.items()
    ):
        return {"status": "PRIOR_MESSAGE_CHECKPOINT_INVALID", "partners": []}, {}
    by_entity: dict[str, list[dict]] = {}
    for rel in relationships:
        if isinstance(rel, dict) and isinstance(rel.get("entity_key"), str):
            by_entity.setdefault(rel["entity_key"], []).append(rel)
    gmail_by_thread: dict[str, list[dict]] = {}
    if gmail_source_state != "GMAIL_METADATA_MISSING_UNSAFE_OR_STALE":
        for item in gmail.get("threads", []) or []:
            if isinstance(item, dict) and isinstance(item.get("gmail_thread_id"), str):
                gmail_by_thread.setdefault(item["gmail_thread_id"], []).append(item)
    updated_ids: dict[str, str] = {}
    rows: list[dict] = []
    seen_entities: set[str] = set()
    for pilot in pilots:
        if not isinstance(pilot, dict):
            continue
        entity = pilot.get("entity_key")
        if (not isinstance(entity, str) or not 1 <= len(entity) <= 110
                or entity in seen_entities):
            continue
        seen_entities.add(entity)
        related = by_entity.get(entity, [])
        thread = pilot.get("reviewed_gmail_thread_id")
        if (len(related) != 1 or not isinstance(thread, str)
                or not THREAD.fullmatch(thread)):
            continue
        rel = related[0]
        domains = rel.get("identity_domains")
        threads = rel.get("gmail_thread_ids")
        gates = pilot.get("activation_gates")
        intake = pilot.get("single_pass_buyer_intake")
        if (not isinstance(domains, list) or not 1 <= len(domains) <= 20
                or any(not isinstance(x, str) or not DOMAIN.fullmatch(x) for x in domains)
                or not isinstance(threads, list) or thread not in threads
                or not isinstance(gates, dict)
                or any(type(v) is not bool for v in gates.values())
                or not isinstance(intake, dict)
                or pilot.get("execution_authority") != "NONE"
                or pilot.get("outbound_authorized") is not False
                or pilot.get("live_traffic_authorized") is not False
                or rel.get("outbound_authorized") is not False
                or rel.get("commercial_buyer_approved") is not False
                or intake.get("execution_authority") != "NONE"
                or intake.get("outbound_authorized") is not False):
            continue

        linked = any(x.get("entity_key") == entity
                     for x in cohort_matches.values() if isinstance(x, dict))
        gm = gmail_by_thread.get(thread, [])
        partial = set(gmail.get("partial_updated_thread_ids", [])) if gmail else set()
        matched_gmail = (len(gm) == 1 and gm[0].get("entity_key") == entity
                         and thread in partial
                         and set(gm[0].get("identity_domains") or []) == set(domains)
                         and gm[0].get("last_inbound_message_id") == rel.get("last_inbound_message_id"))
        inbound_id = rel.get("last_inbound_message_id")
        valid_inbound = isinstance(inbound_id, str) and THREAD.fullmatch(inbound_id)
        if matched_gmail and valid_inbound:
            prior_id = previous.get(entity)
            reply_transition = (
                "BASELINED_PREEXISTING_INBOUND_NOT_NEW"
                if prior_id is None else
                "MATCHED_INBOUND_MESSAGE_UNCHANGED"
                if prior_id == inbound_id else
                "CHANGED_INBOUND_MESSAGE_ID_REVIEW_REQUIRED"
            )
            updated_ids[entity] = inbound_id
        else:
            reply_transition = "INBOUND_NOT_CONFIRMED_BY_FRESH_GMAIL_METADATA"
            # Preserve the previous checkpoint if a source temporarily ages.
            if entity in previous:
                updated_ids[entity] = previous[entity]
        reviewed = (pilot.get("technical_review_packet") or {}).get("reported_inbound_requirements")
        reviewed = reviewed if isinstance(reviewed, dict) else {}
        reported_grade = reviewed.get("evidence_grade")
        reported_keys = []
        if (matched_gmail and reviewed.get("source_ref") == "gmail:" + str(inbound_id)
                and reported_grade in ("HISTORICAL_REPORTED_UNVERIFIED",
                                       "CURRENT_REPORTED_UNVERIFIED")
                and reviewed.get("commercial_terms_confirmed") is False
                and reviewed.get("agreement_received_or_signed_verified") is False
                and reviewed.get("founder_activation_authorized") is False
                and isinstance(reviewed.get("fields"), dict)
                and len(reviewed["fields"]) <= 20):
            reported_keys = sorted(k for k in reviewed["fields"]
                                   if isinstance(k, str) and re.fullmatch(r"[a-z_]{3,80}", k))
        requested = pilot.get("partner_requirement_evidence_requested")
        requested = requested if isinstance(requested, list) else []
        requested = [v for v in requested if isinstance(v, str)
                     and re.fullmatch(r"[a-z0-9_]{3,100}", v)][:12]
        suppressed = (rel.get("do_not_pursue") is True
                      or bool(rel.get("bounced_addresses"))
                      or rel.get("stage") == "DELIVERY_HOLD")
        intake_next = str(intake.get("next_action") or "")[:100]
        if suppressed:
            next_owner_task = "ORIGINAL_CONTACT_SUPPRESSION_OR_DELIVERY_REVIEW"
        elif reply_transition == "CHANGED_INBOUND_MESSAGE_ID_REVIEW_REQUIRED":
            next_owner_task = "REVIEW_NEW_INBOUND_METADATA_IN_ORIGINAL_GMAIL_THREAD"
        elif intake.get("repeat_full_request_blocked") is True:
            next_owner_task = "WAIT_ORIGINAL_PARTNER_ANSWERS_NO_REPEAT_REQUEST"
        else:
            next_owner_task = "REVIEW_BUYBOX_GAPS_WITH_EXISTING_RELATIONSHIP_OWNER"
        rows.append({
            "entity_key": entity,
            "company": str(pilot.get("company") or "")[:90],
            "identity_domains": sorted(set(domains)),
            "canonical_original_thread_ref": "gmail:" + thread,
            "identity_status": ("ORIGINAL_ENTITY_THREAD_MATCHED_RESEARCH_COHORT"
                                if linked else "ORIGINAL_ENTITY_THREAD_MATCHED_OUTSIDE_RESEARCH_COHORT"),
            "gmail_metadata_state": (gmail_source_state if matched_gmail
                                     else "THREAD_METADATA_NOT_CURRENT_OR_UNMATCHED"),
            "last_inbound_message_ref": "gmail:" + inbound_id if matched_gmail and valid_inbound else None,
            "reply_transition": reply_transition,
            "reported_fields_reviewed_not_accepted": reported_keys,
            "reported_fields_status": (reported_grade if reported_keys else
                                       "NO_EXACT_MESSAGE_BOUND_FIELD_REVIEW"),
            "requirements_requested_still_unverified": requested,
            "open_requirement_count": len(requested),
            "repeat_full_request_blocked": intake.get("repeat_full_request_blocked") is True,
            "original_intake_next_action": intake_next,
            "next_existing_owner_task": next_owner_task,
            "suppression_or_delivery_hold": suppressed,
            "accepted_geo_verified": False,
            "call_lead_criteria_verified": False,
            "operating_hours_caps_verified": False,
            "payable_terms_verified": False,
            "pilot_qualified": False,
            "automated_followup_authorized": False,
            "crm_or_database_writes": False,
        })
    rows.sort(key=lambda x: x["entity_key"])
    return {
        "status": "ORIGINAL_PARTNER_REPLY_METADATA_RECONCILED_REVIEW_ONLY",
        "partners": rows,
        "exact_entity_thread_identities": len(rows),
        "linked_to_original_research_cohort": sum(
            x["identity_status"] == "ORIGINAL_ENTITY_THREAD_MATCHED_RESEARCH_COHORT"
            for x in rows),
        "original_relationships_outside_research_cohort": sum(
            x["identity_status"] == "ORIGINAL_ENTITY_THREAD_MATCHED_OUTSIDE_RESEARCH_COHORT"
            for x in rows),
        "changed_inbound_message_ids_review_only": sum(
            x["reply_transition"] == "CHANGED_INBOUND_MESSAGE_ID_REVIEW_REQUIRED"
            for x in rows),
        "repeat_full_request_already_blocked": sum(
            x["repeat_full_request_blocked"] for x in rows),
        "buyer_accepted_geography_count": 0,
        "buyer_accepted_terms_count": 0,
        "pilot_qualified_count": 0,
        "outbound_authorized": False,
        "no_duplicate_agent_or_scheduler": True,
    }, updated_ids
