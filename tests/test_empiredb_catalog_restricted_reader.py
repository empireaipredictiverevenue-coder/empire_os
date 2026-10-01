"""Exercise the real catalog function and correction in disposable PostgreSQL."""
from pathlib import Path

import pytest

from test_empiredb_materializer_bootstrap import execute  # isolated cluster fixture

MIGRATION = Path('migrations/empiredb/022_commercial_catalog_restricted_reader.sql')


@pytest.fixture
def catalog(execute):
    execute('postgres', 'CREATE DATABASE empiredb;')
    execute('empiredb', '''
      CREATE ROLE empiredb_migrator NOLOGIN;
      CREATE ROLE empiredb_app NOLOGIN;
      CREATE ROLE empire_intelligence_materializer NOLOGIN NOINHERIT;
      CREATE ROLE empire_intelligence_materializer_login LOGIN NOINHERIT;
      CREATE ROLE unrelated_reader NOLOGIN;
      GRANT empire_intelligence_materializer TO empire_intelligence_materializer_login;
      GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator;
      GRANT USAGE ON SCHEMA public TO empire_intelligence_materializer;
      SET ROLE empiredb_migrator;
      CREATE TABLE public.commercial_products (
        id integer, product_code text, product_name text, product_family text,
        active boolean, catalog_state text, currency text, provenance jsonb,
        billing_model text);
      CREATE TABLE public.commercial_product_versions (
        id integer, product_id integer, version integer, version_state text,
        effective_from timestamptz, effective_until timestamptz, billing_model text,
        price_basis jsonb, acquisition_cost_basis jsonb, fulfilment_cost_basis jsonb,
        margin_policy jsonb, provenance jsonb, evidence_refs jsonb,
        verified_at timestamptz, verified_by text);
      INSERT INTO public.commercial_products (id, product_code)
        SELECT n, 'fixture-' || n FROM generate_series(1,601) n;
      INSERT INTO public.commercial_product_versions (id,product_id,version,version_state)
        VALUES (1,1,1,'UNKNOWN');
    ''')
    source = Path('migrations/empiredb/016_active_runtime_authority.sql').read_text()
    function = source.split('CREATE OR REPLACE FUNCTION public.get_commercial_product_catalog(', 1)[1]
    function = 'CREATE OR REPLACE FUNCTION public.get_commercial_product_catalog(' + function.split('$$;', 1)[0] + '$$;'
    execute('empiredb', 'SET ROLE empiredb_migrator;\n' + function + '''
      GRANT EXECUTE ON FUNCTION public.get_commercial_product_catalog(text,integer)
        TO empire_intelligence_materializer;
    ''')
    # Inert test-only sentinels for consequential RPC boundaries.
    for name in ('decide_commercial_terms', 'approve_bsc_payment_request',
                 'recognize_bsc_revenue', 'verify_commercial_evidence'):
        execute('empiredb', f"""
          SET ROLE empiredb_migrator;
          CREATE FUNCTION public.{name}() RETURNS boolean
            LANGUAGE sql SECURITY DEFINER AS 'SELECT true';
          REVOKE ALL ON FUNCTION public.{name}() FROM PUBLIC;
        """)
    return execute


