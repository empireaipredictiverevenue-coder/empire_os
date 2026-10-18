"""Pure integration contract: never let synthetic source claims become revenue."""
from copy import deepcopy
from datetime import date
import json

import pytest

from empire_os.search_intelligence.department_integration_review import (
    IntegrationEvidenceHeld, reconcile_department,
)
from scripts import review_seo_department_integrated_20261018 as cli


def evidence():
    return {
        "four": {
            "schema": "empire.discovery.four_surface_readonly.v1",
            "authority": "OBSERVE", "production_mutation": False,
            "seo": {"sitemap_http": 200, "pages": {
                p: {"http": 200, "available": True} for p in (
                    "/commercial","/industries/roofing","/aeo/roofing/DFW/")
            }},
            "aeo": {"answer_engine_citation_verified": "UNKNOWN"},
            "geo": {"external_ai_mentions_or_citations": "UNKNOWN"},
            "a2a": {"no_privileged_actions_exposed": True},
        },
        "organic": {
            "schema_version": "empire.organic_live_release_integrity.v1",
            "mode": "READ_ONLY", "status": "LIVE_BYTES_VERIFIED",
            "file_integrity_pass": True,
            "canonical_source_commit_verified": False,
            "live_campaign_release_verified": False,
            "database_writes_performed_by_review": False,
            "outbound_sent_by_review": False,
            "payment_executed_by_review": False,
        },
        "growth": {
            "schema_version":"empire.marketing_growth.search_department.portfolio_review.v1",
            "canonical_department":"marketing_growth","operating_mode":"OBSERVE",
            "production_write":False, "outbound_or_publication_performed":False,
            "external_requests":False,"credentials_read":False,
            "budget_gbp":0,"campaigns_approved_to_launch":0,
            "campaign_count":2,"desk_count":8,
            "campaigns":[{"status":"RESEARCH_ONLY"},{"status":"RESEARCH_ONLY"}],
        },
        "gsc": {
            "schema_version":"empire.search.first_party_gsc_page_review.v1",
            "source":"google_search_console_page_dimension",
            "mode":"OBSERVE", "page_only_aggregation_not_query_page":True,
            "date_window":["2026-10-08","2026-10-17"],
            "returned_page_rows":28,
            "indexation_verified":False,"commercial_conversion_verified":False,
            "outbound_authorized":False,"publishing_authorized":False,
        },
        "serp_cache": {
            "schema_version":"empire.search_intelligence.serp_cache_inventory.v1",
            "status":"CACHE_INVENTORY_OBSERVED",
            "source":"existing_search_fabric_local_cache","mode":"READ_ONLY",
            "ttl_hours":24,"cache_files_seen":3,
            "cache_envelopes_valid":2,"cache_envelopes_invalid":1,
            "cache_fresh_candidate_count":1,"cache_stale_candidate_count":1,
            "cache_fresh_candidates_by_engine":{"bing_html":1},
            "live_serp_engine_probed":False,
            "external_search_queries_sent":False,"paid_api_calls":0,
            "independent_google_rank_positions_verified":False,
            "cached_engine_positions_are_google_ranks":False,
            "target_buyer_queries_verified":False,
            "customer_records_accessed":False,"database_writes":False,
            "outbound_sent":False,"execution_authority":"NONE",
        },
        "semantic": {
            "schema_version":"live_semantic_site_quality_review.v1",
            "mode":"OBSERVE","source_type":"read_only_public_html",
            "assessed_public_pages":4,"intended_public_pages":4,
            "page_to_static_commercial_form_path_observed":True,
            "editorial_candidate_counts":{
                "EDITORIAL_REVIEW_HVAC_HEAT_PUMP_CONTEXT":1,
                "EDITORIAL_REVIEW_SOLAR_PV_EXPLANATION":1,
            },
            "read_errors":[],"observed_google_indexing":False,
            "submission_executed":False,"crm_receipt_verified":False,
            "revenue_verified":False,"site_mutated":False,
            "paid_api_requests":0,"execution_authority":"none",
        },
        "legacy": {
            "schema_version":"empire.organic_search.gsc_page_legacy_404_review.v1",
            "source":"google_search_console_page_dimension_final",
            "mode":"OBSERVE",
            "window":["2026-10-08","2026-10-17"],
            "returned_page_rows":28,"missing_legacy_page_count":26,
            "missing_legacy_page_impressions":37,
            "missing_legacy_page_clicks":0,
            "returned_page_clicks":1,
            "returned_page_impressions":55,
            "missing_review_categories":{
                "BUYER_INTENT_EDITORIAL_REVIEW":1,
                "EMPIRE_PRODUCT_TOPIC_REVIEW":11,
                "ROOFING_RESEARCH_REVIEW":4,
                "OFF_CORE_RETAIN_404_PENDING_EVIDENCE":10,
            },
            "missing_review_queue":[
                {
                    "path":f"/aeo/example/fixture-{index}/",
                    "review_category":(
                        "BUYER_INTENT_EDITORIAL_REVIEW" if index == 0 else
                        "EMPIRE_PRODUCT_TOPIC_REVIEW" if index < 12 else
                        "ROOFING_RESEARCH_REVIEW" if index < 16 else
                        "OFF_CORE_RETAIN_404_PENDING_EVIDENCE"
                    ),
                    "origin_http_status":404,
                    "page_dimension_impressions":37 if index == 0 else 0,
                    "page_dimension_clicks":0,
                    "redirect_authorized":False,"restore_authorized":False,
                } for index in range(26)
            ],
            "query_page_rows_joined_or_added":False,
            "database_writes":False,"redirect_authorized":False,
            "publication_authorized":False,
        },
    }


