"""Market-aware TAM reader 044: independent disposable PostgreSQL contract."""
from pathlib import Path

import pytest
from test_empiredb_tam_isolated_restricted_reader import isolated
from test_empiredb_materializer_bootstrap import execute

SCOPED=Path("migrations/empiredb/044_tam_scoped_market_sampling.sql")


@pytest.fixture
def market(isolated):
    isolated("empiredb",SCOPED.read_text())
    return isolated


def test_market_reader_reserves_six_country_sector_slots(market):
    market("empiredb",r"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
DO $t$
DECLARE d jsonb;
BEGIN
 SELECT public.get_tam_market_observations_scoped(
   ARRAY['roofing','solar','insurance']::text[],
   ARRAY['GB','US']::text[], 12
 ) INTO d;
 IF d->>'schema_version'<>'empire.tam-scoped-reader.v1' THEN
   RAISE EXCEPTION 'wrong scoped research schema';
 END IF;
 IF d->>'selection_method'<>'MARKET_QUOTA_SAMPLED'
    OR (d->>'requested_scope_count')::int <> 6
    OR pg_catalog.jsonb_array_length(d->'scope_coverage') <> 6
    OR pg_catalog.jsonb_array_length(d->'rows') <> 2
    OR d->>'source_population_complete'<>'false'
    OR d->>'buyer_intent_inferred'<>'false'
    OR d->>'tam_inferred_from_roster'<>'false'
    OR d->>'execution_authority'<>'none'
 THEN RAISE EXCEPTION 'bad market aware result metadata'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.jsonb_array_elements(d->'scope_coverage') x
   WHERE x->>'industry'='insurance' AND x->>'country_code'='GB'
     AND (x->>'selected_count')::int=0
     AND (x->>'sample_quota')::int=2
     AND x->>'population_complete'='false'
 ) THEN RAISE EXCEPTION 'missing honest empty insurance GB slot'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.jsonb_array_elements(d->'rows') x
   WHERE x->>'industry'='roofing' AND x->>'country_code'='US'
     AND x->>'source_ref'='https://source.example/us-new'
 ) OR NOT EXISTS (
   SELECT 1 FROM pg_catalog.jsonb_array_elements(d->'rows') x
   WHERE x->>'industry'='solar' AND x->>'country_code'='GB'
 ) THEN RAISE EXCEPTION 'failed to preserve scoped source evidence'; END IF;
END $t$;
""")


def test_market_quota_does_not_allow_roofing_to_starve_solar(market):
    # Add 6 more roofing US firms with increasing UUIDs, plus 1 GB insurance.
    additions=[]
    for i in range(3,9):
        e=f"00000000-0000-0000-0000-{i:012d}"
        p=f"10000000-0000-0000-0000-{i:012d}"
        a=f"20000000-0000-0000-0000-{i+100:012d}"
        additions.append(f"""('{e}','Roof {i}','roofing')""")
    market("empiredb","""
SET ROLE empiredb_migrator;
INSERT INTO public.business_entities(id,canonical_name,canonical_niche)
VALUES """+",".join(additions)+""";
RESET ROLE;
""")
    for i in range(3,9):
        market("empiredb",f"""
SET ROLE empiredb_migrator;
INSERT INTO public.prospect_entity_links(prospect_id,entity_id,active)
VALUES ('10000000-0000-0000-0000-{i:012d}',
        '00000000-0000-0000-0000-{i:012d}',true);
