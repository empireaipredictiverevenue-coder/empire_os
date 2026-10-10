"""TAM existing-entity genuine-source match: deterministic, read-only."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_empiredb_tam_isolated_restricted_reader import isolated
from test_empiredb_materializer_bootstrap import execute
from empire_os.tam_source_acquisition_connector import (
  _provenance, validate_scope, source_observations, canonical_targets,
  build_review, TARGET_SQL,
)

RECC="https://www.recc.org.uk/scheme/members/solar-co"
OSM="https://www.openstreetmap.org/node/12345"


def t(entity="e1", prospect="p1", name="Solar Co",
      website="https://solarco.example", phone="01234567890"):
    return {"entity_id":entity,"prospect_id":prospect,
        "canonical_name":name,"canonical_website":website,
        "prospect_website":website,"canonical_phone":phone,
        "sector":"solar"}


def source(name="Solar Co",url=RECC,website="https://solarco.example",
           phone="01234567890",country="GB"):
    return {"name":name,"source_url":url,"business_website":website,
            "phone":phone,"country_code":country,
            "source":"recc_solar","sector":"solar"}


def test_two_independent_identity_signals_queue_review_no_write():
    report=build_review(targets=[t()],observations=[source()],
        source="recc_solar",sector="solar",country="GB")
    assert report["strong_evidence_review_count"]==1
    assert report["findings"][0]["state"]=="STRONG_EVIDENCE_REVIEW"
    assert "independent_website_host" in report["findings"][0]["match_basis"]
    assert report["findings"][0]["canonical_acquisition_appended"] is False
    assert report["findings"][0]["identity_verified_for_automatic_promotion"] is False
    assert report["database_write"] is False
    assert report["genuine_acquisition_appended"]==0
    assert report["outbound_sent"] is False
    assert report["source_observation_is_not_automatic_identity_proof"] is True


def test_name_only_never_promoted_and_conflicting_domains_held():
    got=build_review(targets=[t(website="",phone="")],
        observations=[source(website="",phone="")],
        source="recc_solar",sector="solar",country="GB")
    assert got["findings"][0]["state"]=="NAME_ONLY_REVIEW"
    got=build_review(targets=[t()],observations=[
        source(website="https://different.example",phone="")
    ],source="recc_solar",sector="solar",country="GB")
    assert got["findings"][0]["state"]=="CONFLICTING_WEBSITE"
    assert got["strong_evidence_review_count"]==0


def test_duplicate_entities_or_multiple_source_pages_fail_closed():
    duplicate=build_review(
        targets=[t(),t(entity="e2",prospect="p2")],
        observations=[source()],
        source="recc_solar",sector="solar",country="GB")
    assert duplicate["strong_evidence_review_count"]==0
    assert duplicate["findings"][0]["state"]=="AMBIGUOUS_IDENTITY"
    multiple=build_review(
        targets=[t()],observations=[source(),source(url=RECC+"-duplicate")],
        source="recc_solar",sector="solar",country="GB")
    assert multiple["strong_evidence_review_count"]==0
    assert all(f["state"]=="AMBIGUOUS_MULTI_SOURCE_OR_ENTITY"
               for f in multiple["findings"])


@pytest.mark.parametrize("bad",[
    "https://recc.org.uk.evil.test/scheme/members/a",
    "https://www.recc.org.uk.evil.test/scheme/members/a",
    "https://www.recc.org.uk/scheme/",
    "file:///etc/empiredb.env",
    "http://www.recc.org.uk/scheme/members/a",
    "https://evil.test/scheme/members/a",
    "https://user:pass@www.recc.org.uk/scheme/members/a",
])
def test_source_provenance_allowlist_rejects_forgeries(bad):
    assert _provenance(bad,"recc_solar")==""


@pytest.mark.parametrize("kwargs",[
  {"source":"recc_solar","sector":"insurance","country":"GB","limit":25},
  {"source":"recc_solar","sector":"solar","country":"US","limit":25},
  {"source":"overpass_osm","sector":"insurance","country":"GB","limit":25},
  {"source":"unknown","sector":"solar","country":"GB","limit":25},
  {"source":"recc_solar","sector":"solar","country":"GB","limit":501},
  {"source":"recc_solar","sector":"solar","country":"GB","limit":True},
])
def test_source_connector_refuses_outside_approved_research_scope(kwargs):
    with pytest.raises(ValueError):
        validate_scope(**kwargs)


def test_recc_public_member_is_provenance_only_no_candidate_leak():
    fake=lambda metro=None: iter([
        SimpleNamespace(name="Solar Co",niche="solar",country_code="GB",
          source="recc_solar",url=RECC,
          raw={"business_website":"https://solarco.example"},
          phone="01234567890",metro="United Kingdom"),
        SimpleNamespace(name="Fake Solar",niche="solar",country_code="GB",
          source="recc_solar",url="https://evil.test/source",
          raw={},phone="",metro="United Kingdom"),
    ])
    got=source_observations(source="recc_solar",sector="solar",country="GB",
            fetcher=fake,max_source=2)
    assert len(got)==1
    assert got[0]["source_url"]==RECC
    assert "https://solarco.example"==got[0]["business_website"]


def test_no_source_failure_does_not_create_fake_acquisition():
    def fail(**kwargs):
        raise OSError("network unavailable")
    with pytest.raises(RuntimeError,match="public-source"):
        source_observations(source="recc_solar",sector="solar",country="GB",
                            fetcher=fail)
    result=build_review(targets=[t()],observations=[],
        source="recc_solar",sector="solar",country="GB")
    assert result["potential_matched_observations"]==0
    assert result["genuine_acquisition_appended"]==0


def test_read_only_target_sql_disqualifies_previous_acquisition():
    assert "NOT EXISTS" in TARGET_SQL
    assert "public.prospect_acquisitions" in TARGET_SQL
    assert "l.active IS TRUE" in TARGET_SQL
    assert "ORDER BY e.id LIMIT %s" in TARGET_SQL
    assert "SELECT" in TARGET_SQL
    for forbidden in ("INSERT INTO","UPDATE public","DELETE FROM",
                       "GRANT ","ALTER ROLE"):
        assert forbidden not in TARGET_SQL


def test_wrong_sector_and_tam_source_url_are_not_accepted():
    report=build_review(
        targets=[t()],
        observations=[source(country="US"),
                      source(url="https://elsewhere.test/fake")],
        source="recc_solar",sector="solar",country="GB")
    assert report["strong_evidence_review_count"]==0
    assert report["potential_matched_observations"]==0


def test_protected_private_proposal_file(tmp_path):
    from scripts.run_tam_source_acquisition_connector import save_private
    directory=tmp_path/"private"
    dest=save_private({"findings":[{"source_url":RECC}]},directory)
    assert dest.stat().st_mode & 0o077 == 0
    assert directory.stat().st_mode & 0o077 == 0
    assert json.loads(dest.read_text())["findings"][0]["source_url"]==RECC
    dest2=save_private({},directory)
    assert dest2!=dest
    link=tmp_path/"symlink"
    link.symlink_to(directory,target_is_directory=True)
    with pytest.raises(RuntimeError,match="symlink"):
        save_private({},link)


def test_one_entity_with_multiple_prospects_cannot_auto_match_identity():
    report=build_review(
        targets=[t(entity='e1',prospect='p1'),t(entity='e1',prospect='p2')],
        observations=[source()],
        source='recc_solar',sector='solar',country='GB')
    assert report['strong_evidence_review_count']==0
    assert report['findings'][0]['state']=='AMBIGUOUS_PROSPECT_RELATIONSHIP'
    assert len(report['findings'][0]['prospect_ids'])==2


def test_acquisition_review_ids_deterministic_and_not_inserted():
    left=build_review(targets=[t()],observations=[source()],
        source='recc_solar',sector='solar',country='GB')
    right=build_review(targets=[t()],observations=[source()],
        source='recc_solar',sector='solar',country='GB')
    a=left['findings'][0]
    assert len(a['attachment_review_id'])==64
    assert a['attachment_review_id']==right['findings'][0]['attachment_review_id']
    assert a['proposed_source_evidence']['locale']=={'country_code':'GB'}
    assert a['proposed_source_evidence']['source_ref_verified_on_public_page'] is False
    assert a['external_write_authorized'] is False


def test_cli_refuses_nonroot_without_external_network_or_db():
    import os,subprocess
    if os.geteuid()==0:
        pytest.skip('nonroot guard tested when run as ubuntu')
    command=['bash','scripts/run_tam_source_acquisition_connector.sh',
             '--observe','--source','recc_solar',
             '--sector','solar','--country','GB']
    res=subprocess.run(command,capture_output=True,text=True,timeout=5)
    assert res.returncode==3
    assert 'AUTHORISED_ROOT_REQUIRED' in res.stderr


def test_postgres_query_compiles_in_disposable_schema(isolated):
    isolated('empiredb',r'''
SET ROLE empiredb_migrator;
ALTER TABLE public.business_entities ADD COLUMN canonical_website text;
ALTER TABLE public.business_entities ADD COLUMN canonical_phone text;
CREATE TABLE public.prospects(id uuid PRIMARY KEY,website text,phone text);
INSERT INTO public.prospects VALUES
 ('10000000-0000-0000-0000-000000000001','https://roof.example'),
 ('10000000-0000-0000-0000-000000000002','https://solar.example'),
 ('10000000-0000-0000-0000-000000000003','https://solar.example');
RESET ROLE;
''')
    query=TARGET_SQL.replace('%s',"'solar'",1).replace('%s','250',1)
    # Existing solar GB already has an acquisition in the isolated fixture:
    # must be excluded rather than being falsely marked "needs acquisition".
    output=isolated('empiredb',
        'BEGIN TRANSACTION READ ONLY;\n'+query+';\nROLLBACK;')
    assert 'ERROR:' not in output
    assert 'Solar GB' not in output


def test_name_variant_company_domain_review_never_becomes_strong_auto_identity():
    report=build_review(targets=[t(name='Solar Co Holdings Ltd')],
        observations=[source(name='SolarCo Trading')],
        source='recc_solar',sector='solar',country='GB')
    assert report['potential_matched_observations']==1
    assert report['strong_evidence_review_count']==0
    assert report['name_variant_review_count']==1
    assert report['findings'][0]['state']=='NAME_VARIANT_DOMAIN_PHONE_REVIEW'
    assert 'exact_name' not in report['findings'][0]['match_basis']
    assert report['genuine_acquisition_appended']==0


def test_name_variant_phone_only_without_website_is_manual_review():
    review=build_review(targets=[t(name='Solar Company Holdings',website='')],
        observations=[source(name='Solar Company Trading',website='')],
        source='recc_solar',sector='solar',country='GB')
    assert review['name_variant_review_count']==1
    assert review['findings'][0]['state']=='NAME_VARIANT_PHONE_REVIEW'
    assert review['strong_evidence_review_count']==0


def test_generic_social_domain_is_not_independent_business_identity():
    report=build_review(targets=[t(name='Solar Holdings',website='https://facebook.com/sun')],
        observations=[source(name='Solar Trade',website='https://facebook.com/different',phone='')],
        source='recc_solar',sector='solar',country='GB')
    assert report['potential_matched_observations']==0


def test_domain_collision_across_different_entities_is_ambiguous():
    report=build_review(targets=[t(name='Solar Holdings',entity='e1',prospect='p1'),
        t(name='Solar Trading',entity='e2',prospect='p2')],
        observations=[source(name='Solar Holdings',phone='')],
        source='recc_solar',sector='solar',country='GB')
    assert report['potential_matched_observations']==1
    assert report['strong_evidence_review_count']==0
    assert report['findings'][0]['state']=='AMBIGUOUS_IDENTITY'


def test_unique_entities_not_equated_with_identity_link_row_count():
    report=build_review(targets=[t(entity='e1',prospect='p1'),
        t(entity='e1',prospect='p2'),t(entity='e1',prospect='p2')],
        observations=[],source='recc_solar',sector='solar',country='GB')
    assert report['target_relationship_rows_examined']==2
    assert report['unique_target_entities_examined']==1
    assert report['unique_target_prospects_examined']==2
    assert report['target_entities_with_website_evidence']==1
    assert report['target_entities_with_phone_evidence']==1


def test_recc_pagination_reads_selected_page_and_never_next_one(monkeypatch):
    from empire_os.lead_sources import recc_solar
    urls=[]
    def listing(url):
        urls.append(url)
        return '<a href="/scheme/members/member-1">Solar Co</a>'
    def detail(name,url):
        assert name=='Solar Co'
        return SimpleNamespace(name=name,niche='solar',country_code='GB',
            source='recc_solar',url=url,raw={'business_website':'https://solarco.example'},
            phone='01234567890',metro='United Kingdom')
    monkeypatch.setattr(recc_solar,'_get',listing)
    monkeypatch.setattr(recc_solar,'_detail',detail)
    rows=source_observations(source='recc_solar',sector='solar',country='GB',
        max_source=1,source_page=2)
    assert len(rows)==1
    assert len(urls)==1
    assert 'page=2' in urls[0]
    assert rows[0]['source_url'].startswith('https://www.recc.org.uk/scheme/members/')


@pytest.mark.parametrize('bad_page',[True, -1,41,1.5,'1'])
def test_recc_pagination_refuses_invalid_page_before_public_request(bad_page):
    with pytest.raises(ValueError,match='page'):
        source_observations(source='recc_solar',sector='solar',country='GB',
            max_source=1,source_page=bad_page,fetcher=lambda **k: iter(()))


def test_overpass_refuses_recc_page_even_when_country_matches():
    with pytest.raises(ValueError,match='RECC-only'):
        source_observations(source='overpass_osm',sector='solar',country='GB',
            metro='London',source_page=1,max_source=1)


def test_bounded_recc_three_page_sweep_one_db_read_and_aggregate_receipt(
    monkeypatch,capsys,tmp_path,
):
    from scripts import run_tam_source_acquisition_connector as cli
    seen={"db":0,"pages":[]}
    monkeypatch.setattr(cli.os,'geteuid',lambda:0)
    monkeypatch.setattr(cli,'load_runtime_env',
        lambda *a,**k:{'EMPIREDB_DSN':'postgresql:///empiredb'})
    def targets(*a,**k):
        seen['db']+=1
        return [t()]
    monkeypatch.setattr(cli,'canonical_targets',targets)
    def observations(*,source,sector,country,metro,max_source,source_page):
        seen['pages'].append(source_page)
        return [globals()['source'](url=RECC+f'-page-{source_page}')]
    monkeypatch.setattr(cli,'source_observations',observations)
    monkeypatch.setattr(cli,'save_private',lambda report: tmp_path/'private.json')
    assert cli.main(['--observe','--source','recc_solar','--sector','solar',
           '--country','GB','--source-page','1','--page-count','3',
           '--max-source','2'])==0
    receipt=json.loads(capsys.readouterr().out)
    assert seen['db']==1
    assert seen['pages']==[1,2,3]
    assert receipt['source_page_count']==3
    assert receipt['source_observation_limit_total']==6
    assert receipt['source_observations_examined']==3
    assert receipt['potential_matched_observations']==3
    assert receipt['strong_evidence_review_count']==0
    assert receipt['manual_review_count']==3
    assert receipt['database_write'] is False
    assert receipt['acquisitions_appended']==0
    assert receipt['outbound_sent'] is False
    assert 'candidate_name' not in receipt


@pytest.mark.parametrize('page_count',[0,-1,4])
def test_source_cli_cannot_expand_beyond_three_public_pages(page_count):
    from scripts import run_tam_source_acquisition_connector as cli
    with pytest.raises(SystemExit) as err:
        cli.main(['--observe','--source','recc_solar','--sector','solar',
             '--country','GB','--page-count',str(page_count)])
    assert err.value.code==2


def test_uk_international_vs_domestic_phone_is_reviewed_as_same_business():
    from empire_os.tam_source_acquisition_connector import _phone_key
    assert _phone_key('+44 1234 567890','GB')==_phone_key('01234 567890','GB')
    assert _phone_key('00441234567890','GB')==_phone_key('01234567890','GB')
    assert _phone_key('123456789','GB')==''
    assert _phone_key('5555555555','DE')==''
    report=build_review(targets=[t(name='Solar Ltd',website='',phone='+44 1234 567890')],
        observations=[source(name='Solar Trading',website='',phone='01234 567890')],
        source='recc_solar',sector='solar',country='GB')
    assert report['findings'][0]['state']=='NAME_VARIANT_PHONE_REVIEW'
    assert report['strong_evidence_review_count']==0



def test_linked_prospect_phone_can_find_name_variant_without_canonical_phone():
    row=t(name='Solar Holdings Ltd',website='',phone='')
    row['prospect_phone']='01234567890'
    observed=source(name='Trading As SolarCo Ltd',website='',phone='+44 1234 567890')
    report=build_review(targets=[row],observations=[observed],
        source='recc_solar',sector='solar',country='GB')
    assert report['target_entities_with_phone_evidence']==0
    assert report['target_entities_with_linked_prospect_phone']==1
    assert report['target_prospects_with_linked_phone']==1
    assert report['potential_matched_observations']==1
    assert report['name_variant_review_count']==1
    assert report['strong_evidence_review_count']==0
    assert report['findings'][0]['state']=='NAME_VARIANT_PHONE_REVIEW'
    assert report['genuine_acquisition_appended']==0


def test_two_prospects_on_one_entity_with_matching_phone_remain_ambiguous():
    a=t(name='Solar Holdings Ltd',prospect='p1',website='',phone='')
    a['prospect_phone']='01234567890'
    b=t(name='Solar Holdings Ltd',prospect='p2',website='',phone='')
    b['prospect_phone']='01234567890'
    report=build_review(targets=[a,b],
        observations=[source(name='Solar Holdings Ltd',website='',phone='+44 1234 567890')],
        source='recc_solar',sector='solar',country='GB')
    assert report['potential_matched_observations']==1
    assert report['findings'][0]['state']=='AMBIGUOUS_PROSPECT_RELATIONSHIP'
    assert report['genuine_acquisition_appended']==0
