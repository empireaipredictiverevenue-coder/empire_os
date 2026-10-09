from uuid import uuid4
from empire_os.buyer_acquisition_scout import run_buyer_scout
from empire_os.scout_low_yield_recovery import select_low_yield_canonical_domains

def plan():
    return {"priority_targets":[],"product_priority_targets":[],"icp_priority_targets":[
        {"icp_profile_key":"high_ticket_home_service",
         "research_queries":{"end_service_buyers":["roofing companies"]}}]}

def seeds():
    return [{"id":str(uuid4()),"business_name":f"Westbrook Roofing {i}",
             "website":f"https://roof-{i}.example","niche":"roofing",
             "icp_profile_key":"high_ticket_home_service"} for i in range(5)]

def mock(monkeypatch, hosts):
    monkeypatch.setattr("empire_os.buyer_acquisition_scout.search_domains_parallel",
                        lambda queries,num:{q:hosts for q in queries})
    def probe(url,**kw):
        name="Westbrook Roofing 0"
        return {"ok":True,"canonical_url":url,"final_url":url,
                "title":name,"description":f"{name} website",
                "business_names":[name],"emails":[],"phones":[],"people":[],
                "pages_checked":[{"url":url,"visible_text":name}],
                "evidence_score":0.7}
    monkeypatch.setattr("empire_os.buyer_acquisition_scout.probe_site",probe)

def test_one_search_result_reserves_three_canonical_slots(monkeypatch):
    mock(monkeypatch,["first.example"])
    baselines=[{"website":f"https://partner-{i}.example"} for i in range(7)]
    out=run_buyer_scout(plan(),canonical_seed_records=seeds(),
                        research_seed_records=baselines,
                        low_yield_canonical_limit=3,max_domains=5,max_probes=5)
    assert out["low_yield_canonical_supplement_count"]==3
    assert out["candidate_count"]==5
    assert sum(r["discovery_source"]=="canonical_prospect_seed"
               for r in out["candidates"])==3
    assert not any(r["canonical_identity_verified"] for r in out["candidates"])
    assert out["outbound_sent"] is False
    assert out["execution_authority"]=="none"

def test_legacy_default_keeps_no_supplement(monkeypatch):
    mock(monkeypatch,["first.example"])
    out=run_buyer_scout(plan(),canonical_seed_records=seeds())
    assert out["canonical_seed_domain_count"]==0

def test_three_search_results_disable_supplement(monkeypatch):
    mock(monkeypatch,["one.example","two.example","three.example"])
    out=run_buyer_scout(plan(),canonical_seed_records=seeds(),
                        low_yield_canonical_limit=3)
    assert out["low_yield_canonical_supplement_count"]==0
    assert out["candidate_count"]==3

def test_zero_results_preserve_existing_fallback(monkeypatch):
    mock(monkeypatch,[])
    out=run_buyer_scout(plan(),canonical_seed_records=seeds(),
                        low_yield_canonical_limit=3)
    assert out["canonical_seed_fallback_used"] is True
    assert out["canonical_seed_domain_count"]==5

def test_inputs_necessitate_uuid_and_allowed_company_identity():
    values=seeds()
    values.insert(0,{**values[0],"id":"not-a-uuid"})
    values.insert(0,{**values[0],"icp_profile_key":"invalid_profile"})
    found=select_low_yield_canonical_domains(
        values,search_domains={"one.example"},query_count=1,
        search_enabled=True,limit=3)
    assert found==("roof-0.example","roof-1.example","roof-2.example")

def test_reject_invalid_registered_identity_and_source():
    from empire_os.scout_low_yield_recovery import safe_company_host
    valid=seeds()[0]
    bad=[
        {**valid,"website":"https://roof-0.example:8765"},
        {**valid,"business_name":"Home"},
        {**valid,"icp_profile_key":"untrusted"},
        {**valid,"id":"123"},
    ]
    result=select_low_yield_canonical_domains(
        bad+[valid],search_domains={"first.example"},query_count=1,
        search_enabled=True,limit=3)
    assert result==("roof-0.example",)
    assert safe_company_host("https://www.roof-0.example/about")=="roof-0.example"
    assert safe_company_host("ftp://roof-0.example")==""

def test_weak_search_only_with_active_research():
    values=seeds()
    assert not select_low_yield_canonical_domains(
        values,search_domains={"first.example"},query_count=0,
        search_enabled=True,limit=3)
    assert not select_low_yield_canonical_domains(
        values,search_domains={"first.example"},query_count=1,
        search_enabled=False,limit=3)
    assert not select_low_yield_canonical_domains(
        values,search_domains={"first.example"},query_count=1,
        search_enabled=True,limit=0)
