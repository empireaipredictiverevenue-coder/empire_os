"""First-party identity corroboration, not acquisition permission."""
import json

import pytest
from empire_os.tam_source_acquisition_connector import (
    build_first_party_site_review, source_observations,
    validate_scope,
)


def row(entity, prospect, name, website, *, prospect_name=None):
    return {
        "entity_id":entity, "prospect_id":prospect, "sector":"solar",
        "canonical_name":name, "canonical_website":"",
        "prospect_website":website,
        "prospect_name":prospect_name or name,
    }


def evidence(host, name):
    return {
        "ok":True, "final_url":f"https://{host}/",
        "business_names":[name],
        "pages_checked":[{"url":f"https://{host}/","status":200}],
        "addresses":["London, United Kingdom"],
        "emails":["info@not-used.test"],
        "phones":["020 0000 0000"],
    }


def test_exact_first_party_name_is_still_review_only():
    seen=[]
    def probe(url, **kw):
        seen.append((url,kw))
        return evidence("solarbusiness.co.uk","Solar Business Ltd")
    rows=[
        row("a","p1","Solar Business Ltd","https://solarbusiness.co.uk"),
        row("a","p2","Solar Business Ltd","https://solarbusiness.co.uk"),
    ]
    r=build_first_party_site_review(
        targets=rows,max_sites=5,site_probe=probe,
    )
    assert len(seen)==1
    assert seen[0][1]=={
        "max_pages":2,"request_timeout":4.0,
        "time_budget_seconds":10.0,"public_only":True
    }
    assert r["entities_considered"]==1
    assert r["entities_with_unique_business_host"]==1
    assert r["site_probes_attempted"]==1
    assert r["sites_retrieved_from_expected_host"]==1
    assert r["sites_supporting_exact_canonical_name"]==1
    assert r["findings"][0]["linked_prospect_count"]==2
    assert r["findings"][0]["review_state"]=="FIRST_PARTY_NAME_EVIDENCE_REVIEW"
    assert r["findings"][0]["country_explicitly_verified"] is False
    assert r["findings"][0]["canonical_resolution_verified"] is False
    assert r["findings"][0]["prospect_attachment_authorized"] is False
    assert r["findings"][0]["acquisition_appended"] is False
    assert "emails" not in r["findings"][0]
    assert "phones" not in r["findings"][0]
    assert r["database_write"] is False
    assert r["acquisitions_appended"]==0
    assert r["outbound_sent"] is False


def test_redirect_to_unrelated_host_is_not_first_party_proof():
    report=build_first_party_site_review(
        targets=[row("a","p1","Solar Business Ltd","https://solarbusiness.co.uk")],
        site_probe=lambda *a,**k: evidence("other-business.co.uk","Solar Business Ltd"),
    )
    assert report["sites_retrieved_from_expected_host"]==0
    assert report["sites_supporting_exact_canonical_name"]==0
    assert report["findings"][0]["review_state"]=="FIRST_PARTY_PROBE_UNAVAILABLE_OR_UNTRUSTED"
    assert report["findings"][0]["source_url"] is None


def test_invalid_homepage_or_name_does_not_become_identity_proof():
    r=build_first_party_site_review(
        targets=[row("a","p1","Solar Business Ltd","https://solarbusiness.co.uk")],
        site_probe=lambda *a,**k: evidence("solarbusiness.co.uk","Different Brand"),
    )
    assert r["sites_retrieved_from_expected_host"]==1
    assert r["sites_supporting_exact_canonical_name"]==0
    assert r["findings"][0]["review_state"]=="FIRST_PARTY_SITE_OBSERVED_NAME_UNVERIFIED"


def test_mismatched_prospect_names_block_website_probe():
    def fail(*a,**k): raise AssertionError("site must not be probed")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Business Ltd","https://solarbusiness.co.uk",
            prospect_name="Different Company Ltd"),
    ],site_probe=fail)
    assert r["site_probes_attempted"]==0
    assert r["entities_skipped_for_ambiguous_identity_or_domain"]==1


def test_two_domains_on_one_entity_are_not_trusted():
    def fail(*a,**k): raise AssertionError("site must not be probed")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Co Ltd","https://site-one.co.uk"),
        row("a","p2","Solar Co Ltd","https://site-two.co.uk"),
    ],site_probe=fail)
    assert r["site_probes_attempted"]==0
    assert r["entities_skipped_for_ambiguous_identity_or_domain"]==1


