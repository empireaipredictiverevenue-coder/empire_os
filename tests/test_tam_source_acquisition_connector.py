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
CREATE TABLE public.prospects(id uuid PRIMARY KEY,website text);
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
