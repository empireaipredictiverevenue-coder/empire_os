"""Executable security/semantics tests for Founder funnel restricted reader."""
from pathlib import Path

import pytest

from test_empiredb_materializer_bootstrap import execute


MIGRATION = Path(
    "migrations/empiredb/027_founder_commercial_funnel_restricted_reader.sql"
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

CREATE TABLE public.prospect_acquisitions(id uuid);
CREATE TABLE public.buyer_candidate_reviews(id uuid, status text);
CREATE TABLE public.outbound_intents(id uuid, status text);
CREATE TABLE public.outbound_events(id uuid, event_type text);
CREATE TABLE public.outbound_replies(id uuid, classification text);
CREATE TABLE public.closer_cases(id uuid, state text);
CREATE TABLE public.commercial_terms_reviews(id uuid, status text);
CREATE TABLE public.bsc_payment_requests(id uuid, status text);
CREATE TABLE public.bsc_payment_evidence(id uuid);
CREATE TABLE public.fulfilment_orders(id uuid, state text);
CREATE TABLE public.commercial_outcomes(id uuid, delivery_outcome text);
CREATE TABLE public.commercial_events(
  id uuid,
  event_type text,
  amount_cents bigint,
  cost_cents bigint,
  margin_cents bigint
);

RESET ROLE;
"""

FIXTURES = r"""
SET ROLE empiredb_migrator;

INSERT INTO public.prospect_acquisitions VALUES
 ('00000000-0000-0000-0000-000000000001'),
 ('00000000-0000-0000-0000-000000000002');

INSERT INTO public.buyer_candidate_reviews VALUES
 ('00000000-0000-0000-0000-000000000003','approved'),
 ('00000000-0000-0000-0000-000000000004','pending');

INSERT INTO public.outbound_intents VALUES
 ('00000000-0000-0000-0000-000000000005','delivered'),
 ('00000000-0000-0000-0000-000000000006','sent'),
 ('00000000-0000-0000-0000-000000000007','cancelled');

INSERT INTO public.outbound_events VALUES
 ('00000000-0000-0000-0000-000000000008','delivered');

INSERT INTO public.outbound_replies VALUES
 ('00000000-0000-0000-0000-000000000009','positive'),
 ('00000000-0000-0000-0000-000000000010','question'),
 ('00000000-0000-0000-0000-000000000011','unsubscribe');

INSERT INTO public.closer_cases VALUES
 ('00000000-0000-0000-0000-000000000012','engaged');

INSERT INTO public.commercial_terms_reviews VALUES
 ('00000000-0000-0000-0000-000000000013','approved'),
 ('00000000-0000-0000-0000-000000000014','pending');

INSERT INTO public.bsc_payment_requests VALUES
 ('00000000-0000-0000-0000-000000000015','approved');

INSERT INTO public.bsc_payment_evidence VALUES
 ('00000000-0000-0000-0000-000000000016');

INSERT INTO public.fulfilment_orders VALUES
 ('00000000-0000-0000-0000-000000000017','delivered'),
 ('00000000-0000-0000-0000-000000000018','raw');

INSERT INTO public.commercial_outcomes VALUES
 ('00000000-0000-0000-0000-000000000019','confirmed');

INSERT INTO public.commercial_events VALUES
 ('00000000-0000-0000-0000-000000000020',
  'revenue_recognized',1000,600,400),
 ('00000000-0000-0000-0000-000000000021',
  'revenue_recognized',500,NULL,NULL),
 ('00000000-0000-0000-0000-000000000022',
  'prospect_qualified_v2',NULL,NULL,NULL);

RESET ROLE;
"""


@pytest.fixture
def funnel(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    execute("empiredb", FIXTURES)
    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", migration)
    return execute


def test_exact_funnel_semantics(funnel):
    funnel("empiredb", r"""
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.get_founder_commercial_funnel() INTO p;

  IF (p->'counts'->>'prospect_acquisitions')::int <> 2
    OR (p->'counts'->>'buyer_reviews')::int <> 2
    OR (p->'counts'->>'buyer_reviews_approved')::int <> 1
    OR (p->'counts'->>'outbound_intents')::int <> 3
    OR (p->'counts'->>'outbound_delivered')::int <> 1
    OR (p->'counts'->>'commercial_replies')::int <> 2
    OR (p->'counts'->>'unsubscribe_replies')::int <> 1
    OR (p->'counts'->>'closer_cases')::int <> 1
    OR (p->'counts'->>'commercial_terms_reviews')::int <> 2
    OR (p->'counts'->>'commercial_terms_approved')::int <> 1
    OR (p->'counts'->>'payment_requests')::int <> 1
    OR (p->'counts'->>'verified_payment_evidence')::int <> 1
    OR (p->'counts'->>'fulfilment_orders')::int <> 2
    OR (p->'counts'->>'fulfilled_orders')::int <> 1
    OR (p->'counts'->>'commercial_outcomes')::int <> 1
    OR (p->'counts'->>'recognized_revenue_events')::int <> 2
    OR (p->>'recognized_revenue_cents')::bigint <> 1500
    OR (p->>'realized_margin_cents')::bigint <> 400
    OR (p->>'actual_revenue')::boolean IS NOT TRUE
    OR p->>'execution_authority' <> 'none'
  THEN
    RAISE EXCEPTION 'Founder funnel mismatch: %', p;
  END IF;

  IF (p->'outbound_status_counts'->>'delivered')::int <> 1
    OR (p->'outbound_status_counts'->>'sent')::int <> 1
    OR (p->'reply_classification_counts'->>'unsubscribe')::int <> 1
  THEN
    RAISE EXCEPTION 'Founder funnel breakdown mismatch: %', p;
  END IF;
END $$;
""")


def test_missing_revenue_stays_zero_false(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", r"""
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.get_founder_commercial_funnel() INTO p;
  IF (p->>'recognized_revenue_cents')::bigint <> 0
    OR (p->>'realized_margin_cents')::bigint <> 0
    OR (p->>'actual_revenue')::boolean IS NOT FALSE
  THEN
    RAISE EXCEPTION 'missing revenue was fabricated: %', p;
  END IF;
END $$;
""")


def test_authority_stays_restricted(funnel):
    funnel(
        "empiredb",
        """SET SESSION AUTHORIZATION unrelated_reader;
        SELECT public.get_founder_commercial_funnel();""",
        expected_error="permission denied for function get_founder_commercial_funnel",
    )
    funnel(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT * FROM public.commercial_events;""",
        expected_error="permission denied for table commercial_events",
    )
    funnel(
        "empiredb",
        """SET SESSION AUTHORIZATION empiredb_app;
        SELECT public.get_founder_commercial_funnel();""",
        expected_error="permission denied for function get_founder_commercial_funnel",
    )


