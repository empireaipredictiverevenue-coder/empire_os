"""Canonical TAM044 aggregate-only audit tested on disposable PostgreSQL."""
from pathlib import Path
import json
import re

import pytest

from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_isolated_restricted_reader import isolated

SQL=Path("scripts/tam044_source_quality_audit_readonly.sql")
MIGRATION=Path("migrations/empiredb/044_tam_scoped_market_sampling.sql")


@pytest.fixture
def market(isolated):
    isolated("empiredb",MIGRATION.read_text())
    return isolated


def _output(execute):
    # Disposable pg --single prints the scalar JSON from SELECT into stdout.
    out=execute("empiredb",SQL.read_text())
    start=out.find('{"')
    assert start>=0, out[-500:]
    decoder=json.JSONDecoder()
    report,_=decoder.raw_decode(out[start:])
    return report


def test_source_audit_readonly_and_no_records_or_secrets(isolated):
    sql=SQL.read_text()
    assert "TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in sql
    assert "ROLLBACK;" in sql
    assert "statement_timeout='25s'" in sql
    assert "LIMIT 20000" in sql
    assert "company_name" not in sql
    body="\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    assert "email" not in body.lower()
    assert "canonical_phone" not in sql
    assert "contact_points" not in sql
    assert "INSERT INTO" not in sql
    assert "UPDATE public" not in sql
    assert "DELETE FROM" not in sql
    assert "DROP " not in sql
    assert "evidence->>'source_url'" in sql
    assert "l.active IS TRUE" in sql
    assert "TAM_SOURCE_AUDIT_WRONG_DATABASE_OR_REPLICA" in sql
    assert "population_complete',false" in sql


def test_disposable_audit_reports_six_markets_and_known_evidence(market):
    result=_output(market)
    assert result["schema_version"]=="empire.tam-source-quality-audit.v1"
    assert result["mode"]=="OBSERVE"
    assert result["population_complete"] is False
    assert result["candidate_entities_examined"]==2
    assert result["scope_count"]==6
    assert result["database_write"] is False
    assert result["execution_authority"]=="none"
    assert result["contact_rows_returned"]==0
    assert result["company_rows_returned"]==0
    cells={(x["sector"],x["country"]):x for x in result["market_diagnostics"]}
    assert len(cells)==6
    assert cells["roofing","US"]["exact_reader_eligible_sample"]==1
    assert cells["solar","GB"]["exact_reader_eligible_sample"]==1
    assert cells["solar","US"]["exact_reader_eligible_sample"]==0
    assert cells["insurance","GB"]["exact_reader_eligible_sample"]==0
    assert cells["roofing","GB"]["exact_reader_eligible_sample"]==0
    assert cells["solar","GB"]["exact_with_active_link"]==1


def test_candidate_alias_not_automatically_promoted_to_reader_eligible(market):
    market("empiredb","""
SET ROLE empiredb_migrator;
INSERT INTO public.business_entities VALUES
 ('00000000-0000-0000-0000-000000000095','Solar Alias','solar installer'),
 ('00000000-0000-0000-0000-000000000096','Roof Missing','roofing');
INSERT INTO public.prospect_entity_links VALUES
 ('10000000-0000-0000-0000-000000000095',
  '00000000-0000-0000-0000-000000000095',true),
 ('10000000-0000-0000-0000-000000000096',
  '00000000-0000-0000-0000-000000000096',true);
INSERT INTO public.prospect_acquisitions VALUES
 ('20000000-0000-0000-0000-000000000095',
  '10000000-0000-0000-0000-000000000095',
  'registry','https://example.com/solar',
  '{"locale":{"country_code":"GB"}}'::jsonb,
  '2026-10-10 10:00+00'),
 ('20000000-0000-0000-0000-000000000096',
  '10000000-0000-0000-0000-000000000096',
  'registry','',
  '{"locale":{"country_code":"GB"}}'::jsonb,
  '2026-10-10 10:00+00');
RESET ROLE;
""")
    result=_output(market)
    cells={(x["sector"],x["country"]):x for x in result["market_diagnostics"]}
    assert cells["solar","GB"]["aliases_with_country_and_source_not_reader_eligible"]==1
    assert cells["solar","GB"]["exact_reader_eligible_sample"]==1
    assert cells["roofing","GB"]["exact_with_country_evidence"]==1
    assert cells["roofing","GB"]["exact_country_evidence_without_usable_source"]==1
    assert cells["roofing","GB"]["exact_reader_eligible_sample"]==0
