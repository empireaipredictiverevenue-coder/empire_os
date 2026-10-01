"""Executable security/semantics tests for Revenue Pulse restricted reader."""
from pathlib import Path
import pytest

from test_empiredb_materializer_bootstrap import execute

MIGRATION = Path(
    "migrations/empiredb/023_revenue_pulse_restricted_reader.sql"
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

CREATE TABLE public.prospect_acquisitions(
  id uuid, created_at timestamptz);

CREATE TABLE public.prospect_qualifications(
  id uuid, status text, scored_at timestamptz);

CREATE TABLE public.buyer_candidate_reviews(
  id uuid, status text, evidence jsonb, reviewed_at timestamptz);

CREATE TABLE public.outbound_events(
  id uuid, event_type text, occurred_at timestamptz);

CREATE TABLE public.outbound_replies(
  id uuid, classification text, received_at timestamptz);

CREATE TABLE public.commercial_terms_reviews(
  id uuid, status text, proposed_at timestamptz);

CREATE TABLE public.bsc_payment_evidence(
  id uuid, verified_at timestamptz);

CREATE TABLE public.fulfilment_orders(
  id uuid, delivered_at timestamptz);

CREATE TABLE public.commercial_events(
  id uuid, event_type text, amount_cents bigint,
  margin_cents bigint, occurred_at timestamptz);

RESET ROLE;
"""

FIXTURES = r"""
SET ROLE empiredb_migrator;

INSERT INTO public.prospect_acquisitions VALUES
 ('00000000-0000-0000-0000-000000000001','2026-09-30 01:00+00');

INSERT INTO public.prospect_qualifications VALUES
 ('00000000-0000-0000-0000-000000000003','scored','2026-09-30 02:00+00');

INSERT INTO public.buyer_candidate_reviews VALUES
 ('00000000-0000-0000-0000-000000000005','approved',
  '{"outreach_ready":true,"verified_contacts":[{"bound_to_decision_maker":true,"is_valid":true,"email":"buyer@example.com"}]}',
  '2026-09-30 03:00+00');

INSERT INTO public.outbound_events VALUES
 ('00000000-0000-0000-0000-000000000007','delivered','2026-09-30 04:00+00');

INSERT INTO public.outbound_replies VALUES
 ('00000000-0000-0000-0000-000000000009','positive','2026-09-30 05:00+00'),
 ('00000000-0000-0000-0000-000000000010','question','2026-09-30 05:01+00'),
 ('00000000-0000-0000-0000-000000000011','objection','2026-09-30 05:02+00'),
 ('00000000-0000-0000-0000-000000000012','opt_out','2026-09-30 05:03+00');

INSERT INTO public.commercial_terms_reviews VALUES
 ('00000000-0000-0000-0000-000000000013','proposed','2026-09-30 06:00+00');

INSERT INTO public.bsc_payment_evidence VALUES
 ('00000000-0000-0000-0000-000000000014','2026-09-30 07:00+00');

INSERT INTO public.fulfilment_orders VALUES
 ('00000000-0000-0000-0000-000000000015','2026-09-30 08:00+00');

INSERT INTO public.commercial_events VALUES
 ('00000000-0000-0000-0000-000000000016','revenue_recognized',1000,300,'2026-09-30 09:00+00'),
 ('00000000-0000-0000-0000-000000000017','revenue_recognized',500,NULL,'2026-09-30 09:01+00');

RESET ROLE;
"""


@pytest.fixture
def pulse(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    execute("empiredb", FIXTURES)

    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", migration)

    return execute


def test_exact_reader_semantics(pulse):
    pulse("empiredb", r"""
SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
SET ROLE empire_intelligence_materializer;

DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.get_revenue_pulse_window(
    '2026-09-30 00:00+00'::timestamptz,
    '2026-10-01 00:00+00'::timestamptz
  ) INTO p;

  IF (p->>'acquisitions')::int <> 1
    OR (p->>'qualified')::int <> 1
    OR (p->>'buyer_reviews')::int <> 1
    OR (p->>'delivered_outreach')::int <> 1
    OR (p->>'commercial_replies')::int <> 3
    OR (p->>'commercial_terms')::int <> 1
    OR (p->>'verified_payments')::int <> 1
    OR (p->>'fulfilments')::int <> 1
    OR (p->>'recognized_revenue_cents')::bigint <> 1500
    OR (p->>'realized_gp_cents')::bigint <> 300
  THEN
    RAISE EXCEPTION 'Revenue Pulse projection mismatch: %', p;
  END IF;
END $$;
""")


def test_authority_stays_restricted(pulse):
    pulse(
        "empiredb",
        """SET SESSION AUTHORIZATION unrelated_reader;
        SELECT public.get_revenue_pulse_window(
          '2026-09-30'::timestamptz,
          '2026-10-01'::timestamptz);""",
        expected_error="permission denied for function get_revenue_pulse_window",
    )

    pulse(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT * FROM public.outbound_events;""",
        expected_error="permission denied for table outbound_events",
    )


def test_window_guards(pulse):
    pulse(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT public.get_revenue_pulse_window(
          '2026-10-01'::timestamptz,
          '2026-09-30'::timestamptz);""",
        expected_error="pulse window end must be after start",
    )

    pulse(
        "empiredb",
        """SET SESSION AUTHORIZATION empire_intelligence_materializer_login;
        SET ROLE empire_intelligence_materializer;
        SELECT public.get_revenue_pulse_window(
          '2026-01-01'::timestamptz,
          '2026-03-01'::timestamptz);""",
        expected_error="pulse window exceeds 31 days",
    )
