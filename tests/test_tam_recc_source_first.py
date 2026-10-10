"""Genuine public RECC source-first evidence, no contaminated legacy-identity imports."""
from types import SimpleNamespace
import json

import pytest

from empire_os.tam_source_acquisition_connector import (
    build_recc_source_first_review, validate_scope, source_observations,
)

BASE="https://www.recc.org.uk/scheme/members/"
LISTING='''<html><a href="/scheme/members/acme-solar">Acme Solar Ltd</a>
<a href="/scheme/members/bright-solar">Bright Solar Ltd</a></html>'''


def member(name,url,website,postcode="LS1 1AA",phone="0113 1234567",
           country_code="GB",source="recc_solar",niche="solar"):
    return SimpleNamespace(name=name,url=url,source=source,
         country_code=country_code,niche=niche,metro="United Kingdom",
         phone=phone,state="",language_code="en-GB",
         source_language="en-GB",timezone="Europe/London",
         details="Public solar PV scheme membership",
         lead_score=85,
         raw={"business_website":website,"postcode":postcode})


def site(url, business_name="Acme Solar Ltd"):
    return {
        "ok":True,"requested_url":url,"final_url":url,
        "domain":url.split("/")[2],"title":business_name,
        "description":business_name+" operates solar installation services",
        "business_names":[business_name],
        "schema_types":["LocalBusiness"],
        "pages_checked":[{"url":url,"status":200}],
    }


def test_true_source_first_recc_member_and_site_results_in_review_only():
    calls=[]
    def detail(name,url):
        return member(name,url,"https://acmesolar.co.uk/" if "acme" in url
                      else "https://brightsolar.co.uk/")
    def probe(url,**kwargs):
        calls.append((url,kwargs))
        return site(url,"Acme Solar Ltd" if "acmesolar.co.uk" in url
                    else "Different Trading Name")
    data=build_recc_source_first_review(
        max_members=2,max_site_probes=2,
        listing_fetch=lambda url:LISTING,
        detail_fetch=detail,site_probe=probe,
    )
    assert data["members_listed"]==2
    assert data["canonical_acquisition_previews"]==2
    assert data["public_sites_probed"]==2
    assert data["first_party_identity_supported_review_count"]==1
    assert data["member_postcodes_present"]==2
    assert data["database_queries"]==0
    assert data["database_writes"]==0
    assert data["prospects_created"]==0
    assert data["acquisitions_appended"]==0
    assert data["outbound_sent"] is False
    assert data["existing_canonical_duplicate_check_performed"] is False
    assert data["company_identity_not_automatically_promoted"] is True
    assert data["findings"][0]["state"]=="RECC_AND_FIRST_PARTY_IDENTITY_SUPPORTED_REVIEW"
    assert data["findings"][0]["source_acquisition_appended"] is False
    assert data["findings"][0]["specific_prospect_binding_verified"] is False
    assert data["findings"][0]["recc_member_source_url"]==BASE+"acme-solar"
    assert len(data["findings"][0]["original_source_fingerprint"])==64
    assert data["findings"][0]["public_postcode_from_recc"]=="LS1 1AA"
    assert calls[0][1]=={
        "max_pages":1,"request_timeout":4.0,
        "time_budget_seconds":8.0,"public_only":True,
    }


def test_source_first_never_copies_recc_source_to_prospect_website(monkeypatch):
    from empire_os import prospect_ingest
    original=prospect_ingest.prepare_candidate
    prep=[]
    def checked(x):
        payload=original(x)
        prep.append(payload)
        return payload
    monkeypatch.setattr(prospect_ingest,"prepare_candidate",checked)
    build_recc_source_first_review(
        max_members=1,max_site_probes=1,
        listing_fetch=lambda url:LISTING,
        detail_fetch=lambda name,url:member(name,url,"https://acmesolar.co.uk/"),
        site_probe=lambda url,**kw:site(url),
    )
    assert len(prep)==1
    assert prep[0]["evidence"]["source_url"]==BASE+"acme-solar"
    assert prep[0]["evidence"]["locale"]["country_code"]=="GB"
    assert "website" not in prep[0]["prospect"]


def test_shared_business_domain_across_recc_member_records_never_probed():
    calls=[]
    data=build_recc_source_first_review(
        max_members=2,max_site_probes=2,
        listing_fetch=lambda url:LISTING,
        detail_fetch=lambda name,url:member(name,url,"https://sharedsolar.co.uk/"),
        site_probe=lambda url,**kw:calls.append(url),
    )
    assert calls==[]
    assert data["public_sites_probed"]==0
    assert data["first_party_identity_supported_review_count"]==0
    assert data["review_holds"]["COMPANY_DOMAIN_SHARED_ACROSS_RECC_MEMBERS"]==2
    assert data["acquisitions_appended"]==0


