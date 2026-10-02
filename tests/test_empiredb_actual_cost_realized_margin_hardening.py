"""Executable DB tests for actual-cost realized-margin hardening."""
from pathlib import Path

import pytest

from test_empiredb_materializer_bootstrap import execute


MIGRATION = Path(
    "migrations/empiredb/029_actual_cost_realized_margin_hardening.sql"
)

TERMS = "b" * 64

SCHEMA = r"""
CREATE ROLE empiredb_migrator NOLOGIN;
CREATE ROLE empiredb_app NOLOGIN;
CREATE ROLE empire_revenue_recognizer NOLOGIN NOINHERIT;
CREATE ROLE unrelated_reader NOLOGIN NOINHERIT;
GRANT USAGE, CREATE ON SCHEMA public TO empiredb_migrator;
GRANT USAGE ON SCHEMA public TO empire_revenue_recognizer, unrelated_reader;

SET ROLE empiredb_migrator;

CREATE TABLE public.fulfilment_orders(
  id uuid PRIMARY KEY,
  opportunity_id uuid,
  prospect_id uuid,
  entity_id uuid,
  buyer_id uuid,
  product_id uuid,
  state text NOT NULL DEFAULT 'accepted',
  price_cents bigint NOT NULL,
  acquisition_cost_cents bigint NOT NULL DEFAULT 0,
  fulfilment_cost_cents bigint NOT NULL DEFAULT 0,
  actual_margin_cents bigint,
  commercial_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  paid_at timestamptz,
  settled_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

CREATE TABLE public.commercial_evidence_registry(
  id uuid PRIMARY KEY,
  evidence_kind text NOT NULL,
  fulfilment_order_id uuid,
  amount_cents bigint NOT NULL,
  unit text NOT NULL,
  source_type text NOT NULL,
  source_reference text NOT NULL,
  status text NOT NULL,
  observed_at timestamptz NOT NULL
);

CREATE TABLE public.bsc_payment_requests(
  id uuid PRIMARY KEY,
  fulfilment_order_id uuid NOT NULL,
  settlement_mode text NOT NULL,
  status text NOT NULL,
  approved_at timestamptz,
  approved_by text,
  commercial_terms_sha256 text,
  amount_usdt numeric NOT NULL
);

CREATE TABLE public.bsc_payment_evidence(
  id uuid PRIMARY KEY,
  request_id uuid NOT NULL,
  transaction_hash text NOT NULL,
  verified_at timestamptz NOT NULL
);

CREATE TABLE public.bsc_escrow_agreements(
  id uuid PRIMARY KEY,
  request_id uuid NOT NULL,
  status text NOT NULL
);

CREATE TABLE public.bsc_escrow_evidence(
  id uuid PRIMARY KEY,
  agreement_id uuid NOT NULL,
  action text NOT NULL,
  transaction_hash text NOT NULL,
  verified_at timestamptz NOT NULL
);

CREATE TABLE public.commercial_outcomes(
  id uuid PRIMARY KEY,
  fulfilment_order_id uuid NOT NULL
);

CREATE TABLE public.commercial_events(
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  event_type text NOT NULL,
  opportunity_id uuid,
  job_id uuid,
  fulfilment_order_id uuid,
  prospect_id uuid,
  entity_id uuid,
  buyer_id uuid,
  product_id uuid,
  channel text,
  actor text,
  amount_cents bigint,
  cost_cents bigint,
  margin_cents bigint,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
  idempotency_key text UNIQUE
);

GRANT SELECT, UPDATE ON public.fulfilment_orders
  TO empire_revenue_recognizer;
GRANT SELECT ON public.bsc_payment_requests,
  public.bsc_payment_evidence,
  public.bsc_escrow_agreements,
  public.bsc_escrow_evidence,
  public.commercial_outcomes,
  public.commercial_events
  TO empire_revenue_recognizer;
GRANT INSERT ON public.commercial_events TO empire_revenue_recognizer;

RESET ROLE;
"""


def order_sql(order_id: str, request_id: str, evidence_id: str) -> str:
    return f"""
SET ROLE empiredb_migrator;
INSERT INTO public.fulfilment_orders(
  id,buyer_id,state,price_cents,acquisition_cost_cents,fulfilment_cost_cents,
  commercial_payload
) VALUES (
  '{order_id}','90000000-0000-0000-0000-000000000001',
  'accepted',10000,2000,1000,
  '{{"commercial_terms_sha256":"{TERMS}"}}'::jsonb
);
INSERT INTO public.bsc_payment_requests(
  id,fulfilment_order_id,settlement_mode,status,approved_at,approved_by,
  commercial_terms_sha256,amount_usdt
) VALUES (
  '{request_id}','{order_id}','direct','approved',
  pg_catalog.clock_timestamp(),'founder','{TERMS}',100
);
INSERT INTO public.bsc_payment_evidence(
  id,request_id,transaction_hash,verified_at
) VALUES (
  '{evidence_id}','{request_id}','0xtx',
  pg_catalog.clock_timestamp()
);
RESET ROLE;
"""


