"""TAM solar identity graph diagnostic: aggregate-only, real disposable PostgreSQL."""
from pathlib import Path
import json

import pytest
from test_empiredb_materializer_bootstrap import execute

SQL=Path("scripts/tam_solar_identity_graph_audit_readonly.sql")

SCHEMA=r"""
CREATE TABLE public.business_entities(
 id uuid PRIMARY KEY,canonical_name text NOT NULL,normalized_name text,
 canonical_niche text,canonical_website text,canonical_phone text,
 identity_confidence numeric(5,4),resolution_state text,
 canonical_metro text, provenance jsonb
);
CREATE TABLE public.prospect_entity_links(
 entity_id uuid, prospect_id uuid, active bool, match_method text
);
CREATE TABLE public.prospect_acquisitions(prospect_id uuid);
CREATE TABLE public.prospects(
 id uuid PRIMARY KEY,business_name text,website text,phone text,
 metro text,niche text
);
"""
FIXTURES=r"""
INSERT INTO public.business_entities VALUES
 ('00000000-0000-0000-0000-000000000001','Solar Holdings Ltd',
  'solar holdings ltd','solar','https://solarone.example','',0.80,
  'resolved','London','{"locale":{"country_code":"GB"}}'),
 ('00000000-0000-0000-0000-000000000002','Solar UK Two',
  'solar uk two','solar','',null,0.40,'unresolved','',
  '{}'::jsonb),
 ('00000000-0000-0000-0000-000000000003','Solar With Acquisition',
  'solar with acquisition','solar','',null,0.70,'resolved','', '{}'::jsonb);
INSERT INTO public.prospects VALUES
 ('10000000-0000-0000-0000-000000000001','Solar Holdings Ltd',
  'https://solarone.example','','London','solar'),
 ('10000000-0000-0000-0000-000000000002','Solar Trading Ltd',
  'https://differentsolar.example','01234567890','Manchester','solar'),
 ('10000000-0000-0000-0000-000000000003','Solar UK Two',
  'https://second.example','','Leeds','solar'),
 ('10000000-0000-0000-0000-000000000004','Solar With Acquisition',
  'https://third.example','','London','solar');
INSERT INTO public.prospect_entity_links VALUES
 ('00000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',true,'exact_name'),
 ('00000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000002',true,'weak'),
 ('00000000-0000-0000-0000-000000000002',
  '10000000-0000-0000-0000-000000000003',true,'verified'),
 ('00000000-0000-0000-0000-000000000003',
  '10000000-0000-0000-0000-000000000004',true,'exact_name');
INSERT INTO public.prospect_acquisitions VALUES
 ('10000000-0000-0000-0000-000000000004');
"""

@pytest.fixture
def db(execute):
    execute("postgres","CREATE DATABASE empiredb;")
    execute("empiredb",SCHEMA)
    execute("empiredb",FIXTURES)
    return execute

def audit(db):
    result=db("empiredb",SQL.read_text())
    begin=result.find('{"')
    assert begin>=0,result[-600:]
    return json.JSONDecoder().raw_decode(result[begin:])[0]

def test_graph_audit_reports_real_identity_quality_not_fake_unique_entities(db):
    report=audit(db)
    assert report["schema_version"]=="empire.tam-source-identity-graph-audit.v1"
    assert report["source_population_complete"] is False
    assert report["database_write"] is False
    assert report["company_rows_returned"]==0
    assert report["contact_rows_returned"]==0
    assert report["acquisitions_appended"]==0
    m=report["metrics"]
    assert m["target_entities"]==2
    assert m["active_link_rows"]==3
    assert m["distinct_prospects"]==3
    assert m["single_prospect_entities"]==1
    assert m["entities_with_2_to_5_prospects"]==1
    assert m["maximum_links_on_one_entity"]==2
    assert m["entities_with_multiple_prospect_website_hosts"]==1
    assert m["entities_with_canonical_website"]==1
    assert m["entities_without_canonical_website_but_linked_website"]==1
    assert m["entities_with_phone_on_linked_prospect"]==1
    assert m["entities_with_linked_prospect_name_variants"]==1
    assert m["entities_with_website_host_disagreements"]==1
    assert m["entities_with_explicit_gb_provenance"]==1

def test_read_only_scope_and_absence_of_pii(db):
    sql=SQL.read_text()
    assert "REPEATABLE READ READ ONLY" in sql
    assert "ROLLBACK;" in sql
    assert "LIMIT 250" in sql
    assert "source_population_complete',false" in sql
    assert "company_rows_returned',0" in sql
    assert "contact_rows_returned',0" in sql
    for unsafe in ("INSERT INTO","UPDATE public","DELETE FROM","GRANT EXECUTE"):
        assert unsafe not in sql
    assert audit(db)["metrics"]["target_entities"]==2

def test_no_solar_data_is_zero_sample_not_population_assertion(execute):
    execute("postgres","CREATE DATABASE empiredb;")
    execute("empiredb",SCHEMA)
    result=execute("empiredb",SQL.read_text())
    doc=json.JSONDecoder().raw_decode(result[result.index('{"'):])[0]
    assert doc["metrics"]["target_entities"]==0
    assert doc["source_population_complete"] is False