def test_shared_website_across_two_entities_blocks_both():
    def fail(*a,**k): raise AssertionError("site must not be probed")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Alpha Ltd","https://one-company.co.uk"),
        row("b","p2","Solar Beta Ltd","https://one-company.co.uk"),
    ],site_probe=fail)
    assert r["site_probes_attempted"]==0
    assert r["entities_skipped_for_ambiguous_identity_or_domain"]==2


def test_social_pages_are_not_independent_company_websites():
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Co Ltd","https://facebook.com/solarbusiness"),
    ],site_probe=lambda *a,**k: {})
    assert r["site_probes_attempted"]==0


def test_public_fetch_errors_fail_closed_without_leaking_details():
    def denied(*a,**k): raise RuntimeError("private network blocked")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Co Ltd","https://one-solar.co.uk"),
    ],site_probe=denied)
    assert r["site_probes_attempted"]==1
    assert r["sites_retrieved_from_expected_host"]==0
    assert "private network" not in json.dumps(r)
    assert r["acquisitions_appended"]==0


def test_five_site_limit_and_deterministic_entity_order():
    seen=[]
    def probe(url,**kw):
        seen.append(url)
        return {"ok":False}
    rows=[
        row(str(i),f"p{i}",f"Solar {i}",f"https://solar-{i}.co.uk")
        for i in range(15)
    ]
    r=build_first_party_site_review(targets=rows,max_sites=5,site_probe=probe)
    assert len(seen)==5
    assert r["site_probes_attempted"]==5
    assert len(r["findings"])==5
    assert r["entities_considered"]==15
    assert r["tam_population_verified"] is False


@pytest.mark.parametrize("size",[0,6,True,"2",None])
def test_invalid_site_limit_refused(size):
    with pytest.raises(ValueError,match="five"):
        build_first_party_site_review(targets=[],max_sites=size,site_probe=lambda *a,**k:{})


def test_source_observations_cannot_fake_first_party_source():
    with pytest.raises(ValueError,match="target-bound"):
        source_observations(
            source="first_party_site",sector="solar",country="GB",
            fetcher=lambda **k:iter([]),
        )


@pytest.mark.parametrize("sector,country",[
    ("roofing","GB"),("solar","US"),("insurance","GB")
])
def test_first_party_scope_restricted_to_solar_gb(sector,country):
    with pytest.raises(ValueError):
        validate_scope(source="first_party_site",sector=sector,country=country,limit=5)


def test_first_party_cli_returns_only_aggregate_counts(monkeypatch, capsys, tmp_path):
    from scripts import run_tam_source_acquisition_connector as cli
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    monkeypatch.setattr(cli,"load_runtime_env",
                        lambda *a,**k:{"EMPIREDB_DSN":"postgresql:///empiredb"})
    monkeypatch.setattr(cli,"canonical_targets",
                        lambda *a,**k:[row("a","p1","Solar Ltd","https://solar.co.uk")])
    def stub(*,targets,max_sites,diagnose_only):
        assert max_sites == 3
        assert diagnose_only is False
        return build_first_party_site_review(
            targets=targets,max_sites=max_sites,
            site_probe=lambda *a,**k:evidence("solar.co.uk","Solar Ltd"),
        )
    monkeypatch.setattr(cli,"build_first_party_site_review",stub)
    monkeypatch.setattr(cli,"save_private",lambda packet:tmp_path/"sensitive.json")
    exit_code=cli.main(["--observe","--source","first_party_site",
       "--sector","solar","--country","GB","--max-source","3"])
    assert exit_code==0
    receipt=json.loads(capsys.readouterr().out)
    assert receipt["sites_supporting_exact_canonical_name"]==1
    assert receipt["country_verified"] is False
    assert receipt["database_write"] is False
    assert receipt["acquisitions_appended"]==0
    assert "canonical_name" not in receipt
    assert "website" not in receipt


@pytest.mark.parametrize("extra",[
    ["--max-source","6"],
    ["--source-page","1"],
    ["--page-count","2"],
    ["--metro","London"]
])
def test_first_party_cli_refuses_unbounded_modes(extra):
    from scripts import run_tam_source_acquisition_connector as cli
    with pytest.raises(SystemExit) as exc:
        cli.main(["--observe","--source","first_party_site",
                  "--sector","solar","--country","GB"]+extra)
    assert exc.value.code==2