INSERT INTO public.prospect_acquisitions(id,prospect_id,source,source_url,evidence,created_at)
VALUES (
 '20000000-0000-0000-0000-{i+100:012d}',
 '10000000-0000-0000-0000-{i:012d}',
 'registry','https://source.example/roof-{i}',
 '{{"locale":{{"country_code":"US"}}}}'::jsonb,
 '2026-10-0{i-1} 12:00+00'
);
RESET ROLE;
""")
    market("empiredb",r"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
DO $t$
DECLARE d jsonb;
BEGIN
 SELECT public.get_tam_market_observations_scoped(
  ARRAY['roofing','solar','insurance'],ARRAY['GB','US'],6) INTO d;
 IF pg_catalog.jsonb_array_length(d->'rows')<>2
 THEN RAISE EXCEPTION 'unexpected quota admission'; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.jsonb_array_elements(d->'rows') x
  WHERE x->>'industry'='solar' AND x->>'country_code'='GB'
 ) THEN RAISE EXCEPTION 'solar GB starved by larger roofing US cohort'; END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.jsonb_array_elements(d->'scope_coverage') x
  WHERE x->>'industry'='roofing' AND x->>'country_code'='US'
    AND (x->>'sample_quota')::int=1 AND (x->>'selected_count')::int=1
 ) THEN RAISE EXCEPTION 'roofing US quota not bounded'; END IF;
END $t$;
""")


@pytest.mark.parametrize("bad_expr",[
 "ARRAY['roofing','roofing']::text[]",
 "ARRAY['finance']::text[]",
 "ARRAY[NULL]::text[]",
 "ARRAY['Roofing']::text[]",
 "NULL::text[]",
 "ARRAY[]::text[]",
])
def test_scoped_market_rejects_invalid_industries(market,bad_expr):
    market("empiredb",f"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
SELECT public.get_tam_market_observations_scoped(
 {bad_expr},ARRAY['GB','US']::text[],6
);
""", expected_error="TAM scoped markets must be unique approved countries/sectors")


@pytest.mark.parametrize("bad_expr",[
 "ARRAY['GB','GB']::text[]",
 "ARRAY['DE']::text[]",
 "ARRAY[NULL]::text[]",
 "ARRAY['gb']::text[]",
 "NULL::text[]",
])
def test_scoped_market_rejects_invalid_countries(market,bad_expr):
    market("empiredb",f"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
SELECT public.get_tam_market_observations_scoped(
 ARRAY['roofing']::text[],{bad_expr},3
);
""", expected_error="TAM scoped markets must be unique approved countries/sectors")


@pytest.mark.parametrize("value",["0","5","1001","NULL"])
def test_scoped_limit_is_bounded_and_requires_minimum_slot(market,value):
    market("empiredb",f"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
SELECT public.get_tam_market_observations_scoped(
 ARRAY['roofing','solar','insurance'],ARRAY['GB','US'],{value}
);
""",expected_error="TAM scoped sample limit must be per-scope to 1000")


def test_scoped_market_never_grants_legacy_or_base_table_access(market):
    market("empiredb",r"""
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;
SELECT public.get_tam_market_observations_scoped(
 ARRAY['roofing'],ARRAY['US'],1);
""",expected_error="permission denied for function get_tam_market_observations_scoped")
    market("empiredb",r"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
SELECT * FROM public.prospect_acquisitions;
""",expected_error="permission denied for table prospect_acquisitions")


def test_scoped_reader_migration_rejects_colliding_redeploy(market):
    market("empiredb",SCOPED.read_text(),
           expected_error="TAM scoped reader collision; review catalog first")


def test_scoped_only_rollback_preserves_live_043_and_legacy(market):
    rollback=Path('deploy/empiredb/tam044_scoped_rollback_held.sql').read_text()
    market('empiredb',rollback)
    market('empiredb',r'''
DO $r$
BEGIN
 IF to_regprocedure('public.get_tam_market_observations_scoped(text[],text[],integer)')
  IS NOT NULL THEN RAISE EXCEPTION 'scoped function not rolled back'; END IF;
 IF to_regprocedure('public.get_tam_market_observations(integer)')
  IS NULL THEN RAISE EXCEPTION 'old 043 function was lost'; END IF;
 IF NOT has_function_privilege('empire_tam_market_reader',
   'public.get_tam_market_observations(integer)','EXECUTE') THEN
   RAISE EXCEPTION 'old TAM isolation removed'; END IF;
 IF NOT has_table_privilege('empire_intelligence_materializer',
   'public.business_entities','SELECT') THEN
   RAISE EXCEPTION 'legacy Market GPS permissions lost'; END IF;
END $r$;
''')
