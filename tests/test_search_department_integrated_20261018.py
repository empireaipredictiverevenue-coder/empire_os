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
        "legacy": {
            "schema_version":"empire.organic_search.gsc_page_legacy_404_review.v1",
            "source":"google_search_console_page_dimension_final",
            "mode":"OBSERVE",
            "window":["2026-10-08","2026-10-17"],
            "returned_page_rows":28,"missing_legacy_page_count":26,
            "missing_legacy_page_impressions":37,
            "missing_legacy_page_clicks":0,
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
    assert d["gsc_query_and_page_totals_added"] is False
    assert d["gsc_sitewide_traffic_or_indexing_verified"] is False
    assert d["external_ai_answer_citation_verified"] is False
    assert d["external_geo_mentions_verified"] is False
    assert d["search_rankings_verified"] is False
    assert d["buyer_enquiries_verified"] is False
    assert d["realised_revenue_verified"] is False
    assert d["campaigns_approved_to_launch"]==0
    assert d["zero_spend_gbp"]==0
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