@pytest.mark.parametrize("host",[
    "127.0.0.1", "10.1.2.3", "192.0.2.3", "co.uk",
    "printer.local", "service.internal", "site.invalid",
])
def test_invalid_or_nonbusiness_site_hosts_are_never_probed(host):
    def never(*a,**k):
        raise AssertionError("unsafe host must not be fetched")
    report=build_first_party_site_review(
        targets=[row("a","p1","Solar Ltd",f"https://{host}/")],
        site_probe=never,
    )
    assert report["site_probes_attempted"]==0
    assert report["acquisitions_appended"]==0


def test_no_network_diagnostic_emits_precise_shared_host_rejection_counts():
    def forbidden(*a,**kw):
        raise AssertionError("diagnose-only must not fetch a public site")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar A","https://shared-business.co.uk/about"),
        row("b","p2","Solar B","https://shared-business.co.uk/contact"),
        row("c","p3","Solar C","https://unique-business.co.uk/solar"),
        row("d","p4","Solar D",""),
    ],max_sites=5,site_probe=forbidden,diagnose_only=True)
    d=r["eligibility_diagnostic"]
    assert r["diagnose_only"] is True
    assert r["site_probes_attempted"]==0
    assert r["entities_considered"]==4
    assert d["entity_candidates_before_cross_entity_host_check"]==3
    assert d["cross_entity_shared_host_entity_count"]==2
    assert d["cross_entity_shared_host_distinct_count"]==1
    assert d["website_values_with_path"]==3
    assert d["rejection_reasons"]=={
        "BUSINESS_HOST_SHARED_ACROSS_ENTITIES":2,
        "NO_UNAMBIGUOUS_BUSINESS_WEBSITE":1,
    }
    assert r["entities_with_unique_business_host"]==1
    assert r["acquisitions_appended"]==0


def test_deep_path_candidate_can_be_probed_only_from_company_root():
    seen=[]
    def probe(url,**kwargs):
        seen.append(url)
        return evidence("solarco.co.uk","Solar Co")
    r=build_first_party_site_review(targets=[
        row("a","p1","Solar Co","https://solarco.co.uk/contact")
    ],site_probe=probe)
    assert seen==["https://solarco.co.uk/"]
    assert r["sites_supporting_exact_canonical_name"]==1
    assert r["eligibility_diagnostic"]["website_values_with_path"]==1
    assert r["country_verified_from_site"] is False


def test_diagnostic_cli_prohibits_site_network(monkeypatch,capsys,tmp_path):
    from scripts import run_tam_source_acquisition_connector as cli
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    monkeypatch.setattr(cli,"load_runtime_env",
                        lambda *a,**k:{"EMPIREDB_DSN":"postgresql:///empiredb"})
    monkeypatch.setattr(cli,"canonical_targets",lambda *a,**k:[
        row("a","p1","Solar Co","https://example-solar.co.uk/about")
    ])
    def review(*,targets,max_sites,diagnose_only):
        assert diagnose_only is True
        return build_first_party_site_review(
            targets=targets,max_sites=max_sites,diagnose_only=True,
            site_probe=lambda *a,**k:(_ for _ in ()).throw(
                AssertionError("not allowed to access network"))
        )
    monkeypatch.setattr(cli,"build_first_party_site_review",review)
    monkeypatch.setattr(cli,"save_private",lambda packet:tmp_path/"private.json")
    assert cli.main(["--observe","--source","first_party_site",
         "--sector","solar","--country","GB","--diagnose-only",
         "--max-source","5"])==0
    receipt=json.loads(capsys.readouterr().out)
    assert receipt["status"]=="READ_ONLY_FIRST_PARTY_ELIGIBILITY_DIAGNOSTIC"
    assert receipt["site_probes_attempted"]==0
    assert receipt["diagnose_only"] is True
    assert receipt["eligibility_diagnostic"][
        "entity_candidates_before_cross_entity_host_check"]==1
    assert receipt["acquisitions_appended"]==0
    assert receipt["database_write"] is False
    assert "candidate_name" not in receipt


def test_diagnose_flag_refused_for_recc_source():
    from scripts import run_tam_source_acquisition_connector as cli
    with pytest.raises(SystemExit) as exc:
        cli.main(["--observe","--source","recc_solar",
                  "--sector","solar","--country","GB","--diagnose-only"])
    assert exc.value.code==2
