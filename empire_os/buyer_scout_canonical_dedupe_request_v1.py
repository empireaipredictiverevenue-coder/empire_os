"""Bounded read-only canonical EmpireDB request contract for the existing Scout.

Prepare exactly scoped public company-domain questions for the authorised CRM
owner. Never query, import or persist CRM people, contacts or suppression data.
An unexecuted request is not a negative duplicate check or contact clearance.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping
import re

SCHEMA = "empire.buyer_scout.canonical_identity_lookup_request.v1"
SOURCE_SCHEMA = "empire.buyer_scout.source_verification_queue.v1"
DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
TASK = re.compile(r"^[0-9a-f]{24}$")
ALLOWED_MARKETS = {"tampa, fl", "little rock, ar", "nyc"}
ALLOWED_SECTORS = {"roofing", "hvac", "general_contractor"}


def prepare_canonical_lookup_requests(queue: Mapping[str, Any]) -> dict[str, Any]:
    """Return no PII and zero verified identities; fail closed on source drift."""
    if (not isinstance(queue, Mapping)
            or queue.get("schema_version") != SOURCE_SCHEMA
            or queue.get("mode") != "OBSERVE"
            or queue.get("execution_authority") != "NONE"
            or queue.get("owner") != "existing_buyer_scout"
            or queue.get("canonical_crm_records_created") != 0
            or queue.get("verified_revenue_buyers") != 0
            or queue.get("outbound_messages_sent") != 0
            or queue.get("tasks_dispatched_to_live_buyer_scout") != 0
            or queue.get("search_api_results_persisted") is not False):
        raise ValueError("UNTRUSTED_SOURCE_QUEUE_OR_AUTHORITY")
    ready = queue.get("ready_first_party_verification_tasks")
    held = queue.get("held_site_tasks")
    history = queue.get("historical_official_company_context")
    if (not isinstance(ready, list) or len(ready) > 9
            or not isinstance(held, list) or len(held) > 9
            or not isinstance(history, list) or len(history) > 40
            or queue.get("ready_first_party_verification_count") != len(ready)
            or queue.get("held_site_count") != len(held)
            or queue.get("historical_official_context_count") != len(history)):
        raise ValueError("UNBOUNDED_OR_INCONSISTENT_QUEUE")
    requests: list[dict[str, Any]] = []
    keys: set[str] = set()
    for row in ready:
        if not isinstance(row, Mapping):
            raise ValueError("UNTRUSTED_QUEUE_ROW")
        host = row.get("public_company_domain")
        ticket = row.get("stable_review_task_id")
        digest = row.get("source_content_sha256")
        market = row.get("market")
        sector = row.get("sector")
        if (not isinstance(host, str) or not DOMAIN.fullmatch(host)
                or not isinstance(ticket, str) or not TASK.fullmatch(ticket)
                or market not in ALLOWED_MARKETS or sector not in ALLOWED_SECTORS
                or (market, sector) not in {
                    ("tampa, fl","roofing"),
                    ("little rock, ar","hvac"),
                    ("nyc","general_contractor"),
                }
                or row.get("state") != "OWNER_REVIEW_NOT_DELIVERED"
                or row.get("contact_allowed") is not False
                or row.get("can_create_customer") is not False
                or row.get("commercial_claims_verified") is not False
                or row.get("requires_canonical_empiredb_duplicate_and_suppression_check") is not True
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
                or host in keys):
            raise ValueError("INVALID_OR_DUPLICATE_CANONICAL_LOOKUP_TARGET")
        keys.add(host)
        requests.append({
            "request_id": sha256(("empiredb-exact-company-domain:"+host).encode()).hexdigest()[:24],
            "public_company_domain": host,
            "source_worklist_task_id": ticket,
            "source_document_sha256": digest,
            "market": market,
            "sector": sector,
            "selector": "EXACT_NORMALIZED_PUBLIC_COMPANY_DOMAIN",
            "scope": [
                "PROSPECT_WEBSITE_DOMAIN_MATCH",
                "BUYER_COMPANY_DOMAIN_MATCH",
                "EXISTING_RELATIONSHIP_OR_SUPPRESSION_STATUS",
            ],
            "fetch_contact_persons": False,
            "return_email_addresses": False,
            "return_phone_numbers": False,
            "do_not_infer_contact_clearance_from_no_match": True,
            "canonical_read_status": "AWAITING_AUTHORIZED_OWNER_EXECUTION",
            "match_state": "UNKNOWN_NOT_CHECKED",
            "can_send_message": False,
        })
    return {
        "schema_version": SCHEMA,
        "execution_authority": "NONE",
        "mode": "OBSERVE",
        "data_owner": "existing_canonical_empiredb_crm_owner",
        "lookup_request_count": len(requests),
        "lookup_requests": requests,
        "held_site_tasks_excluded": len(held),
        "historical_permit_company_names_excluded": len(history),
        "canonical_database_read_performed": False,
        "canonical_lookup_results_verified": 0,
        "canonical_no_match_claims": 0,
        "outreach_authorized": False,
        "crm_writes": 0,
        "outbound_sent": 0,
        "buyer_purchase_intent_verified": 0,
        "next_gate": "AUTHENTICATED_READ_ONLY_EMPIREDB_OWNER_AND_EXACT_DOMAIN_RECONCILIATION",
    }
