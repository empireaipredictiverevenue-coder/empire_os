-- EmpireDB 076 — ORIGINAL predictive revenue forecast registry; HELD.
-- This is an EMPIREDB-ONLY proposal, not a Supabase migration.
-- STAGED ONLY. Never auto-apply on boot, scheduled agents or deployment.
-- Founder/DBA schema approval, backup and isolated PostgreSQL 18 test required.
-- No historical predictions imported or backfilled; no money/CRM/outbound.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $guard$
BEGIN
  IF current_database() <> 'empiredb' OR pg_catalog.pg_is_in_recovery() THEN
    RAISE EXCEPTION 'REV076_CANONICAL_EMPIREDB_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname = current_user AND rolsuper) THEN
    RAISE EXCEPTION 'REV076_PRIVILEGED_DBA_REQUIRED';
  END IF;
  IF pg_catalog.to_regclass('public.predictive_forecasts') IS NOT NULL
     OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_predictive_registry_reader') THEN
    RAISE EXCEPTION 'REV076_EXISTING_REGISTRY_OR_ROLE_REVIEW_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator') THEN
    RAISE EXCEPTION 'REV076_MIGRATOR_OWNER_REQUIRED';
  END IF;
  IF NOT pg_catalog.has_schema_privilege('empiredb_migrator','public','CREATE') THEN
    RAISE EXCEPTION 'REV076_MIGRATOR_SCHEMA_CREATE_PERMISSION_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
      AND p.prosecdef IS TRUE AND p.provolatile='s'
      AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
                      WHERE rolname='empiredb_migrator')) THEN
    RAISE EXCEPTION 'REV076_TRUSTED_TENANT_RESOLVER_REQUIRED';
  END IF;
END
$guard$;

CREATE ROLE empire_predictive_registry_reader
  NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;

GRANT USAGE ON SCHEMA public TO empire_predictive_registry_reader;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
  TO empire_predictive_registry_reader;

SET LOCAL ROLE empiredb_migrator;

-- The initial registry is read-only to all business services.
-- Only a separately reviewed future append-only writer can register
-- immutable forecasts from original prospective observations.
CREATE TABLE public.predictive_forecasts (
  id uuid PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
  forecast_key text NOT NULL UNIQUE
    CHECK(length(forecast_key) BETWEEN 1 AND 180),
  model_name text NOT NULL CHECK(length(model_name) BETWEEN 1 AND 100),
  model_version text NOT NULL CHECK(length(model_version) BETWEEN 1 AND 100),
  metric text NOT NULL CHECK(length(metric) BETWEEN 1 AND 100),
  dimension_key text NOT NULL
    CHECK(dimension_key ~ '^tenant:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'),
  horizon_days integer NOT NULL CHECK(horizon_days BETWEEN 1 AND 365),
  sample_count integer NOT NULL CHECK(sample_count >= 7),
  latest_observed_value numeric,
  predicted_value numeric NOT NULL CHECK(predicted_value >= 0),
  daily_slope numeric,
  r_squared numeric NOT NULL CHECK(r_squared BETWEEN 0 AND 1),
  evidence_confidence numeric NOT NULL CHECK(evidence_confidence BETWEEN 0 AND 1),
  direction text NOT NULL CHECK(direction IN ('up','down','flat')),
  source text NOT NULL CHECK(length(source) BETWEEN 1 AND 200),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb
    CHECK(pg_catalog.jsonb_typeof(evidence) = 'object'),
  generated_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
);

ALTER TABLE public.predictive_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictive_forecasts FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.predictive_forecasts FROM PUBLIC;
GRANT SELECT ON TABLE public.predictive_forecasts
  TO empire_predictive_registry_reader;

-- Trusted session_user -> tenant mapping from EmpireDB migration 018;
-- never use caller-controlled GUC, client-supplied tenant or a global row.
CREATE POLICY predictive_registry_tenant_read
  ON public.predictive_forecasts FOR SELECT
  TO empire_predictive_registry_reader
  USING (
    public.empire_current_tenant_id() IS NOT NULL
    AND dimension_key =
      'tenant:' || public.empire_current_tenant_id()::text
  );

-- No writer login, membership, RPC or source-data copy is introduced.
-- A catalogue PASS here does NOT establish original forecast custody,
-- tenant account entitlement, actual-revenue finality or model calibration.
COMMIT;
