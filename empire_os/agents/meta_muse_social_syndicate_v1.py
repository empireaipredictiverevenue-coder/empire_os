"""EmpireOS-owned social post syndicator + repeat-safe MCP dispatch *preview*.

Revives useful structural patterns from historical Social Syndication via the
existing Media OS duplicate guard and Muse editorial planner. Never imports
historical OAuth, provider-specific upload logic, secrets or credentials.

This module contains no outbound MCP calls. A separate authorised connector
must resolve exact provider tool names, platform account IDs and write receipt
before any real publishing can be attempted.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import re

from empire_os.media_repurposing import content_fingerprint, duplication_guard
from empire_os.agents.meta_muse_social_operations_v1 import SCHEMA as SOURCE_SCHEMA

SCHEMA = "empire.meta_muse_owned_social_syndication.v1"
PLATFORMS = ("facebook", "instagram")
KINDS = {
    "facebook_post": ("facebook", "post"),
    "instagram_carousel": ("instagram", "carousel"),
    "instagram_reel": ("instagram", "reel"),
    "instagram_story": ("instagram", "story"),
}
SYNDICATION = {
    "facebook_post": ("instagram", "carousel"),
    "instagram_carousel": ("facebook", "post"),
    "instagram_reel": ("facebook", "reel"),
    "instagram_story": ("facebook", "story"),
}
REF = re.compile(r"^[a-z0-9][a-z0-9._:-]{5,100}$")
CHANNEL_KIND = {
    ("facebook", "post"), ("facebook", "reel"), ("facebook", "story"),
    ("instagram", "carousel"), ("instagram", "reel"), ("instagram", "story"),
}


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "state": "HOLD",
        "reason": reason, "job_count": 0, "draft_jobs": [],
        "publisher_commands_executed": 0, "mcp_calls_executed": 0,
        "posts_published": 0, "social_accounts_created": 0,
        "ads_created": 0, "ad_spend_cents": 0, "execution_authority": "none",
    }


def build_owned_syndication_preview(
    plan: Mapping[str, Any] | None,
    *,
    prior_items: Sequence[Mapping[str, Any]] = (),
    original_media_ref: str | None = None,
    original_rights_evidence_refs: Sequence[str] = (),
    at: datetime | None = None,
) -> dict[str, Any]:
    """Generate two-platform variants and private review-only scheduling jobs.

    A media reference here is only a reference, not proof footage exists or
    rights are cleared. A duplicate output is held; never silently post it.
    """
    if (not isinstance(plan, Mapping)
            or plan.get("schema_version") != SOURCE_SCHEMA
            or plan.get("state") != "EDITORIAL_SOCIAL_OPERATIONS_DRAFT_ONLY"
            or plan.get("execution_authority") != "NONE"
            or any(plan.get(k)!=0 for k in ("posts_published","ads_campaigns_created","external_actions","ad_spend_cents"))
            or plan.get("facebook_page_created") is not False
            or plan.get("instagram_account_created") is not False):
        return _hold("invalid_source_social_plan")
    source = plan.get("content_drafts")
    if (not isinstance(source, list) or len(source)>31
            or len(source)!=plan.get("draft_count")
            or not isinstance(prior_items, (list, tuple)) or len(prior_items)>500
            or (original_media_ref is not None and (not isinstance(original_media_ref,str) or not REF.fullmatch(original_media_ref)))
            or any(not isinstance(r,str) or not REF.fullmatch(r) for r in original_rights_evidence_refs)
            or len(original_rights_evidence_refs)>30):
        return _hold("untrusted_or_oversized_source_or_lineage")
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("aware_clock_required")

    historic=[]
    for item in prior_items:
        # Historical receipts have to be scoped to a real account by a later
        # authenticated provider reader; this is a conservative cross-account
        # duplicate warning only and isn't authoritative.
        if not isinstance(item, Mapping) or len(str(item))>5000:
            return _hold("untrusted_historical_post")
        if (not isinstance(item.get("id"), str) or not REF.fullmatch(item["id"])
                or not isinstance(item.get("platform"),str)
                or item["platform"] not in PLATFORMS
                or not isinstance(item.get("content_fingerprint"),str)
                or not re.fullmatch(r"[0-9a-f]{64}",item["content_fingerprint"])):
            return _hold("missing_or_invalid_historical_post_fingerprint")
        historic.append(item)
    old_fingerprints={(item["platform"],item["content_fingerprint"]) for item in historic}
    seen_source_ids=set()
    seen_queue_keys=set()
    jobs=[]
    blocked=0
    for row in source:
        if not isinstance(row,Mapping):
            return _hold("invalid_editorial_row")
        rid=row.get("id")
        kind=row.get("format")
        date=row.get("date")
        native=KINDS.get(kind)
        if (not isinstance(rid,str) or not re.fullmatch(r"[a-f0-9]{20}",rid)
                or rid in seen_source_ids or native is None
                or row.get("platform")!=native[0]
                or row.get("publish_state")!="DRAFT_REQUIRES_EDITORIAL_AND_PLATFORM_APPROVAL"
                or row.get("scheduled_on_meta") is not False
                or row.get("external_platform_submission") is not False
                or not isinstance(date,str) or not re.fullmatch(r"\d{4}-\d\d-\d\d",date)
                or not isinstance(row.get("topic"),str) or not isinstance(row.get("hook"),str)
                or not isinstance(row.get("caption_draft"),str)
                or len(row["caption_draft"])>2200):
            return _hold("untrusted_post_payload_or_duplicate_source")
        seen_source_ids.add(rid)
        # Shared original fingerprint follows across syndication, while
        # per-account *job* identity additionally includes platform/format/day.
        fingerprint=content_fingerprint(
            topic=row["topic"], thesis=row["caption_draft"],
            angle=plan["market"], hook=row["hook"],
        )
        options=[(native[0],native[1],"NATIVE"),(*SYNDICATION[kind],"REPURPOSED")]
        for platform,format_name,relation in options:
            key=(platform,format_name,date,rid)
            if key in seen_queue_keys:
                return _hold("duplicated_queue_job")
            seen_queue_keys.add(key)
            idem=sha256(
                f"empire-muse-poster/v1/{platform}/{format_name}/{rid}/{date}".encode()
            ).hexdigest()
            repeated=(platform,fingerprint) in old_fingerprints
            if repeated:
                blocked+=1
            jobs.append({
                "job_id":idem[:24],
                "idempotency_key_sha256":idem,
                "source_draft_id":rid,
                "source_content_fingerprint_sha256":fingerprint,
                "original_source_ref":original_media_ref,
                "original_rights_evidence_refs":list(original_rights_evidence_refs),
                "platform":platform, "content_format":format_name,
                "variant_type":relation,
                "proposed_local_date_no_timezone_or_publish_slot":date,
                "caption_draft":row["caption_draft"],
                "hashtags_draft":row.get("hashtags_draft"),
                "keywords_draft":row.get("recommended_keywords"),
                "source_media_asset_rendered_and_verified":False,
                "media_rights_independently_cleared":False,
                "destination_account_verified":False,
                "editorial_approved":False,
                "provider_permissions_verified":False,
                "existing_provider_schedule_deduped":False,
                "duplicate_risk":repeated,
                "state":(
                    "HOLD_PRIOR_CONTENT_DUPLICATE" if repeated
                    else "DRAFT_NEEDS_CREATIVE_QC_RIGHTS_ACCOUNT_AND_APPROVAL"
                ),
                "mcp_provider_intent":"create_or_update_social_post",
                "actual_mcp_tool_name":None,
                "mcp_tool_call_performed":False,
                "public_publish_authorized":False,
                "on_failure_never_retry_without_provider_receipt_check":True,
            })
    jobs.sort(key=lambda r:(r["proposed_local_date_no_timezone_or_publish_slot"],
                            r["platform"],r["content_format"],r["job_id"]))
    return {
        "schema_version":SCHEMA,
        "state":"OWNED_SYNDICATION_QUEUE_PREVIEW_ONLY",
        "revived_from_historical_design":"83cf4ecd -> 81a9f7f6",
        "canonical_media_duplicate_guard":"empire_os.media_repurposing.content_fingerprint",
        "source_social_draft_count":len(source),
        "job_count":len(jobs),
        "duplicate_risk_jobs_held":blocked,
        "channels":[
            {"platform":"facebook","account_connected":False,"business_owner_verified":False},
            {"platform":"instagram","account_connected":False,"business_owner_verified":False},
        ],
        "original_media_rights_verified":False,
        "provider_schedule_checked_live":False,
        "review_requirements":[
            "verify_social_account_admin_identity_via_connected_provider",
            "check_existing_provider_schedule_and_post_receipts_to_avoid_duplicates",
            "finish_original_creative_with_commercial_media_licences_and_format_qc",
            "select_timezone_and_explicit_per_account_publish_time",
            "obtain_human_approved_editorial_media_destination_and_one_post_scope",
            "perform_exact_discovered_MCP_provider_action_once_then_reconcile_receipt",
            "track_real_reach_and_first_party_opt_in_separately_from_revenue",
        ],
        "draft_jobs":jobs,
        "publisher_commands_executed":0,
        "mcp_calls_executed":0,
        "posts_published":0,
        "social_accounts_created":0,
        "ads_created":0,
        "ad_spend_cents":0,
        "execution_authority":"none",
    }
