"""Scope OpenManus-style discovery jobs to existing A2A owner tickets.

This code does not import/run OpenManus's unrestricted browser/shell. A known
FoundationAgents/OpenManus source snapshot exists on the server, but no
production executor/owner-authorised adapter was verified. Exporting this
job plan is NOT successful external execution or fresh buyer discovery.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from empire_os.a2a_owner_research_protocol_v1 import OUTBOX_SCHEMA
from empire_os.a2a_first_party_recovery_readback_v1 import SCHEMA as READBACK_SCHEMA

SCHEMA = "empire.a2a.openmanus_scoped_owner_research_plan.v1"

PHASES = (
    "PLAN_EXACT_B2B_MARKET_TARGET",
    "DISCOVER_OWNER_APPROVED_PUBLIC_SOURCES",
    "READ_FIRST_PARTY_COMPANY_EVIDENCE",
    "CROSSCHECK_COMPANY_GEO_AND_CANONICAL_DUPLICATES",
    "SEND_SIGNED_EVIDENCE_RECEIPT_TO_EXISTING_OWNER",
)
TOOL_ALLOWLIST = (
    "public_first_party_business_homepage_readonly",
    "approved_official_business_registry_readonly",
    "source_atlas_public_rss_existing_owner",
)


def build_scoped_openmanus_plan(
    pickup: Mapping[str, Any],
    public_readback: Mapping[str, Any],
    *,
    executor_verified_by_owner: bool = False,
) -> dict[str, Any]:
    # Only the existing agent owner can attest and activate the executor.
    # No external actions exist in this bridge even if caller says yes.
    if (not isinstance(pickup, Mapping)
            or pickup.get("schema_version") != OUTBOX_SCHEMA
            or pickup.get("execution_authority") != "NONE"
            or pickup.get("owner_dispatches") != 0
            or pickup.get("messages_sent") != 0):
        raise ValueError("UNTRUSTED_RESEARCH_OWNER_PICKUP")
    if (not isinstance(public_readback, Mapping)
            or public_readback.get("schema_version") != READBACK_SCHEMA
            or public_readback.get("execution_authority") != "NONE"
            or public_readback.get("new_verified_sales_leads") != 0
            or public_readback.get("outbound_sent") != 0):
        raise ValueError("UNTRUSTED_PUBLIC_SITE_READBACK")
    if type(executor_verified_by_owner) is not bool:
        raise ValueError("EXECUTOR_BOOLEAN_REQUIRED")
    buyer_jobs = pickup.get("pickup_by_owner",{}).get("buyer_scout")
    source_jobs = pickup.get("pickup_by_owner",{}).get("community_intent")
    if not isinstance(buyer_jobs,list) or not isinstance(source_jobs,list):
        raise ValueError("UNTRUSTED_OWNER_JOB_LISTS")
    by_target = {}
    for job in buyer_jobs + source_jobs:
        if not isinstance(job, Mapping):
            raise ValueError("INVALID_OWNER_JOB")
        task = job.get("research_request")
        if not isinstance(task, Mapping) or job.get("execution_state") != "PICKUP_AVAILABLE_NOT_DELIVERED":
            raise ValueError("OWNER_JOB_NOT_RESEARCH_ONLY")
        owner = task.get("review_owner")
        target_id = task.get("target_id")
        if not isinstance(target_id,str) or owner not in ("buyer_scout","community_intent"):
            raise ValueError("UNTRUSTED_OPENMANUS_RESEARCH_BINDING")
        slot = by_target.setdefault(target_id,{})
        if owner in slot:
            raise ValueError("DUPLICATE_OWNER_JOB_FOR_TARGET")
        slot[owner]=job
    reports = public_readback.get("market_coverage")
    if not isinstance(reports,Mapping):
        raise ValueError("INVALID_PUBLIC_SOURCE_COVERAGE")
    jobs=[]
    for target, owner_map in sorted(by_target.items()):
        if set(owner_map) != {"buyer_scout","community_intent"}:
            raise ValueError("MISSING_OWNER_FOR_SCOPED_RESEARCH")
        buyer = owner_map["buyer_scout"]["research_request"]
        community = owner_map["community_intent"]["research_request"]
        if buyer.get("sector") != community.get("sector") or buyer.get("market") != community.get("market"):
            raise ValueError("CONFLICTING_OWNER_RESEARCH_TARGETS")
        metro = buyer["market"]
        coverage = reports.get(metro)
        if not isinstance(coverage, Mapping):
            raise ValueError("UNMAPPED_FIRST_PARTY_MARKET")
        signature = sha256((target+"|"+owner_map["buyer_scout"]["ticket_sha256"]+"|"+
                            owner_map["community_intent"]["ticket_sha256"]).encode()).hexdigest()[:24]
        verified_read_receipts = [
            {"public_url": row["source_url"], "site_body_sha256": row["source_sha256_if_http_200"],
             "buyer_verified": False}
            for row in public_readback.get("source_records", [])
            if isinstance(row, Mapping) and row.get("market") == metro
            and row.get("sector") == buyer["sector"]
            and row.get("read_status") == "HTTP_200"
            and row.get("source_sha256_if_http_200")
        ][:3]
        jobs.append({
            "job_id": "openmanus-a2a-research-"+signature,
            "target_id": target,
            "sector": buyer["sector"], "market": metro,
            "owner_ticket_ids": {owner: owner_map[owner]["ticket_id"]
                                 for owner in ("buyer_scout","community_intent")},
            "research_queries_proposed_not_executed": buyer["suggested_research_queries_not_executed"][:3],
            "first_party_site_evidence_reads": coverage.get("successful_site_reads"),
            "first_party_sector_and_region_self_claims": coverage.get("self_described_sector_and_region_matches"),
            "first_party_http200_source_receipts_for_owner_review": verified_read_receipts,
            "source_urls_are_public_evidence_not_personal_contacts": True,
            "phases": list(PHASES),
            "permitted_tool_classes": list(TOOL_ALLOWLIST),
            "maximum_new_public_pages_per_approved_owner_run": 3,
            "max_new_source_domains": 5,
            "non_personal_b2b_only": True,
            "capture_source_receipt_hash_and_timestamp": True,
            "confirm_current_site_terms_and_robots_before_fetch": True,
            "must_validate_real_company_canonical_id": True,
            "must_validate_actual_purchase_need_and_capacity": True,
            "openmanus_unrestricted_shell_allowed": False,
            "openmanus_private_login_or_group_scraping_allowed": False,
            "outbound_messages_allowed": False,
            "production_job_dispatch_performed": False,
            "job_state": "AWAIT_EXISTING_SOURCE_OWNER_ACCEPTANCE",
        })
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "execution_authority": "NONE",
        "openmanus_source_code_reviewed_locally": True,
        "production_openmanus_executor_verified": False,
        "executor_claim_supplied_but_not_authenticated": executor_verified_by_owner,
        "jobs_prepared": len(jobs),
        "jobs_executed": 0,
        "jobs": jobs,
        "source_fetch_owner": "existing_community_intent",
        "buyer_qualification_owner": "existing_buyer_scout",
        "signed_result_owner": "existing_a2a_identity_owner",
        "production_jobs_dispatched": 0, "buyer_leads_created": 0,
        "external_network_requests_performed": 0,
        "commercial_outbound_authorized": False,
        "openmanus_tool_runtime_installed_by_this_module": False,
        "next_gate": "OWNER_VERIFIED_OPENMANUS_EXECUTOR_AND_SIGNED_RESPONSES",
    }
