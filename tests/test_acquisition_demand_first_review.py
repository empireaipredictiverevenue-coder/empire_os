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