@pytest.fixture
def hardened(execute):
    execute("postgres", "CREATE DATABASE empiredb;")
    execute("empiredb", SCHEMA)
    migration = MIGRATION.read_text()
    execute("empiredb", migration)
    execute("empiredb", migration)
    return execute


def test_terms_time_costs_alone_cannot_create_realized_margin(hardened):
    hardened("empiredb", order_sql(
        "10000000-0000-0000-0000-000000000001",
        "20000000-0000-0000-0000-000000000001",
        "30000000-0000-0000-0000-000000000001",
    ))
    hardened(
        "empiredb",
        """
SET ROLE empire_revenue_recognizer;
SELECT public.recognize_bsc_revenue(
  '10000000-0000-0000-0000-000000000001',
  'revenue-worker'
);
""",
        expected_error=(
            "verified order-bound actual acquisition and fulfilment "
            "cost evidence required"
        ),
    )


def test_realized_margin_uses_verified_actual_evidence(hardened):
    order = "10000000-0000-0000-0000-000000000010"
    hardened("empiredb", order_sql(
        order,
        "20000000-0000-0000-0000-000000000010",
        "30000000-0000-0000-0000-000000000010",
    ))
    hardened("empiredb", f"""
SET ROLE empiredb_migrator;
INSERT INTO public.commercial_evidence_registry VALUES
 ('40000000-0000-0000-0000-000000000010','acquisition_cost',
  '{order}',1200,'per_order','provider_invoice','invoice:acq:10',
  'verified',pg_catalog.clock_timestamp()),
 ('40000000-0000-0000-0000-000000000011','fulfilment_cost',
  '{order}',800,'flat','internal_actual','internal:fulfil:10',
  'verified',pg_catalog.clock_timestamp());
RESET ROLE;
""")
    hardened("empiredb", f"""
SET ROLE empire_revenue_recognizer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.recognize_bsc_revenue(
    '{order}','revenue-worker'
  ) INTO p;
  IF p->>'decision' <> 'revenue_recognized'
     OR (p->>'cost_cents')::bigint <> 2000
     OR (p->>'margin_cents')::bigint <> 8000
     OR (p->>'actual_revenue')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'wrong realized economics: %', p;
  END IF;
END $$;
RESET ROLE;

DO $$
DECLARE
  e public.commercial_events%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
BEGIN
  SELECT * INTO e FROM public.commercial_events
   WHERE fulfilment_order_id='{order}';
  SELECT * INTO o FROM public.fulfilment_orders
   WHERE id='{order}';

  IF e.cost_cents <> 2000 OR e.margin_cents <> 8000 THEN
    RAISE EXCEPTION 'event used non-actual economics';
  END IF;
  IF e.payload->>'actual_cost_evidence_verified' <> 'true' THEN
    RAISE EXCEPTION 'actual cost attestation missing';
  END IF;
  IF e.payload->'actual_cost_evidence'->'acquisition_cost'
       ->>'source_reference' <> 'invoice:acq:10' THEN
    RAISE EXCEPTION 'acquisition cost provenance missing';
  END IF;
  IF e.payload->'actual_cost_evidence'->'fulfilment_cost'
       ->>'source_reference' <> 'internal:fulfil:10' THEN
    RAISE EXCEPTION 'fulfilment cost provenance missing';
  END IF;

  IF o.acquisition_cost_cents <> 2000
     OR o.fulfilment_cost_cents <> 1000 THEN
    RAISE EXCEPTION 'approved expected costs were overwritten';
  END IF;
  IF o.actual_margin_cents <> 8000 THEN
    RAISE EXCEPTION 'order realized margin not updated';
  END IF;
END $$;
""")


def test_explicit_zero_actual_cost_is_valid(hardened):
    order = "10000000-0000-0000-0000-000000000020"
    hardened("empiredb", order_sql(
        order,
        "20000000-0000-0000-0000-000000000020",
        "30000000-0000-0000-0000-000000000020",
    ))
    hardened("empiredb", f"""
SET ROLE empiredb_migrator;
INSERT INTO public.commercial_evidence_registry VALUES
 ('40000000-0000-0000-0000-000000000020','acquisition_cost',
  '{order}',0,'per_order','internal_actual','zero:acq:20',
  'verified',pg_catalog.clock_timestamp()),
 ('40000000-0000-0000-0000-000000000021','fulfilment_cost',
  '{order}',0,'per_order','internal_actual','zero:fulfil:20',
  'verified',pg_catalog.clock_timestamp());
RESET ROLE;
SET ROLE empire_revenue_recognizer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.recognize_bsc_revenue(
    '{order}','revenue-worker'
  ) INTO p;
  IF (p->>'cost_cents')::bigint <> 0
     OR (p->>'margin_cents')::bigint <> 10000 THEN
    RAISE EXCEPTION 'explicit zero actual cost lost: %', p;
  END IF;
END $$;
""")


