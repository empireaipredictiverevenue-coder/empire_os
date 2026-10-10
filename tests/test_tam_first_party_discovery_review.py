"""Independent first-party website discovery for polluted legacy solar URLs."""
import json

import pytest

from empire_os.tam_source_acquisition_connector import (
    build_first_party_discovery_review, validate_scope, source_observations,
)


def target(entity, name, metro, original):
    return {
        "entity_id":entity,"prospect_id":"p"+entity,
        "canonical_name":name,"canonical_metro":metro,
        "prospect_name":name,"sector":"solar",
        "canonical_website":"","prospect_website":original,
    }


def example_probe(url, **kwargs):
    return {
        "ok":True,
        "final_url":url,
        "domain":url.split("/")[2],
        "title":"Acme Solar Ltd",
        "description":"Acme Solar Ltd provides solar services",
        "business_names":["Acme Solar Ltd"],
        "schema_types":["LocalBusiness"],
        "pages_checked":[{"url":url,"status":200}],
    }


def test_discover_from_search_not_shared_directory_host():
    seen=[]
    def search(query,*,num):
        seen.append(("search",query,num))
        return [{"link":"https://www.source-listings.example/solar/acme","title":"Acme"},
                {"link":"https://acmesolar.co.uk/about","title":"Acme Solar Ltd"}]
    def probe(url,**kwargs):
        seen.append(("site",url,kwargs))
        return example_probe(url,**kwargs)
    rows=[
      target("e1","Acme Solar Ltd","Bristol",
             "https://source-listings.example/solar/acme"),
      target("e2","Bright Solar Ltd","Leeds",
             "https://source-listings.example/solar/bright"),
    ]
    # Search resolves only the one candidate for each; but directory host is
    # globally shared in the source rows and never becomes identity proof.
    def search_one(query,*,num):
        if "Acme" in query:
            return search(query,num=num)
        return [{"link":"https://brightsolar.co.uk/"}]
    def verified(url,**kwargs):
        if "acmesolar.co.uk" in url:
            return example_probe(url,**kwargs)
        result=example_probe(url,**kwargs)
        result["title"]="Bright Solar Ltd"
        result["description"]="Bright Solar Ltd"
        result["business_names"]=["Bright Solar Ltd"]
        return result
    review=build_first_party_discovery_review(
        targets=rows,max_entities=2,searcher=search_one,site_probe=verified,
    )
    assert review["shared_existing_host_count"]==1
    assert review["entities_selected_for_search"]==2
    assert review["website_probes_attempted"]==2
    assert review["verified_company_site_review_count"]==2
    assert all(f["review_state"]=="DISCOVERED_FIRST_PARTY_NAME_CORROBORATION_REVIEW"
               for f in review["findings"])
    assert all(f["linked_prospect_count"]==1 for f in review["findings"])
    assert all(f["proven_country"] is False for f in review["findings"])
    assert review["database_write"] is False
    assert review["acquisitions_appended"]==0
    assert review["outbound_sent"] is False


def test_one_reused_host_is_rejected_not_copied_as_first_party():
    def search(query,*,num):
        return [{"link":"https://source-listings.example/company/acme"}]
    def forbidden(url,**kw):
        raise AssertionError("shared source host must not be probed")
    review=build_first_party_discovery_review(targets=[
        target("e1","Acme Solar Ltd","London","https://source-listings.example/a"),
        target("e2","Bright Solar Ltd","London","https://source-listings.example/b"),
    ],max_entities=2,searcher=search,site_probe=forbidden)
    assert review["website_probes_attempted"]==0
    assert review["verified_company_site_review_count"]==0
    assert review["shared_existing_host_count"]==1


def test_shared_host_from_search_results_across_entities_blocks_all():
    seen=[]
    review=build_first_party_discovery_review(targets=[
        target("e1","Acme Solar Ltd","London",""),
        target("e2","Bright Solar Ltd","London",""),
    ],max_entities=2,
        searcher=lambda q,**k:[{"link":"https://shared-result.co.uk/contact"}],
        site_probe=lambda *a,**k:seen.append("probed"))
    assert seen==[]
    assert review["website_probes_attempted"]==0
    assert all(f["review_state"]=="AMBIGUOUS_OR_MISSING_DISCOVERED_HOST"
               for f in review["findings"])


def test_search_degradation_results_in_unverified_not_fabricated_site():
    review=build_first_party_discovery_review(
        targets=[target("e1","Acme Solar Ltd","London","")],
        searcher=lambda *a,**k:(_ for _ in ()).throw(ConnectionError()),
        site_probe=lambda *a,**k:(_ for _ in ()).throw(AssertionError()),
    )
    assert review["search_errors"]==1
    assert review["website_probes_attempted"]==0
    assert review["acquisitions_appended"]==0


def test_redirect_to_different_host_is_not_verified():
    review=build_first_party_discovery_review(
        targets=[target("e1","Acme Solar Ltd","London","")],
        searcher=lambda *a,**k:[{"link":"https://acmesolar.co.uk"}],
        site_probe=lambda *a,**k:example_probe("https://otherbusiness.co.uk/"),
    )
    assert review["website_probes_attempted"]==1
    assert review["verified_company_site_review_count"]==0
    assert review["findings"][0]["source_url"] is None


