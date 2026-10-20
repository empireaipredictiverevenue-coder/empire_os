"""Revived native Social Syndication is only an owned, repeat-safe draft queue."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from empire_os.agents.meta_muse_social_operations_v1 import build_muse_social_operations
from empire_os.agents.meta_muse_social_syndicate_v1 import build_owned_syndication_preview


def _source():
    return build_muse_social_operations(niche="roofing",market="tampa, fl")


def test_owned_social_post_syndicates_all_14_organic_drafts_without_calls():
    x=build_owned_syndication_preview(_source())
    assert x["state"]=="OWNED_SYNDICATION_QUEUE_PREVIEW_ONLY"
    assert x["source_social_draft_count"]==14
    assert x["job_count"]==28
    assert len(x["draft_jobs"])==28
    assert sum(j["platform"]=="facebook" for j in x["draft_jobs"])==14
    assert sum(j["platform"]=="instagram" for j in x["draft_jobs"])==14
    assert sum(j["content_format"]=="reel" for j in x["draft_jobs"])==8
    assert len({j["idempotency_key_sha256"] for j in x["draft_jobs"]})==28
    assert len({j["job_id"] for j in x["draft_jobs"]})==28
    assert all(j["state"]=="DRAFT_NEEDS_CREATIVE_QC_RIGHTS_ACCOUNT_AND_APPROVAL"
               for j in x["draft_jobs"])
    assert all(not j["public_publish_authorized"] for j in x["draft_jobs"])
    assert all(j["actual_mcp_tool_name"] is None for j in x["draft_jobs"])
    assert x["mcp_calls_executed"]==0
    assert x["posts_published"]==0
    assert x["ads_created"]==0 and x["ad_spend_cents"]==0
    assert x["canonical_media_duplicate_guard"]=="empire_os.media_repurposing.content_fingerprint"


def test_stable_jobs_across_runs_and_source_media_not_assumed_cleared():
    a=build_owned_syndication_preview(_source(),original_media_ref="media:owned_film_0001",
                                       original_rights_evidence_refs=("licence:proof_0001",))
    b=build_owned_syndication_preview(_source(),original_media_ref="media:owned_film_0001",
                                       original_rights_evidence_refs=("licence:proof_0001",))
    assert [j["idempotency_key_sha256"] for j in a["draft_jobs"]]==[
        j["idempotency_key_sha256"] for j in b["draft_jobs"]]
    assert all(j["original_source_ref"]=="media:owned_film_0001" for j in a["draft_jobs"])
    assert not a["original_media_rights_verified"]
    assert all(not j["source_media_asset_rendered_and_verified"] for j in a["draft_jobs"])


def test_existing_provider_history_duplicate_held_not_reposted():
    a=build_owned_syndication_preview(_source())
    j=a["draft_jobs"][0]
    old=[{
        "id":"historical-owned-post-01",
        "platform":j["platform"],
        "content_fingerprint":j["source_content_fingerprint_sha256"],
    }]
    b=build_owned_syndication_preview(_source(),prior_items=old)
    assert b["duplicate_risk_jobs_held"]>=1
    assert any(x["state"]=="HOLD_PRIOR_CONTENT_DUPLICATE" for x in b["draft_jobs"])
    assert b["mcp_calls_executed"]==0


def test_no_external_permission_from_self_reported_publishing_flag():
    d=_source()
    d["posts_published"]=1
    assert build_owned_syndication_preview(d)["state"]=="HOLD"
    d=_source()
    d["content_drafts"][0]["scheduled_on_meta"]=True
    assert build_owned_syndication_preview(d)["state"]=="HOLD"
    d=_source()
    d["content_drafts"][0]["id"]=d["content_drafts"][1]["id"]
    assert build_owned_syndication_preview(d)["state"]=="HOLD"


def test_user_supplied_history_and_source_refs_bounded():
    assert build_owned_syndication_preview(_source(),prior_items=[{"id":"bad"}])["state"]=="HOLD"
    assert build_owned_syndication_preview(_source(),original_media_ref="https://random-site/contact?email=abc")["state"]=="HOLD"
    assert build_owned_syndication_preview(_source(),original_rights_evidence_refs=("invalid raw contact text",))["state"]=="HOLD"


def test_existing_muse_cli_renders_owner_poster_but_never_posts():
    repo=Path(__file__).resolve().parents[1]
    cmd=[
        sys.executable,"-B","-m","scripts.run_meta_market_validation_agent",
        "--report-only","--social-draft-niche","roofing",
        "--social-draft-market","tampa, fl",
        "--social-syndicate-preview","--mcp-handoff",
    ]
    r=subprocess.run(cmd,text=True,capture_output=True,check=False,timeout=25,cwd=repo,
                     env={**os.environ,"PYTHONPATH":str(repo)})
    assert r.returncode==0,r.stderr
    x=json.loads(r.stdout)
    assert x["owned_social_syndication_preview"]["job_count"]==28
    assert x["social_mcp_handoff"]["mcp_calls_executed"]==0
    assert x["authority"]["publish_or_send"] is False
    assert x["owned_social_syndication_preview"]["posts_published"]==0