@pytest.mark.parametrize("bad_rows", [
    "pending",
    "unbound",
    "non_actual",
])
def test_non_actual_or_unverified_cost_evidence_is_rejected(
    hardened,
    bad_rows,
):
    suffix = {
        "pending": "030",
        "unbound": "031",
        "non_actual": "032",
    }[bad_rows]
    order = f"10000000-0000-0000-0000-000000000{suffix}"
    hardened("empiredb", order_sql(
        order,
        f"20000000-0000-0000-0000-000000000{suffix}",
        f"30000000-0000-0000-0000-000000000{suffix}",
    ))
    target = (
        "99999999-0000-0000-0000-000000000000"
        if bad_rows == "unbound"
        else order
    )
    status = "pending" if bad_rows == "pending" else "verified"
    source = (
        "observed_contract"
        if bad_rows == "non_actual"
        else "internal_actual"
    )
    hardened("empiredb", f"""
SET ROLE empiredb_migrator;
INSERT INTO public.commercial_evidence_registry VALUES
 ('40000000-0000-0000-0000-000000000{suffix}',
  'acquisition_cost','{target}',100,'per_order',
  '{source}','bad:acq:{suffix}','{status}',pg_catalog.clock_timestamp()),
 ('50000000-0000-0000-0000-000000000{suffix}',
  'fulfilment_cost','{target}',100,'per_order',
  '{source}','bad:fulfil:{suffix}','{status}',pg_catalog.clock_timestamp());
RESET ROLE;
""")
    hardened(
        "empiredb",
        f"""SET ROLE empire_revenue_recognizer;
        SELECT public.recognize_bsc_revenue(
          '{order}','revenue-worker'
        );""",
        expected_error=(
            "verified order-bound actual acquisition and fulfilment "
            "cost evidence required"
        ),
    )


def test_existing_revenue_event_remains_idempotent_without_new_costs(hardened):
    order = "10000000-0000-0000-0000-000000000040"
    hardened("empiredb", f"""
SET ROLE empiredb_migrator;
INSERT INTO public.commercial_events(
  event_type,fulfilment_order_id,amount_cents,cost_cents,margin_cents,
  payload,idempotency_key
) VALUES (
  'revenue_recognized','{order}',10000,3000,7000,
  '{{"historical":true}}','revenue:{order}:v1'
);
RESET ROLE;
SET ROLE empire_revenue_recognizer;
DO $$
DECLARE p jsonb;
BEGIN
  SELECT public.recognize_bsc_revenue(
    '{order}','revenue-worker'
  ) INTO p;
  IF p->>'decision' <> 'existing_revenue'
     OR (p->>'cost_cents')::bigint <> 3000
     OR (p->>'margin_cents')::bigint <> 7000 THEN
    RAISE EXCEPTION 'historical idempotency changed: %', p;
  END IF;
END $$;
""")


def test_actual_cost_reader_is_narrow_and_no_direct_table_grant(hardened):
    hardened(
        "empiredb",
        """SET ROLE unrelated_reader;
        SELECT public.get_verified_actual_cost_evidence(
          '10000000-0000-0000-0000-000000000001'
        );""",
        expected_error=(
            "permission denied for function "
            "get_verified_actual_cost_evidence"
        ),
    )
    hardened(
        "empiredb",
        """SET ROLE empire_revenue_recognizer;
        SELECT * FROM public.commercial_evidence_registry;""",
        expected_error="permission denied for table commercial_evidence_registry",
    )
    hardened("empiredb", r"""
DO $$
DECLARE owner_name text; secure boolean; config text[];
BEGIN
  SELECT r.rolname,p.prosecdef,p.proconfig
  INTO owner_name,secure,config
  FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
  JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
  WHERE n.nspname='public'
    AND p.proname='get_verified_actual_cost_evidence';

  IF owner_name <> 'empiredb_migrator' OR secure IS NOT TRUE THEN
    RAISE EXCEPTION 'unsafe actual cost reader';
  END IF;
  IF config IS DISTINCT FROM ARRAY['search_path=""'] THEN
    RAISE EXCEPTION 'actual cost reader search_path unsafe: %', config;
  END IF;
END $$;
""")


def test_migration_does_not_rewrite_historical_events():
    text = MIGRATION.read_text().lower()
    assert "update public.commercial_events" not in text
    assert "delete from public.commercial_events" not in text
    assert "actual_cost_evidence_verified',true" in text
    assert "provider_invoice" in text
    assert "internal_actual" in text