def test_function_security_owner_and_search_path(funnel):
    funnel("empiredb", r"""
DO $$
DECLARE
  owner_name text;
  secure boolean;
  config text[];
BEGIN
  SELECT r.rolname,p.prosecdef,p.proconfig
    INTO owner_name,secure,config
  FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
  WHERE n.nspname='public'
    AND p.proname='get_founder_commercial_funnel';

  IF owner_name <> 'empiredb_migrator' OR secure IS NOT TRUE THEN
    RAISE EXCEPTION 'unsafe funnel function owner/security';
  END IF;
  IF config IS NULL
     OR pg_catalog.array_to_string(config, ',') NOT LIKE 'search_path=%'
     OR pg_catalog.array_to_string(config, ',') NOT LIKE '%""%' THEN
    RAISE EXCEPTION 'empty search_path required: %', config;
  END IF;
END $$;
""")


def test_migration_contains_no_mutating_business_sql():
    text = MIGRATION.read_text().lower()
    function = text.split(
        "create or replace function public.get_founder_commercial_funnel()", 1
    )[1].split("$funnel$;", 1)[0]
    for token in (
        "insert into public.",
        "update public.",
        "delete from public.",
        "call public.",
        "perform public.",
    ):
        assert token not in function
    assert "event_type='revenue_recognized'" in function
    assert "execution_authority','none'" in function
