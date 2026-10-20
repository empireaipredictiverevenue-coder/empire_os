"""Browser Use and OpenHands may plan, but never execute through source reports."""
from __future__ import annotations
from copy import deepcopy
import pytest
from empire_os.a2a_optional_source_agents_v1 import review_optional_agents


def sites():
    return {
        "schema_version":"empire.a2a.first_party_source_recovery_review.v1",
        "mode":"OBSERVE","execution_authority":"NONE",
        "new_verified_sales_leads":0,
        "source_records":[
            {"source_url":"https://roofstampa.com/","market":"tampa, fl",
             "read_status":"HTTP_200","buyer_or_lead_verified":False,
             "contact_allowed":False,
             "self_description_matches_trade_and_region":True,
             "scrapling_structured_page_parsed":True,
             "crawl4ai_offline_markdown_extracted":True},
            {"source_url":"https://www.danconservices.com/","market":"nyc",
             "read_status":"ROBOTS_POLICY_HOLD","buyer_or_lead_verified":False,
             "contact_allowed":False,
             "self_description_matches_trade_and_region":False,
             "scrapling_structured_page_parsed":False},
            {"source_url":"https://www.llnygroup.com/","market":"nyc",
             "read_status":"CONTENT_TOO_LARGE","buyer_or_lead_verified":False,
             "contact_allowed":False,
             "self_description_matches_trade_and_region":False,
             "scrapling_structured_page_parsed":False},
        ],
    }


def test_current_sites_not_a_reason_to_launch_browser():
    data=review_optional_agents(sites(),browser_use_installed=True,crawl4ai_installed=True)
    assert data["browser_use_library_installed"]
    assert data["crawl4ai_library_installed"]
    assert data["browser_jobs_prepared"]==0
    assert data["browser_jobs_executed"]==0
    assert not data["browser_use_browser_execution_proven"]
    assert not data["openhands_workspace_contract"]["production_repo_writable"]
    assert data["openhands_workspace_contract"]["workspace_mode"]=="disposable_clone"


def test_valid_approved_js_gap_only_prepares_one_bounded_browser_request():
    source=sites()
    source["source_records"][0].update({
        "self_description_matches_trade_and_region":False,
        "scrapling_structured_page_parsed":False,
        "crawl4ai_offline_markdown_extracted":False,
    })
    result=review_optional_agents(source,browser_use_installed=True,crawl4ai_installed=True)
    assert result["browser_jobs_prepared"]==1
    job=result["browser_jobs"][0]
    assert job["bounded_max_pages"]==1
    assert job["source_owner_approval_required"]
    assert job["no_stealth_or_antibot_bypass"]
    assert not job["no_outbound_messages"] is False
    assert result["browser_jobs_executed"]==0


def test_unsafe_buyer_claim_and_untrusted_workspace_rejected():
    source=sites()
    source["source_records"][0]["buyer_or_lead_verified"]=True
    with pytest.raises(ValueError,match="UNTRUSTED_BROWSER_INPUT"):
        review_optional_agents(source,browser_use_installed=True,crawl4ai_installed=True)
    source=sites()
    source["new_verified_sales_leads"]=1
    with pytest.raises(ValueError,match="UNTRUSTED_PUBLIC_SITE_EVIDENCE"):
        review_optional_agents(source,browser_use_installed=True,crawl4ai_installed=True)


def test_browser_or_openhands_claim_never_grants_authority():
    result=review_optional_agents(sites(),browser_use_installed=True,
                                  crawl4ai_installed=True,
                                  browser_sandbox_verified=True,
                                  openhands_executor_verified=True)
    assert result["browser_sandbox_claim_supplied_but_unverified"]
    assert result["openhands_executor_claim_supplied_but_unverified"]
    assert not result["openhands_code_task_executed"]
    assert result["production_repo_writes"]==0
    assert result["outbound_messages"]==0
