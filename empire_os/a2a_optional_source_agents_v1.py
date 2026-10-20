"""Optional-source-agent readiness and owner-scoped execution handoff proposals.

There is no implied permission to use a browser, code shell, credentials or
paid provider. Owner approval/sandbox/identity are required before dispatch.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any, Mapping

from empire_os.openhands_workspace_adapter import (
    OpenHandsWorkspaceRequest, build_openhands_workspace_contract,
)

SCHEMA = "empire.a2a.optional_research_agents_readiness.v1"


def review_optional_agents(
    public_sites: Mapping[str,Any],
    *,
    browser_use_installed: bool,
    crawl4ai_installed: bool,
    openhands_executor_verified: bool=False,
    browser_sandbox_verified: bool=False,
) -> dict[str,Any]:
    if (not isinstance(public_sites,Mapping)
            or public_sites.get("schema_version") != "empire.a2a.first_party_source_recovery_review.v1"
            or public_sites.get("execution_authority")!="NONE"
            or public_sites.get("new_verified_sales_leads") != 0):
        raise ValueError("UNTRUSTED_PUBLIC_SITE_EVIDENCE")
    for value in (browser_use_installed,crawl4ai_installed,
                  openhands_executor_verified,browser_sandbox_verified):
        if type(value) is not bool:
            raise ValueError("INVALID_RUNTIME_ASSERTION")
    inputs=public_sites.get("source_records")
    if not isinstance(inputs,list) or len(inputs)>9:
        raise ValueError("UNBOUNDED_PUBLIC_SITES")
    browser_jobs=[]
    for row in inputs:
        if not isinstance(row,Mapping):
            raise ValueError("INVALID_SITE_RECORD")
        url=row.get("source_url")
        fetched=row.get("read_status")=="HTTP_200"
        if (not isinstance(url,str) or not url.startswith("https://")
                or len(url)>180 or row.get("buyer_or_lead_verified") is not False
                or row.get("contact_allowed") is not False):
            raise ValueError("UNTRUSTED_BROWSER_INPUT")
        if (row.get("read_status") in ("ROBOTS_POLICY_HOLD","CONTENT_TOO_LARGE")
                or not fetched):
            # Browser automation NEVER bypasses a denied/oversized source.
            continue
        if (row.get("self_description_matches_trade_and_region") is not True
                and row.get("scrapling_structured_page_parsed") is not True
                and row.get("crawl4ai_offline_markdown_extracted") is not True):
            # A valid HTTP200 source with insufficient static content might
            # require JavaScript, but the source owner must still approve.
            digest=sha256(url.encode()).hexdigest()[:24]
            browser_jobs.append({
                "job_id":"browser-use-approved-source-"+digest,
                "public_source_url":url,
                "objective":"Determine if approved public page is client-side rendered; collect source receipt only",
                "bounded_max_pages":1,
                "source_owner_approval_required":True,
                "sandbox_required":True,
                "disable_social_logins_and_credentials":True,
                "robots_policy_already_checked_by_collector":True,
                "no_stealth_or_antibot_bypass":True,
                "no_outbound_messages":True,
                "state":"NOT_DISPATCHED_PENDING_SOURCE_OWNER_AND_BROWSER_SANDBOX",
            })
    openhands_job=build_openhands_workspace_contract(
        OpenHandsWorkspaceRequest(
            job_id="a2a-search-fabric-provider-health-review",
            objective=("Review degraded official/public Search Fabric queries in a disposable "
                       "clone; propose source-backed health reporting and tests. "
                       "No production configuration or providers activated."),
            allowed_paths=("empire_os/search_fabric/","tests/","docs/commercial/"),
            workspace_mode="disposable_clone",
        )
    )
    return {
        "schema_version":SCHEMA,"mode":"OBSERVE","execution_authority":"NONE",
        "crawl4ai_library_installed":crawl4ai_installed,
        "browser_use_library_installed":browser_use_installed,
        "browser_use_browser_execution_proven":False,
        "browser_sandbox_claim_supplied_but_unverified":browser_sandbox_verified,
        "browser_jobs_prepared":len(browser_jobs),
        "browser_jobs_executed":0,
        "browser_jobs":browser_jobs,
        "openhands_workspace_contract":openhands_job,
        "openhands_code_task_prepared":True,
        "openhands_executor_claim_supplied_but_unverified":openhands_executor_verified,
        "openhands_code_task_executed":False,
        "production_repo_writes":0,
        "source_fetches_performed_by_this_module":0,
        "facebook_instagram_reddit_login_access":False,
        "account_creations":0,"paid_actions":0,"outbound_messages":0,
        "next_gate":"OWNER_AUTHENTICATED_SANDBOX_EXECUTOR_AND_APPROVED_SINGLE_JOB",
    }