def test_member_country_contract_mismatch_is_excluded():
    data=build_recc_source_first_review(
        max_members=2,max_site_probes=2,
        listing_fetch=lambda url:LISTING,
        detail_fetch=lambda name,url:member(name,url,"https://solar.co.uk/",
                                            country_code="US"),
        site_probe=lambda *a,**k:(_ for _ in ()).throw(
            AssertionError("never probe non-GB member"))
    )
    assert data["canonical_acquisition_previews"]==0
    assert data["public_sites_probed"]==0
    assert data["review_holds"]["MEMBER_EVIDENCE_CONTRACT_MISMATCH"]==2


def test_recc_public_source_unavailable_not_interpreted_as_zero_companies():
    def fail(_url): raise TimeoutError()
    with pytest.raises(RuntimeError,match="public listing unavailable"):
        build_recc_source_first_review(listing_fetch=fail,
            detail_fetch=lambda *a:None,site_probe=lambda *a,**k:{})


def test_site_redirect_to_different_host_is_not_independent_identity_proof():
    data=build_recc_source_first_review(
        max_members=1,max_site_probes=1,
        listing_fetch=lambda url:LISTING,
        detail_fetch=lambda name,url:member(name,url,"https://acmesolar.co.uk/"),
        site_probe=lambda url,**kw:site("https://otherwebsite.co.uk/"),
    )
    assert data["public_sites_probed"]==1
    assert data["first_party_identity_supported_review_count"]==0
    assert data["review_holds"]["WEBSITE_SAME_HOST_RECEIPT_MISSING"]==1


@pytest.mark.parametrize("number",[0,-1,6,True,"5",None])
def test_member_bound_fail_closed(number):
    with pytest.raises(ValueError):
        build_recc_source_first_review(max_members=number,
                                       listing_fetch=lambda _:LISTING,
                                       detail_fetch=lambda *x:None,
                                       site_probe=lambda *a,**k:{})


@pytest.mark.parametrize("number",[0,3,-1,True,"2",None])
def test_site_probe_bound_fail_closed(number):
    with pytest.raises(ValueError):
        build_recc_source_first_review(max_site_probes=number,
                                       listing_fetch=lambda _:LISTING,
                                       detail_fetch=lambda *x:None,
                                       site_probe=lambda *a,**k:{})


def test_first_source_provider_scope_gb_solar_only():
    validate_scope(source="recc_source_first",sector="solar",country="GB",limit=5)
    for sector,country in (("roofing","GB"),("solar","US"),("insurance","GB")):
        with pytest.raises(ValueError):
            validate_scope(source="recc_source_first",sector=sector,
                           country=country,limit=5)
    with pytest.raises(ValueError,match="target-bound"):
        source_observations(source="recc_source_first",sector="solar",
                            country="GB",max_source=1)


def test_cli_source_first_is_public_only_without_empiredb_credentials(
        monkeypatch, capsys, tmp_path):
    from scripts import run_tam_source_acquisition_connector as cli
    monkeypatch.setattr(cli.os,"geteuid",lambda:0)
    def forbidden_env(*a,**k):
        raise AssertionError("source-first must not access canonical DB env")
    monkeypatch.setattr(cli,"load_runtime_env",forbidden_env)
    monkeypatch.setattr(cli,"canonical_targets",forbidden_env)
    def stub(*,max_members,max_site_probes):
        assert max_members==2
        assert max_site_probes==1
        return build_recc_source_first_review(
            max_members=2,max_site_probes=1,
            listing_fetch=lambda url:LISTING,
            detail_fetch=lambda name,url:member(name,url,
                 "https://acmesolar.co.uk/" if "acme" in url
                 else "https://brightsolar.co.uk/"),
            site_probe=lambda url,**kw:site(url),
        )
    monkeypatch.setattr(cli,"build_recc_source_first_review",stub)
    monkeypatch.setattr(cli,"save_private",lambda x:tmp_path/"private.json")
    assert cli.main([
        "--observe","--source","recc_source_first",
        "--sector","solar","--country","GB",
        "--max-source","2","--max-site-probes","1",
    ])==0
    output=capsys.readouterr().out
    receipt=json.loads(output)
    assert receipt["status"]=="PUBLIC_RECC_SOURCE_FIRST_REVIEW_PREPARED"
    assert receipt["first_party_identity_supported_review_count"]==1
    assert receipt["database_queries"]==0
    assert receipt["database_writes"]==0
    assert receipt["acquisitions_appended"]==0
    assert "Acme Solar Ltd" not in output
    assert "https://acmesolar.co.uk" not in output


@pytest.mark.parametrize("extra",[
    ["--max-source","6"],["--max-site-probes","3"],
    ["--page-count","2"],["--source-page","1"],["--metro","London"],
    ["--diagnose-only"],
])
def test_cli_refuses_unbounded_source_first(extra):
    from scripts import run_tam_source_acquisition_connector as cli
    with pytest.raises(SystemExit) as exc:
        cli.main(["--observe","--source","recc_source_first",
                  "--sector","solar","--country","GB"]+extra)
    assert exc.value.code==2