def test_search_fabric_results_not_trusted_without_actual_site_name():
    def no_name(url,**kw):
        report=example_probe(url,**kw)
        report["business_names"]=[]
        return report
    review=build_first_party_discovery_review(
        targets=[target("e1","Acme Solar Ltd","London","")],
        searcher=lambda *a,**k:[{"link":"https://acmesolar.co.uk"}],
        site_probe=no_name,
    )
    assert review["verified_company_site_review_count"]==0
    assert review["acquisitions_appended"]==0


def test_search_cap_max_5_and_selector_holds_weak_names():
    queries=[]
    rows=[target(str(i),f"Acme Company {i} Ltd","London","")
          for i in range(15)]
    rows.append(target("xx","Solar","London",""))
    review=build_first_party_discovery_review(targets=rows,
        max_entities=5,searcher=lambda q,**kw:queries.append(q) or [],
        site_probe=lambda *a,**k:{})
    assert review["entities_selected_for_search"]==5
    assert len(queries)==5
    assert review["entity_candidates_available"]==16
    assert review["entities_skipped_by_search_selector"][
        "INSUFFICIENT_DISTINCTIVE_SEARCH_IDENTITY"]==1
    assert review["website_probes_attempted"]==0


@pytest.mark.parametrize("size",[0,6,True,None,-1])
def test_discovery_limit_fail_closed(size):
    with pytest.raises(ValueError,match="five"):
        build_first_party_discovery_review(
            targets=[],max_entities=size,
            searcher=lambda *a,**k:[],
            site_probe=lambda *a,**k:{},
        )


@pytest.mark.parametrize("sector,country",[("solar","US"),("insurance","GB"),("roofing","GB")])
def test_first_party_search_scope_restricted(sector,country):
    with pytest.raises(ValueError):
        validate_scope(source="first_party_search",
                       sector=sector,country=country,limit=3)


def test_first_party_source_observations_cannot_impersonate_search_discovery():
    with pytest.raises(ValueError,match="target-bound"):
        source_observations(
            source="first_party_search",sector="solar",country="GB",
            max_source=1,fetcher=lambda *a,**k:[],
        )


def test_cli_first_party_search_prints_aggregates_not_private_names(monkeypatch,capsys,tmp_path):
    from scripts import run_tam_source_acquisition_connector as cli
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    monkeypatch.setattr(cli,"load_runtime_env",
                        lambda *a,**k:{"EMPIREDB_DSN":"postgresql:///empiredb"})
    monkeypatch.setattr(cli,"canonical_targets",lambda *a,**k:[
        target("e1","Acme Solar Ltd","London","")
    ])
    def review(*,targets,max_entities):
        assert max_entities==3
        return build_first_party_discovery_review(
            targets=targets,max_entities=max_entities,
            searcher=lambda *a,**kw:[],
            site_probe=lambda *a,**kw:{},
        )
    monkeypatch.setattr(cli,"build_first_party_discovery_review",review)
    monkeypatch.setattr(cli,"save_private",lambda packet:tmp_path/"source-private.json")
    assert cli.main(["--observe","--source","first_party_search",
                     "--sector","solar","--country","GB",
                     "--max-source","3"])==0
    stdout=capsys.readouterr().out
    receipt=json.loads(stdout)
    assert receipt["source"]=="first_party_search"
    assert receipt["entities_selected_for_search"]==1
    assert receipt["database_write"] is False
    assert receipt["acquisitions_appended"]==0
    assert receipt["country_verified"] is False
    assert "Acme Solar Ltd" not in stdout


@pytest.mark.parametrize("extra",[
    ["--max-source","6"],["--page-count","2"],
    ["--source-page","1"],["--metro","Bristol"]
])
def test_cli_prevents_broad_search_run(extra):
    from scripts import run_tam_source_acquisition_connector as cli
    with pytest.raises(SystemExit) as exc:
        cli.main(["--observe","--source","first_party_search",
                "--sector","solar","--country","GB"]+extra)
    assert exc.value.code==2



def test_discovered_host_claimed_by_different_entity_is_not_probed():
    calls=[]
    review=build_first_party_discovery_review(targets=[
        target("e1","Acme Solar Ltd","London",""),
        target("e2","Bright Solar Ltd","London","https://acmesolar.co.uk/about"),
    ],max_entities=2,
      searcher=lambda query,**kw:[
        {"link":"https://acmesolar.co.uk"}] if "Acme" in query else [],
      site_probe=lambda *a,**k:calls.append(a))
    assert calls==[]
    assert review["website_probes_attempted"]==0
    assert review["acquisitions_appended"]==0


def test_invalid_search_result_ports_are_skipped_not_crash():
    review=build_first_party_discovery_review(
        targets=[target("e1","Acme Solar Ltd","London","")],
        searcher=lambda *a,**k:[
            {"link":"https://solar.co.uk:badport/"},
            {"link":"https://acmesolar.co.uk/"},
        ],
        site_probe=lambda url,**k:example_probe(url),
    )
    assert review["website_probes_attempted"]==1
    assert review["acquisitions_appended"]==0
