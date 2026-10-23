from datetime import datetime, timezone
from hashlib import sha256
import pytest
from empire_os.acquisition_demand_first_review import (
    demand_first_tasks, screen_original_requirement,screen_candidates_against_canonical_qualification
)
NOW=datetime(2026,10,23,10,tzinfo=timezone.utc)
BASE={
    "company_website":"https://firm.co.uk",
    "source_url":"https://firm.co.uk/procurement/request-2026",
    "published_at":"2026-10-20T11:30:00+00:00",
    "excerpt":"Request for proposals from external vendors to undertake a technical SEO audit for our website.",
}
CATALOG={"generated_at":NOW.isoformat(),"products":[{"product_code":"technical_search_audit",
          "active":True,"catalog_state":"VERIFIED","version_state":"VERIFIED","binding_terms_ready":True}]}


def test_company_owned_source_still_requires_owner():
    r=screen_original_requirement(**BASE,now=NOW,catalog=CATALOG)
    assert r["status"]=="ORIGINAL_BUYER_REQUEST_REQUIRES_OWNER_ATTESTATION"
    assert "technical_search_audit" in r["product_hypotheses"]
    assert r["buyer_request_verified"] is False
    assert r["outbound_authorized"] is False


def test_hiring_never_buyer_request():
    r=screen_original_requirement(**{**BASE,"excerpt":"We are hiring a technical SEO agency manager. Apply for this role."},now=NOW,catalog=CATALOG)
    assert r["status"]=="HIRING_OR_SELLER_CONTENT"


def test_third_party_identity_mismatch():
    r=screen_original_requirement(**{**BASE,"source_url":"https://somewhere.com/firm.co.uk"},now=NOW,catalog=CATALOG)
    assert r["status"]=="UNVERIFIED_SOURCE_OWNERSHIP"


def test_undated_rejected():
    r=screen_original_requirement(**{**BASE,"published_at":None},now=NOW,catalog=CATALOG)
    assert r["status"]=="UNDATED_OR_STALE_SOURCE"


def test_canonical_promotion_denied_even_with_original_request():
    r=screen_candidates_against_canonical_qualification(
      candidates=[{"prospect_ref":"p1","company":"Firm",**{k:v for k,v in BASE.items() if k!="excerpt"}, "original_excerpt":BASE["excerpt"]}],catalog=CATALOG,now=NOW)
    assert r["source_candidates_for_owner_attestation"]==1
    assert r["canonical_qualified"]==0
    assert r["outbound_authorized"] is False


def test_existing_500_pool_balanced_and_not_contact_ready():
    a=[]
    for i in range(9):
        a.append({"company":f"Firm{i}","yc_profile":f"https://www.ycombinator.com/companies/firm{i}",
                  "website":f"https://firm{i}.com", "research_segment":"Marketing" if i<7 else "Finance",
                  "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED","approval_state":"RESEARCH_ONLY"})
    ref=sha256(a[0]["yc_profile"].encode()).hexdigest()[:24]
    r=demand_first_tasks(a,excluded_prospect_refs={ref},limit=6)
    assert r["new_company_research_count"]==6
    assert r["previously_reviewed_count"]==1
    assert set(q["niche"] for q in r["next_company_reviews"]) == {"Marketing","Finance"}
    assert not r["outbound_authorized"]


def test_circuit_open_does_not_search_or_conflate_unknown_with_no_demand():
    from empire_os.acquisition_demand_first_review import discover_original_requirement_candidates
    tasks=demand_first_tasks([{"company":"Firm","yc_profile":"https://www.ycombinator.com/companies/firm",
          "website":"https://firm.co.uk", "research_segment":"Marketing",
          "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
          "approval_state":"RESEARCH_ONLY"}], excluded_prospect_refs=set())
    def must_not_call(*args, **kwargs):raise AssertionError("search circuit open")
    r=discover_original_requirement_candidates(
        research_queue=tasks,provider_state={"last_state":"CIRCUIT_OPEN","circuit_open":True},
        lookup=must_not_call)
    assert r["status"]=="SEARCH_PROVIDER_UNAVAILABLE_NOT_NO_BUYING_DEMAND"
    assert r["unsearched_companies"]==1
    assert r["search_queries_attempted"]==0


def test_search_only_retains_original_company_domain_and_never_promotes():
    from empire_os.acquisition_demand_first_review import discover_original_requirement_candidates
    tasks=demand_first_tasks([{"company":"Firm","yc_profile":"https://www.ycombinator.com/companies/firm",
          "website":"https://firm.co.uk", "research_segment":"Marketing",
          "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
          "approval_state":"RESEARCH_ONLY"}], excluded_prospect_refs=set())
    r=discover_original_requirement_candidates(
        research_queue=tasks, provider_state={"last_state":"HEALTHY","circuit_open":False},
        lookup=lambda query, num:{"search_operational_status":"RECOVERED","organic":[
            {"link":"https://not-firm.co.uk/seo-rfp"},
            {"link":"https://firm.co.uk/procurement/seo-rfp"}]})
    assert r["searched_companies"]==1
    assert len(r["original_source_candidates"])==1
    assert r["original_source_candidates"][0]["source_url"]=="https://firm.co.uk/procurement/seo-rfp"
    assert not r["original_source_candidates"][0]["buyer_request_verified"]
    assert r["buyer_requests_verified"]==0