def test_catalog_boundary_and_idempotency(catalog):
    catalog('empiredb', '''SET ROLE empire_intelligence_materializer;
      SELECT public.get_commercial_product_catalog(NULL,100);''',
      expected_error='permission denied for table commercial_products')
    migration = MIGRATION.read_text()
    catalog('empiredb', migration)
    catalog('empiredb', migration)
    catalog('empiredb', '''
      SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
      SET ROLE empire_intelligence_materializer;
      DO $$ DECLARE n integer; requested integer; BEGIN
        FOREACH requested IN ARRAY ARRAY[501,2147483647,100,0,-1,NULL] LOOP
          n := jsonb_array_length(public.get_commercial_product_catalog(NULL,requested));
          IF n <> LEAST(GREATEST(COALESCE(requested,100),1),500) THEN
            RAISE EXCEPTION 'catalog bound violated';
          END IF;
        END LOOP;
        IF public.get_commercial_product_catalog('fixture-1',500)->0->>'version_state'
            IS DISTINCT FROM 'UNKNOWN' THEN RAISE EXCEPTION 'version projection lost'; END IF;
        IF public.get_commercial_product_catalog('missing',500) <> '[]'::jsonb THEN
          RAISE EXCEPTION 'filter lost'; END IF;
      END $$;
    ''')
    for role in ('empire_intelligence_materializer', 'empire_intelligence_materializer_login'):
        for table in ('commercial_products', 'commercial_product_versions'):
            for statement in (f'SELECT * FROM public.{table}',
                              f'INSERT INTO public.{table}(id) VALUES (999)',
                              f'UPDATE public.{table} SET id=999',
                              f'DELETE FROM public.{table}'):
                catalog('empiredb', f'SET ROLE {role}; {statement};',
                        expected_error=f'permission denied for table {table}')
    for name in ('decide_commercial_terms', 'approve_bsc_payment_request',
                 'recognize_bsc_revenue', 'verify_commercial_evidence'):
        catalog('empiredb', f'SET ROLE empire_intelligence_materializer; SELECT public.{name}();',
                expected_error=f'permission denied for function {name}')
    catalog('empiredb', '''SET ROLE unrelated_reader;
      SELECT public.get_commercial_product_catalog(NULL,1);''',
      expected_error='permission denied for function get_commercial_product_catalog')
    catalog('empiredb', '''
      DO $$ BEGIN
        IF NOT EXISTS (SELECT FROM pg_proc WHERE
          oid='public.get_commercial_product_catalog(text,integer)'::regprocedure
          AND prosecdef AND proowner='empiredb_migrator'::regrole
          AND proconfig=ARRAY['search_path=""']) THEN
          RAISE EXCEPTION 'unsafe function configuration'; END IF;
        IF EXISTS (SELECT FROM pg_proc p,
          LATERAL aclexplode(p.proacl) a
          WHERE p.oid='public.get_commercial_product_catalog(text,integer)'::regprocedure
            AND a.grantee=0) THEN RAISE EXCEPTION 'PUBLIC execute'; END IF;
        IF EXISTS (SELECT FROM pg_auth_members WHERE
          member='empire_intelligence_materializer'::regrole) THEN
          RAISE EXCEPTION 'materializer gained role authority'; END IF;
        IF EXISTS (SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname='public' AND p.proname <> 'get_commercial_product_catalog'
          AND has_function_privilege('empire_intelligence_materializer',p.oid,'EXECUTE')) THEN
          RAISE EXCEPTION 'additional executable function'; END IF;
      END $$;
    ''')


@pytest.mark.parametrize('unsafe_sql,error', [
    ('ALTER ROLE empiredb_migrator LOGIN', 'catalog owner requires'),
    ('GRANT empiredb_migrator TO empire_intelligence_materializer', 'runtime role must not'),
    ('GRANT SELECT ON public.commercial_products TO empire_intelligence_materializer',
     'unexpected materializer commercial table authority'),
    ('GRANT SELECT (id) ON public.commercial_product_versions TO empire_intelligence_materializer',
     'unexpected materializer commercial table authority'),
])
def test_unsafe_preconditions_abort(catalog, unsafe_sql, error):
    catalog('empiredb', unsafe_sql + ';')
    catalog('empiredb', MIGRATION.read_text(), expected_error=error)
    catalog('empiredb', '''DO $$ BEGIN
      IF (SELECT prosecdef FROM pg_proc WHERE
          oid='public.get_commercial_product_catalog(text,integer)'::regprocedure) THEN
        RAISE EXCEPTION 'failed migration changed security'; END IF;
      END $$;''')