def test_all_reviewers_connected_but_actual_search_rank_and_sales_stay_unproven():
    d=reconcile_department(**evidence())
    assert d["status"]=="DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN"
    assert d["owned_seo_aeo_a2a_discovery_http_verified"] is True
    assert d["organic_live_assets_verified"] is True
    assert d["organic_source_committed_verified"] is False
    assert d["live_campaign_measurement_release_verified"] is False
    assert d["gsc_returned_page_rows"]==28
    assert d["legacy_missing_404_count_in_returned_page_sample"]==26
    assert d["gsc_returned_page_sample_clicks"]==1
    assert d["legacy_404_core_topic_editorial_review_count"]==16
    assert d["legacy_404_off_core_retain_404_count"]==10
    assert d["legacy_404_restorations_approved"]==0
    assert d["legacy_404_redirects_approved"]==0
    assert d["gsc_query_and_page_totals_added"] is False
    assert d["gsc_sitewide_traffic_or_indexing_verified"] is False
    assert d["external_ai_answer_citation_verified"] is False
    assert d["external_geo_mentions_verified"] is False
    assert d["search_rankings_verified"] is False
    assert d["buyer_enquiries_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["campaigns_approved_to_launch"]==0
    assert d["zero_spend_gbp"]==0
    assert d["search_fabric_cache_fresh_candidates_24h"]==1
    assert d["search_fabric_cache_invalid_envelopes"]==1
    assert d["live_serp_provider_current_buyer_query_verified"] is False
    assert d["semantic_live_priority_pages_checked"]==4
    assert d["semantic_editorial_review_candidates"]==2
    assert d["semantic_owned_pages_commercial_route_verified"] is True
    assert "SEMANTIC_ORIGINAL_CONTENT_EDITORIAL_REVIEW_PENDING" in d["open_gates"]
    assert d["database_writes"] is False
    assert d["outbound_sent"] is False
    assert "INDUSTRY_CAMPAIGN_RELEASE_NOT_VERIFIED" in d["open_gates"]
    assert "HISTORIC_GSC_404_EDITORIAL_TRIAGE_PENDING" in d["open_gates"]


@pytest.mark.parametrize("kind,field,value,reason",[
    ("four","authority","PUBLISH","FOUR_SURFACE_PROVENANCE_UNVERIFIED"),
    ("four","production_mutation",True,"FOUR_SURFACE_PROVENANCE_UNVERIFIED"),
    ("organic","database_writes_performed_by_review",True,"ORGANIC_INTEGRITY_PROVENANCE_UNVERIFIED"),
    ("organic","status","HOLD_INTEGRITY_DRIFT",None),
    ("growth","campaigns_approved_to_launch",1,"GROWTH_PORTFOLIO_PROVENANCE_UNVERIFIED"),
    ("growth","budget_gbp",2,"GROWTH_PORTFOLIO_PROVENANCE_UNVERIFIED"),
    ("growth","external_requests",True,"GROWTH_PORTFOLIO_PROVENANCE_UNVERIFIED"),
    ("gsc","source","query_page","GSC_PAGE_DIMENSION_UNVERIFIED"),
    ("gsc","outbound_authorized",True,"GSC_PAGE_DIMENSION_UNVERIFIED"),
    ("gsc","page_only_aggregation_not_query_page",False,"GSC_PAGE_DIMENSION_UNVERIFIED"),
    ("semantic","paid_api_requests",1,"SEMANTIC_SITE_SOURCE_UNVERIFIED"),
    ("semantic","site_mutated",True,"SEMANTIC_SITE_SOURCE_UNVERIFIED"),
    ("semantic","revenue_verified",True,"SEMANTIC_SITE_SOURCE_UNVERIFIED"),
    ("legacy","missing_review_queue",[],"LEGACY_EDITORIAL_REVIEW_LEDGER_UNVERIFIED"),
    ("legacy","returned_page_clicks",100,"LEGACY_SAMPLE_TOTALS_CONTRADICTED"),
    ("serp_cache","independent_google_rank_positions_verified",True,
     "SERP_CACHE_PROVENANCE_UNVERIFIED"),
    ("serp_cache","paid_api_calls",1,"SERP_CACHE_PROVENANCE_UNVERIFIED"),
    ("serp_cache","cache_fresh_candidate_count",5,"SERP_CACHE_COUNTS_INCONSISTENT"),
    ("legacy","redirect_authorized",True,"LEGACY_PAGE_REVIEW_UNVERIFIED"),
    ("legacy","database_writes",True,"LEGACY_PAGE_REVIEW_UNVERIFIED"),
    ("legacy","returned_page_rows",27,"INCONSISTENT_PAGE_DIMENSION_SAMPLE"),
    ("legacy","missing_legacy_page_clicks",38,"INCONSISTENT_PAGE_DIMENSION_SAMPLE"),
])
def test_invalid_or_inconsistent_evidence_cannot_be_promoted(kind,field,value,reason):
    e=evidence();e[kind][field]=value
    if reason is None:
        e["organic"]["file_integrity_pass"] = False
        d=reconcile_department(**e)
        assert d["organic_live_assets_verified"] is False
        assert "ORGANIC_LIVE_ASSET_INTEGRITY_HOLD" in d["open_gates"]
    else:
        with pytest.raises(IntegrationEvidenceHeld,match=reason):
            reconcile_department(**e)


def test_a_missing_discovery_page_never_claims_indexation_or_external_visibility():
    e=evidence()
    e["four"]["seo"]["pages"]["/aeo/roofing/DFW/"]={
        "http":404, "available":False
    }
    d=reconcile_department(**e)
    assert d["owned_seo_aeo_a2a_discovery_http_verified"] is False
    assert "OWNED_DISCOVERY_SURFACE_REVIEW_REQUIRED" in d["open_gates"]
    assert d["search_rankings_verified"] is False


def test_absence_of_historical_404_rows_does_not_prove_search_visitors():
    e=evidence()
    e["legacy"]["missing_legacy_page_count"]=0
    e["legacy"]["missing_legacy_page_impressions"]=0
    e["legacy"]["missing_review_queue"]=[]
    e["legacy"]["missing_review_categories"]={}
    d=reconcile_department(**e)
    assert "HISTORIC_GSC_404_EDITORIAL_TRIAGE_PENDING" not in d["open_gates"]
    assert d["gsc_sitewide_traffic_or_indexing_verified"] is False
    assert d["buyer_enquiries_verified"] is False


def test_schema_of_injected_source_is_not_passed_through_to_public_output():
    e=evidence()
    e["growth"]["private_buyer_email"]="not-for-output@example.test"
    e["legacy"]["private_event"]="not-for-output@example.test"
    d=reconcile_department(**e)
    assert "not-for-output@example.test" not in json.dumps(d)


def test_cli_handles_dependency_hold_without_printing_driver_error(monkeypatch,capsys):
    from empire_os.search_intelligence import department_integration_review as unit
    def err(**_):
        raise RuntimeError("SECRET-DO-NOT-DISCLOSE")
    monkeypatch.setattr(unit,"run",err)
    # CLI imports run at module import time, so replace its own fixed reference.
    monkeypatch.setattr(cli,"run",err)
    assert cli.main(["--review-only","--start-date","2026-10-08",
                     "--end-date","2026-10-17"])==2
    d=json.loads(capsys.readouterr().out)
    assert d["status"]=="HELD_UNVERIFIED_DEPENDENCY"
    assert d["reason_code"]=="SEO_DEPARTMENT_READONLY_SOURCE_UNAVAILABLE"
    assert "SECRET" not in json.dumps(d)


def test_cli_requires_explicit_review_only_and_date_pair():
    for args in ([],["--review-only","--start-date","2026-10-08"],
                 ["--review-only","--publish"],
                 ["--review-only","--send"]):
        with pytest.raises(SystemExit):
            cli.main(args)


def test_404_category_totals_cannot_be_invented():
    e=evidence()
    e["legacy"]["missing_review_categories"]["EMPIRE_PRODUCT_TOPIC_REVIEW"] += 1
    with pytest.raises(IntegrationEvidenceHeld,match="LEGACY_EDITORIAL_CATEGORY_COUNT_MISMATCH"):
        reconcile_department(**e)


def test_404_duplicate_page_path_fails_closed():
    e=evidence()
    e["legacy"]["missing_review_queue"][1]["path"] = (
        e["legacy"]["missing_review_queue"][0]["path"])
    with pytest.raises(IntegrationEvidenceHeld,match="LEGACY_EDITORIAL_ENTRY_UNVERIFIED"):
        reconcile_department(**e)


def test_404_ledger_mismatched_impressions_fails_closed():
    e=evidence()
    e["legacy"]["missing_review_queue"][0]["page_dimension_impressions"] += 1
    with pytest.raises(IntegrationEvidenceHeld,match="LEGACY_EDITORIAL_LEDGER_TOTALS_MISMATCH"):
        reconcile_department(**e)


def test_non_core_retained_404_never_authorizes_mass_redirect():
    e=evidence()
    e["legacy"]["missing_review_queue"][16]["redirect_authorized"] = True
    with pytest.raises(IntegrationEvidenceHeld,match="LEGACY_EDITORIAL_ENTRY_UNVERIFIED"):
        reconcile_department(**e)
