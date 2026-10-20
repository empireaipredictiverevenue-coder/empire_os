"""Muse organic operations + MCP handoff remain no execution by default."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from empire_os.agents.meta_muse_social_operations_v1 import (
    build_muse_social_operations,review_organic_metrics,MEASUREMENT_SCHEMA,
)
from empire_os.agents.meta_muse_mcp_handoff_v1 import plan_muse_mcp_operations


def test_fourteen_day_cross_platform_draft_and_creative_rights():
    x=build_muse_social_operations(niche="roofing", market="tampa, fl")
    assert x["state"]=="EDITORIAL_SOCIAL_OPERATIONS_DRAFT_ONLY"
    assert x["organic_calendar_days"]==14
    assert x["draft_count"]==14
    assert len({r["id"] for r in x["content_drafts"]})==14
    assert x["reels_with_storyboards"]==4
    assert any(r["platform"]=="facebook" for r in x["content_drafts"])
    assert any(r["platform"]=="instagram" for r in x["content_drafts"])
    assert len(x["keyword_clusters"]["service_and_questions"])>=8
    for row in x["content_drafts"]:
        assert row["publish_state"]=="DRAFT_REQUIRES_EDITORIAL_AND_PLATFORM_APPROVAL"
        assert not row["scheduled_on_meta"]
        assert not row["external_platform_submission"]
        assert not row["metrics_observed"]
    for row in x["content_drafts"]:
        if row["format"]=="instagram_reel":
            assert row["video_brief"]["aspect_ratio"]=="9:16"
            assert not row["video_brief"]["generated_video_file_exists"]
    assert not x["facebook_page_created"] and not x["instagram_account_created"]
    assert not x["pages_connected"]
    assert x["posts_published"]==0 and x["ads_campaigns_created"]==0
    assert x["future_meta_ads"]["approved_spend_usd"]==0
    assert not x["future_meta_ads"]["campaign_created"]


def test_mcp_handoff_does_not_invent_tools_or_connected_accounts():
    x=build_muse_social_operations(niche="hvac",market="phoenix, az")
    h=plan_muse_mcp_operations(x)
    assert h["state"]=="REQUIRES_INDEPENDENT_CONNECTED_MCP_DISCOVERY_AND_APPROVAL"
    assert h["target_provider"]=="metricool"
    assert h["content_calendar_draft_count"]==14
    assert len(h["content_draft_id_digests"])==14
    assert len(h["required_provider_capabilities"])==5
    assert all(r["actual_provider_tool_name"] is None for r in h["required_provider_capabilities"])
    assert not h["account_binding_verified_here"]
    assert h["mcp_calls_executed"]==0 and h["posts_published"]==0
    assert h["ads_spend_cents"]==0
    assert not h["separate_meta_business_assets"]["metricool_page_creation_supported_or_verified"]
    # Fake flags from self-asserted sources may never authenticate a plugin tool.
    y=plan_muse_mcp_operations(x,observed_provider_capabilities={
        "provider":"metricool","tools_discovered":True,"pages_connected":True,
        "admin_approved":True,"publish_approved":True,
    })
    assert y["state"]=="REQUIRES_INDEPENDENT_CONNECTED_MCP_DISCOVERY_AND_APPROVAL"
    assert y["mcp_calls_executed"]==0 and y["posts_published"]==0
    assert not y["account_binding_verified_here"]


def test_mcp_rejects_forged_published_drafts():
    x=build_muse_social_operations(niche="plumbing",market="charlotte, nc")
    x["posts_published"]=1
    assert plan_muse_mcp_operations(x)["state"]=="HOLD"
    y=build_muse_social_operations(niche="plumbing",market="charlotte, nc")
    y["content_drafts"][0]["scheduled_on_meta"]=True
    assert plan_muse_mcp_operations(y)["state"]=="HOLD"


def test_no_third_party_page_impersonation_or_fake_meta_authority():
    assert build_muse_social_operations(
        niche="roofing",market="denver, co",brand="Local Roofing Inc",
    )["state"]=="HOLD"
    assert build_muse_social_operations(
        niche="roofing",market="denver, co",page_connection_authorized=True,
    )["state"]=="HOLD"
    assert build_muse_social_operations(
        niche="solar",market="united kingdom",
    )["state"]=="HOLD"


def test_aggregate_performance_feedback_is_unverified_not_money():
    m={
        "schema_version":MEASUREMENT_SCHEMA,
        "reach":1000,"impressions":1700,"saves":30,"shares":12,
        "posts_published":4,"engaged_sessions":60,"first_party_opt_ins":2,
    }
    result=review_organic_metrics(m)
    assert result["state"]=="UNAUTHENTICATED_AGGREGATE_FEEDBACK"
    assert result["engagement_rate_from_supplied_counts"]==round(42/1700,4)
    assert result["revenue_verified_cents"]==0
    assert not result["provider_data_independently_authenticated"]
    forged=deepcopy(m)
    forged["individual_email"]="test@example.com"
    assert review_organic_metrics(forged)["state"]=="HOLD"
    forged=deepcopy(m)
    forged["first_party_opt_ins"]=61
    assert review_organic_metrics(forged)["state"]=="HOLD"


def test_muse_cli_runs_draft_and_mcp_handoff_without_posting():
    repo=Path(__file__).resolve().parents[1]
    cmd=[
        sys.executable,"-B","-m","scripts.run_meta_market_validation_agent",
        "--report-only","--social-draft-niche","roofing",
        "--social-draft-market","tampa, fl","--mcp-handoff",
    ]
    p=subprocess.run(cmd,cwd=repo,check=False,text=True,capture_output=True,
                     timeout=20,env={**os.environ,"PYTHONPATH":str(repo)})
    assert p.returncode==0,p.stderr
    x=json.loads(p.stdout)
    assert x["social_operations_draft"]["draft_count"]==14
    assert x["social_mcp_handoff"]["mcp_calls_executed"]==0
    assert x["authority"]["publish_or_send"] is False
    assert x["social_operations_draft"]["ad_spend_cents"]==0
