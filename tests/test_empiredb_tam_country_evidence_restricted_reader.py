"""Executable tests for the restricted TAM country-evidence reader."""
from pathlib import Path

import pytest

from test_empiredb_materializer_bootstrap import execute


MIGRATION = Path(
    "migrations/empiredb/028_tam_country_evidence_restricted_reader.sql"
)

SCHEMA = r"""
CREATE ROLE empiredb_migrator NOLOGIN;
CREATE ROLE empiredb_app NOLOGIN;
CREATE ROLE empire_intelligence_materializer NOLOGIN NOINHERIT;
CREATE ROLE empire_intelligence_materializer_login LOGIN NOINHERIT;
CREATE ROLE unrelated_reader LOGIN NOINHERIT;
GRANT empire_intelligence_materializer
  TO empire_intelligence_materializer_login;
GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator;
GRANT USAGE ON SCHEMA public
  TO empire_intelligence_materializer, unrelated_reader;

SET ROLE empiredb_migrator;
CREATE TABLE public.business_entities(
  id uuid PRIMARY KEY,
  canonical_name text,
  canonical_niche text
);
CREATE TABLE public.prospect_entity_links(
  prospect_id uuid,
  entity_id uuid,
  active boolean
);
CREATE TABLE public.prospect_acquisitions(
  id uuid PRIMARY KEY,
  prospect_id uuid,
  source text,
  source_url text,
  evidence jsonb,
  created_at timestamptz
);
RESET ROLE;
"""

FIXTURES = r"""
SET ROLE empiredb_migrator;
INSERT INTO public.business_entities VALUES
 ('00000000-0000-0000-0000-000000000001','Roof One','roofing'),
 ('00000000-0000-0000-0000-000000000002','Solar GB','solar');

INSERT INTO public.prospect_entity_links VALUES
 ('10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',true),
 ('10000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000002',true),
 ('10000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000002',false);

INSERT INTO public.prospect_acquisitions VALUES
 ('20000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  'registry','https://source.example/us-old',
  '{"locale":{"country_code":"US","resolved_from":"explicit_country"}}',
  '2026-10-01 10:00+00'),
 ('20000000-0000-0000-0000-000000000002',
  '10000000-0000-0000-0000-000000000001',
  'registry','https://source.example/us-new',
  '{"locale":{"country_code":"US","resolved_from":"explicit_country"}}',
  '2026-10-02 10:00+00'),
 ('20000000-0000-0000-0000-000000000003',
  '10000000-0000-0000-0000-000000000002',
  'registry','https://source.example/gb',
  '{"locale":{"country_code":"GB","resolved_from":"explicit_country"}}',
  '2026-10-02 11:00+00'),
 ('20000000-0000-0000-0000-000000000004',
  '10000000-0000-0000-0000-000000000002',
  'bad','https://source.example/bad',
  '{"locale":{"country_code":"United Kingdom"}}',
  '2026-10-02 12:00+00');
RESET ROLE;
"""


@pytest.fixture
def tam_reader(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    execute("empiredb", FIXTURES)
    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", migration)
    return execute


def test_reader_returns_latest_evidence_and_valid_country(tam_reader):
    tam_reader("empiredb", r"""
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.get_tam_market_observations(100) INTO p;
  IF pg_catalog.jsonb_array_length(p) <> 2 THEN
    RAISE EXCEPTION 'unexpected TAM row count: %', p;
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.jsonb_array_elements(p) x
    WHERE x->>'company_name'='Roof One'
      AND x->>'country_code'='US'
      AND x->>'source_ref'='https://source.example/us-new'
      AND x->>'execution_authority'='none'
  ) THEN
    RAISE EXCEPTION 'latest US evidence missing: %', p;
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_catalog.jsonb_array_elements(p) x
    WHERE x->>'company_name'='Solar GB'
      AND x->>'country_code'='GB'
  ) THEN
    RAISE EXCEPTION 'GB evidence missing: %', p;
  END IF;
END $$;
""")


def test_reader_authority_is_restricted(tam_reader):
    tam_reader(
        "empiredb",
        """SET SESSION AUTHORIZATION unrelated_reader;
        SELECT public.get_tam_market_observations(10);""",
        expected_error="permission denied for function get_tam_market_observations",
    )
    tam_reader(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT * FROM public.prospect_acquisitions;""",
        expected_error="permission denied for table prospect_acquisitions",
    )


def test_reader_limit_guards(tam_reader):
    tam_reader(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT public.get_tam_market_observations(0);""",
        expected_error="TAM observation limit must be 1-5000",
    )


def test_reader_security_contract(tam_reader):
    tam_reader("empiredb", r"""
DO $$
DECLARE owner_name text; secure boolean; config text[];
BEGIN
  SELECT r.rolname,p.prosecdef,p.proconfig
  INTO owner_name,secure,config
  FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
  WHERE n.nspname='public'
    AND p.proname='get_tam_market_observations';

  IF owner_name <> 'empiredb_migrator' OR secure IS NOT TRUE THEN
    RAISE EXCEPTION 'unsafe TAM reader owner/security';
  END IF;
  IF config IS NULL
     OR pg_catalog.array_to_string(config, ',') NOT LIKE 'search_path=%'
     OR pg_catalog.array_to_string(config, ',') NOT LIKE '%""%' THEN
    RAISE EXCEPTION 'empty search_path required: %', config;
  END IF;
END $$;
""")
