"""MCP-first Muse social operations capability contract (no tool execution).

Metricool can be an MCP-backed provider for supported brand analytics, content
calendar and post workflows once independently connected and authorised.
Creating Meta Business assets still belongs to Meta's documented, approved
account-management routes. This module NEVER invents a connected account,
an executable MCP tool name, a published post or an ad budget.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from empire_os.agents.meta_muse_social_operations_v1 import SCHEMA as SOCIAL_SCHEMA

SCHEMA = "empire.meta_muse_mcp_handoff.v1"
PROVIDER = "metricool"
CAPABILITIES = (
    ("inspect_connected_brands","Read connected Facebook/Instagram brands"),
    ("inspect_social_analytics","Read aggregate performance and account analytics"),
    ("inspect_scheduled_content","Read scheduled posts and publishing calendar"),
    ("inspect_recommended_times","Read provider-recommended posting windows"),
    ("create_or_update_social_post","Draft/schedule supported posts through provider after approval"),
)
# Provider-proven call mapping is populated only by a later real MCP discovery
# and account-connection handshake, not inferred from an installation flag.


def plan_muse_mcp_operations(social_plan: Mapping[str,Any] | None,
                             *, observed_provider_capabilities: Mapping[str,Any] | None = None
                             ) -> dict[str,Any]:
    if (not isinstance(social_plan,Mapping)
            or social_plan.get("schema_version")!=SOCIAL_SCHEMA
            or social_plan.get("state")!="EDITORIAL_SOCIAL_OPERATIONS_DRAFT_ONLY"
            or social_plan.get("posts_published")!=0
            or social_plan.get("ads_campaigns_created")!=0
            or social_plan.get("external_actions")!=0):
        return {
            "schema_version":SCHEMA, "state":"HOLD",
            "reason":"untrusted_social_plan_or_claimed_external_execution",
            "mcp_calls_executed":0, "posts_published":0, "ads_spend_cents":0,
        }
    posts=social_plan.get("content_drafts")
    if (not isinstance(posts,list) or len(posts)>14 or len(posts)!=social_plan.get("draft_count")
            or any(not isinstance(p,Mapping) or p.get("publish_state")!="DRAFT_REQUIRES_EDITORIAL_AND_PLATFORM_APPROVAL"
                   or p.get("scheduled_on_meta") is not False
                   for p in posts)):
        return {
            "schema_version":SCHEMA,"state":"HOLD",
            "reason":"invalid_or_published_content_queue",
            "mcp_calls_executed":0,"posts_published":0,"ads_spend_cents":0,
        }
    # Never transform source claims/brand identifiers into actual MCP tool
    # destinations: actual exact tool schemas and account IDs must be
    # discovered from a connected MCP provider by the owning service.
    observed = observed_provider_capabilities if isinstance(observed_provider_capabilities,Mapping) else {}
    provider_name = observed.get("provider")
    provider_available = provider_name==PROVIDER and observed.get("tools_discovered") is True
    # Even a self-asserted flag does not authenticate any token or admin seat.
    return {
        "schema_version":SCHEMA,
        "state":"REQUIRES_INDEPENDENT_CONNECTED_MCP_DISCOVERY_AND_APPROVAL",
        "target_provider":PROVIDER,
        "provider_installed_in_chatgpt_is_not_authenticated_brand":True,
        "mcp_tool_manifest_independently_verified_here":False,
        "account_binding_verified_here":False,
        "provider_capabilities_self_reported_not_authoritative":provider_available,
        "required_provider_capabilities":[
            {"intent":key,"description":desc,
             "actual_provider_tool_name":None,
             "tool_discovered":False}
            for key,desc in CAPABILITIES
        ],
        "provider_tool_calls_only_after_connection":True,
        "content_calendar_draft_count":len(posts),
        "content_draft_id_digests":[
            sha256(p["id"].encode()).hexdigest()[:16]
            for p in posts if isinstance(p.get("id"),str)
        ],
        "recommended_handoff":[
            "Discover real connected Metricool MCP tools; confirm read-only account/brand list",
            "Read supported Facebook Pages/Instagram professional brand identities and available permissions",
            "Compare creator-owned Page/IG assets, domain, privacy link and editorial ownership",
            "Read analytics, recommendations and current calendar via read-only MCP where available",
            "For posts/Reels: obtain media rights, finished asset, exact destination, review and single-post approval",
            "Request provider write through exact discovered tool only in interactive approved workflow",
            "Reconcile provider post/schedule receipt and failures without duplicate retry",
        ],
        "separate_meta_business_assets":{
            "facebook_page_creation":"META_BUSINESS_ASSET_MANAGEMENT_SEPARATE_AUTHORISATION",
            "instagram_professional_account_setup":"META_BUSINESS_ASSET_MANAGEMENT_SEPARATE_AUTHORISATION",
            "metricool_page_creation_supported_or_verified":False,
            "no_unapproved_account_creation":True,
        },
        "ads":{
            "future_only":True,
            "requires_separate_meta_ads_permissions_account_billing_and_founder_approval":True,
            "approved_spend_usd":0,
            "ad_campaigns_created":0,
            "provider_ads_capability_verified":False,
        },
        "mcp_calls_executed":0,"posts_published":0,
        "reels_published":0,"ads_spend_cents":0,
        "social_account_mutations":0,"database_writes":False,
        "execution_authority":"NONE",
    }