def test_expired_circuit_half_open_gets_one_guarded_probe():
    from empire_os.acquisition_demand_first_review import discover_original_requirement_candidates
    tasks=demand_first_tasks([
        {"company":f"Company{i}", "yc_profile":f"https://www.ycombinator.com/companies/company{i}",
         "website":f"https://company{i}.co.uk", "research_segment":"Research",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"} for i in range(3)
    ], excluded_prospect_refs=set())
    calls=[]
    def unavailable(query, num):
        calls.append(query)
        return {"organic":[], "search_operational_status":"CIRCUIT_OPEN",
                "searchParameters":{"search_state":"PROVIDER_DEGRADED"}}
    r=discover_original_requirement_candidates(
       research_queue=tasks, provider_state={"last_state":"CIRCUIT_OPEN","circuit_open":False},
       lookup=unavailable)
    assert len(calls)==1
    assert r["searched_companies"]==1
    assert r["unsearched_companies"]==2
    assert r["status"]=="SEARCH_PROVIDER_FAILED_REMAINDER_UNSEARCHED"
    assert r["buyer_requests_verified"]==0


def test_stale_results_only_one_query_and_never_verified():
    from empire_os.acquisition_demand_first_review import discover_original_requirement_candidates
    tasks=demand_first_tasks([
        {"company":f"Company{i}", "yc_profile":f"https://www.ycombinator.com/companies/company{i}",
         "website":f"https://company{i}.co.uk", "research_segment":"Research",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"} for i in range(3)
    ], excluded_prospect_refs=set())
    def stale(query, num):
        return {"organic":[{"link":"https://company0.co.uk/old-tender"}],
                "search_operational_status":"DEGRADED_WITH_LAST_KNOWN_GOOD",
                "searchParameters":{"search_state":"STALE_RESULTS"}}
    r=discover_original_requirement_candidates(
       research_queue=tasks,provider_state={"last_state":"HEALTHY","circuit_open":False},lookup=stale)
    assert r["search_queries_attempted"]==1
    assert r["stale_discovery_only"] is True
    assert all(not item["buyer_request_verified"] for item in r["original_source_candidates"])
    assert r["status"]=="STALE_DISCOVERY_ONLY_ORIGINAL_VERIFICATION_REQUIRED"


def test_unknown_search_status_fails_closed():
    from empire_os.acquisition_demand_first_review import discover_original_requirement_candidates
    tasks=demand_first_tasks([
        {"company":"Test", "yc_profile":"https://www.ycombinator.com/companies/test",
         "website":"https://test.co.uk", "research_segment":"Research",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"}], excluded_prospect_refs=set())
    r=discover_original_requirement_candidates(
       research_queue=tasks, provider_state={"last_state":"HEALTHY","circuit_open":False},
       lookup=lambda *a,**kw:{"organic":[]})
    assert r["status"]=="SEARCH_PROVIDER_FAILED_REMAINDER_UNSEARCHED"


def test_owned_site_probe_does_not_claim_purchasing_authority():
    from empire_os.acquisition_demand_first_review import review_original_company_pages
    tasks=demand_first_tasks([
        {"company":"Firm","yc_profile":"https://www.ycombinator.com/companies/firm",
         "website":"https://firm.co.uk", "research_segment":"Services",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"}],excluded_prospect_refs=set())
    calls=[]
    def source_probe(url,**kwargs):
        calls.append(kwargs)
        return {"ok":True,"final_url":"https://firm.co.uk/",
                "pages_checked":[{"url":"https://firm.co.uk/procurement",
                          "visible_text":"Request for proposals from independent agencies for marketing services."}]}
    result=review_original_company_pages(research_queue=tasks,probe_site=source_probe)
    assert calls[0]["public_only"] is True
    assert calls[0]["page_priority"]=="commercial"
    assert result["company_sites_observed"]==1
    assert result["original_language_candidates_for_owner_review"]==1
    evidence=result["records"][0]["original_source_candidates"][0]
    assert evidence["buyer_request_verified"] is False
    assert evidence["date_published_verified"] is False
    assert not result["outbound_authorized"]


def test_cross_domain_redirect_cannot_promote_original_company_evidence():
    from empire_os.acquisition_demand_first_review import review_original_company_pages
    tasks=demand_first_tasks([
        {"company":"Firm","yc_profile":"https://www.ycombinator.com/companies/firm",
         "website":"https://firm.co.uk", "research_segment":"Services",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"}],excluded_prospect_refs=set())
    r=review_original_company_pages(research_queue=tasks,
       probe_site=lambda u,**k:{"ok":True,"final_url":"https://unrelated.biz/",
             "pages_checked":[{"url":"https://unrelated.biz/rfp","visible_text":"Request for proposals"}]})
    assert r["company_sites_observed"]==0
    assert r["original_language_candidates_for_owner_review"]==0



def test_reachable_site_without_pages_is_not_counted_as_reviewed():
    from empire_os.acquisition_demand_first_review import review_original_company_pages
    tasks=demand_first_tasks([
        {"company":"Firm","yc_profile":"https://www.ycombinator.com/companies/firm",
         "website":"https://firm.co.uk", "research_segment":"Services",
         "verification_status":"public_directory_only","buyer_intent":"UNVERIFIED",
         "approval_state":"RESEARCH_ONLY"}],excluded_prospect_refs=set())
    r=review_original_company_pages(research_queue=tasks,
       probe_site=lambda u,**k:{"ok":True,"final_url":"https://firm.co.uk/",
                                       "pages_checked":[]})
    assert r["company_sites_observed"]==0
    assert r["total_original_pages_observed"]==0
    assert r["records"][0]["status"]=="SITE_REACHABLE_WITHOUT_REVIEWED_PAGES"
