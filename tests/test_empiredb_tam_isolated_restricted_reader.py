"""Held isolated TAM role + RPC release: disposable PostgreSQL contract.

No production credentials or databases touched. Old Market GPS materializer
must keep its source-table SELECT while new TAM role has zero source access.
"""
from pathlib import Path
import pytest
from test_empiredb_materializer_bootstrap import execute
from test_empiredb_tam_country_evidence_restricted_reader import SCHEMA, FIXTURES

BOOTSTRAP=Path('deploy/empiredb/tam_isolated_roles_bootstrap.sql')
MIGRATION=Path('migrations/empiredb/043_tam_isolated_restricted_reader.sql')


@pytest.fixture
def isolated(execute):
    execute('postgres','CREATE DATABASE empiredb;')
    execute('empiredb',SCHEMA)
    execute('empiredb',FIXTURES)
    execute('empiredb',"""
        GRANT SELECT ON public.prospect_entity_links, public.business_entities
        TO empire_intelligence_materializer;
    """)
    execute('empiredb', BOOTSTRAP.read_text())
    execute('empiredb', MIGRATION.read_text())
    return execute


def test_isolated_reader_returns_canonical_evidence_and_no_legacy_break(isolated):
    isolated('empiredb',r"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
DO $test$
DECLARE p jsonb;
BEGIN
  SELECT public.get_tam_market_observations(100) INTO p;
  IF pg_catalog.jsonb_array_length(p) <> 2 THEN
    RAISE EXCEPTION 'unexpected restricted TAM row count %',p;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.jsonb_array_elements(p) x
    WHERE x->>'company_name'='Roof One'
      AND x->>'country_code'='US'
      AND x->>'source_ref'='https://source.example/us-new'
      AND x->>'execution_authority'='none'
  ) THEN RAISE EXCEPTION 'no newest US source evidence'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.jsonb_array_elements(p) x
    WHERE x->>'company_name'='Solar GB'
      AND x->>'country_code'='GB'
  ) THEN RAISE EXCEPTION 'missing solar GB source'; END IF;
END $test$;
RESET ROLE;
RESET SESSION AUTHORIZATION;
DO $assert$
BEGIN
  IF NOT has_table_privilege(
    'empire_intelligence_materializer',
    'public.prospect_entity_links','SELECT'
  ) OR NOT has_table_privilege(
    'empire_intelligence_materializer','public.business_entities','SELECT'
  ) THEN RAISE EXCEPTION 'legacy materializer privileges changed'; END IF;
END $assert$;
""")


def test_new_tam_role_no_base_tables_and_no_legacy_function_execute(isolated):
    isolated('empiredb',r"""
DO $test$
DECLARE name text; rel text; priv text;
BEGIN
  FOREACH name IN ARRAY ARRAY[
    'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    FOREACH rel IN ARRAY ARRAY[
      'public.prospect_acquisitions',
      'public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      FOREACH priv IN ARRAY ARRAY[
        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
      ] LOOP
        IF has_table_privilege(name,rel,priv) THEN
          RAISE EXCEPTION 'unauthorized source table privilege %',name;
        END IF;
      END LOOP;
      IF has_any_column_privilege(
          name,rel,'SELECT,INSERT,UPDATE,REFERENCES'
      ) THEN RAISE EXCEPTION 'unauthorized source column privilege'; END IF;
    END LOOP;
  END LOOP;
  IF has_function_privilege(
    'empire_intelligence_materializer',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR has_function_privilege(
    'empire_intelligence_materializer_login',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) OR has_function_privilege(
    'empiredb_app','public.get_tam_market_observations(integer)','EXECUTE'
  ) THEN RAISE EXCEPTION 'legacy materializer got isolated function'; END IF;
  IF NOT has_function_privilege(
    'empire_tam_market_reader',
    'public.get_tam_market_observations(integer)','EXECUTE'
  ) THEN RAISE EXCEPTION 'isolated reader cannot execute function'; END IF;
END $test$;
""")


def test_invalid_bound_and_legacy_login_does_not_gain_tam_function(isolated):
    isolated('empiredb',r"""
SET SESSION AUTHORIZATION empire_tam_market_login;
SET ROLE empire_tam_market_reader;
DO $test$
BEGIN
  BEGIN
    PERFORM public.get_tam_market_observations(5001);
    RAISE EXCEPTION 'overbound TAM request accepted';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM='overbound TAM request accepted' THEN RAISE; END IF;
  END;
END $test$;
RESET ROLE;
RESET SESSION AUTHORIZATION;
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;
DO $test$
BEGIN
  BEGIN
    PERFORM public.get_tam_market_observations(1);
    RAISE EXCEPTION 'legacy TAM RPC should be forbidden';
  EXCEPTION WHEN insufficient_privilege OR undefined_function THEN NULL;
  END;
END $test$;
""")


def test_new_role_bootstrap_and_sql_reject_existing_legacy_grants(execute):
    execute('postgres','CREATE DATABASE empiredb;')
    execute('empiredb',SCHEMA)
    execute('empiredb',"""
        GRANT SELECT ON public.prospect_entity_links,public.business_entities
          TO empire_intelligence_materializer;
    """)
    execute('empiredb',BOOTSTRAP.read_text())
    execute('empiredb',MIGRATION.read_text())
    # No impact to the current materializer; old migration still fails.
    old=Path('migrations/empiredb/028_tam_country_evidence_restricted_reader.sql')
    execute('empiredb',old.read_text(),
            expected_error='unexpected TAM materializer table authority')


def test_guarded_isolated_rollback_preserves_old_materializer(isolated):
    rollback=Path("deploy/empiredb/tam_isolated_rollback_held.sql").read_text()
    isolated("empiredb",rollback)
    isolated("empiredb",r"""
DO $test$
BEGIN
  IF to_regprocedure('public.get_tam_market_observations(integer)')
     IS NOT NULL THEN
    RAISE EXCEPTION 'isolated TAM RPC still present after rollback';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname IN (
      'empire_tam_market_login','empire_tam_market_reader'
    )
  ) THEN RAISE EXCEPTION 'isolated TAM roles still present'; END IF;
  IF NOT has_table_privilege(
     'empire_intelligence_materializer','public.business_entities','SELECT'
  ) OR NOT has_table_privilege(
     'empire_intelligence_materializer','public.prospect_entity_links','SELECT'
  ) THEN RAISE EXCEPTION 'legacy Market GPS permissions changed'; END IF;
END $test$;
""")


def test_missing_prerequisite_is_rejected_without_accidental_roles(execute):
    execute('postgres','CREATE DATABASE empiredb;')
    execute('empiredb',SCHEMA)
    execute('empiredb',MIGRATION.read_text(),
            expected_error='dedicated isolated TAM bootstrap required')
    execute('empiredb',r"""
DO $test$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_tam_market_login'
  ) OR to_regprocedure('public.get_tam_market_observations(integer)')
      IS NOT NULL THEN
    RAISE EXCEPTION 'held migration unexpectedly created authority';
  END IF;
END $test$;
""")
