-- EmpireDB REV078: prospective original forecast registration, HELD.
-- Depends on founder-reviewed REV076 registry. NOT approved for live apply.
-- A DB timestamp is first-party custody, NOT independently attested time.
-- Nothing here certifies source truth, financial outcomes or model accuracy.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
BEGIN
  IF current_database()<>'empiredb' OR pg_catalog.pg_is_in_recovery()
     OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname=current_user AND rolsuper) THEN
    RAISE EXCEPTION 'REV078_CANONICAL_PRIVILEGED_DBA_REQUIRED';
  END IF;
  IF pg_catalog.to_regclass('public.predictive_forecasts') IS NULL
     OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
     OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_class
       WHERE oid=pg_catalog.to_regclass('public.predictive_forecasts')
         AND relrowsecurity AND relforcerowsecurity
         AND relowner=(SELECT oid FROM pg_catalog.pg_roles
                       WHERE rolname='empiredb_migrator')) THEN
    RAISE EXCEPTION 'REV078_NATIVE_REGISTRY_AND_FORCE_RLS_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
     WHERE rolname='empire_predictive_registry_reader'
       AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
       AND NOT rolinherit) OR NOT EXISTS(
     SELECT 1 FROM pg_catalog.pg_policies
     WHERE schemaname='public' AND tablename='predictive_forecasts'
       AND policyname='predictive_registry_tenant_read'
       AND cmd='SELECT'
  ) THEN
    RAISE EXCEPTION 'REV078_ORIGINAL_RESTRICTED_REGISTRY_READER_REQUIRED';
  END IF;
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
     WHERE p.oid=pg_catalog.to_regprocedure('public.empire_current_tenant_id()')
       AND p.prosecdef AND p.provolatile='s'
       AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
           WHERE rolname='empiredb_migrator')) THEN
    RAISE EXCEPTION 'REV078_TRUSTED_SESSION_TENANT_REQUIRED';
  END IF;
  IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles
       WHERE rolname='empire_predictive_forecast_registrar')
     OR pg_catalog.to_regprocedure(
       'public.register_predictive_revenue_forecast_v1(text,text,date,integer,integer,numeric,numeric,numeric,text,text)') IS NOT NULL THEN
    RAISE EXCEPTION 'REV078_EXISTING_REGISTRAR_REVIEW_REQUIRED';
  END IF;
END
$guard$;

CREATE ROLE empire_predictive_forecast_registrar
 NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
 NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO empire_predictive_forecast_registrar;
-- The private adapter checks the same trusted session_user -> tenant
-- identity before invoking the definer; never grant source-table SELECT.
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_predictive_forecast_registrar;
SET LOCAL ROLE empiredb_migrator;

-- Because registry is FORCE RLS, owner also needs a strict INSERT policy;
-- the only business write surface is the guarded SECURITY DEFINER function.
CREATE POLICY predictive_registry_prospective_insert
 ON public.predictive_forecasts FOR INSERT
 TO empiredb_migrator
 WITH CHECK (
   public.empire_current_tenant_id() IS NOT NULL
   AND dimension_key =
     'tenant:' || public.empire_current_tenant_id()::text
 );

CREATE FUNCTION public.register_predictive_revenue_forecast_v1(
 p_model_name text,
 p_model_version text,
 p_observed_through date,
 p_horizon_days integer,
 p_sample_count integer,
 p_predicted_value_cents numeric,
 p_r_squared numeric,
 p_evidence_confidence numeric,
 p_direction text,
 p_source_evidence_sha256 text
)
RETURNS TABLE (registration_ref text, registered_at timestamptz)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=''
AS $register$
DECLARE
 trusted uuid;
 clock_at timestamptz;
 utc_day date;
 target_day date;
 key text;
 captured_at timestamptz;
BEGIN
 trusted := public.empire_current_tenant_id();
 IF trusted IS NULL THEN
    RAISE EXCEPTION 'REV078_TRUSTED_TENANT_REQUIRED';
 END IF;
 clock_at := pg_catalog.clock_timestamp();
 utc_day := (clock_at AT TIME ZONE 'UTC')::date;
 IF p_observed_through IS NULL
    OR p_observed_through<utc_day-7
    OR p_observed_through>=utc_day THEN
    RAISE EXCEPTION 'REV078_RECENT_COMPLETED_SOURCE_DAY_REQUIRED';
 END IF;
 -- Horizon is measured from the DB registration UTC date, consistent
 -- with existing enterprise_forecast_shadow_scorecard issuance semantics.
 -- Observed-through is *input freshness*, never the prediction clock.
 IF p_horizon_days IS NULL OR p_horizon_days NOT BETWEEN 1 AND 365
    OR p_sample_count IS NULL OR p_sample_count NOT BETWEEN 7 AND 120 THEN
    RAISE EXCEPTION 'REV078_PROSPECTIVE_FORECAST_HORIZON_REQUIRED';
 END IF;
 IF p_model_name IS NULL OR pg_catalog.length(p_model_name) NOT BETWEEN 1 AND 100
    OR p_model_version IS NULL OR pg_catalog.length(p_model_version) NOT BETWEEN 1 AND 100
    OR p_model_name !~ '^[a-zA-Z0-9._-]+$'
    OR p_model_version !~ '^[a-zA-Z0-9._-]+$'
    OR p_direction NOT IN ('up','down','flat')
    OR p_direction IS NULL THEN
    RAISE EXCEPTION 'REV078_MODEL_METADATA_INVALID';
 END IF;
 -- Existing EmpireDB registry reader admits only exact INTEGER cents.
 -- Fractional cents would register but fail on the original reader.
 IF p_predicted_value_cents IS NULL OR p_predicted_value_cents<0
    OR p_predicted_value_cents>1000000000000000
    OR p_predicted_value_cents<>pg_catalog.trunc(p_predicted_value_cents)
    OR p_r_squared IS NULL OR p_r_squared<0 OR p_r_squared>1
    OR p_evidence_confidence IS NULL OR p_evidence_confidence<0
    OR p_evidence_confidence>1 THEN
    RAISE EXCEPTION 'REV078_NUMERIC_FORECAST_INVALID';
 END IF;
 IF p_source_evidence_sha256 IS NULL
    OR p_source_evidence_sha256 !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'REV078_BOUNDED_SOURCE_FINGERPRINT_REQUIRED';
 END IF;
 target_day := utc_day+p_horizon_days;
 -- There is only ONE first registered forecast for a given tenant,
 -- model/version, target UTC day and horizon. Source observation date
 -- cannot be varied to submit competing predictions for the same outcome.
 -- Unique forecast_key prevents concurrent replacements or replay.
 key := 'efr:' || pg_catalog.md5(
     trusted::text || ':' || p_model_name || ':' || p_model_version || ':'
     || target_day::text || ':' || p_horizon_days::text
 );
 INSERT INTO public.predictive_forecasts(
    forecast_key,model_name,model_version,metric,dimension_key,
    horizon_days,sample_count,predicted_value,r_squared,
    evidence_confidence,direction,source,evidence,generated_at
 ) VALUES (
    key,p_model_name,p_model_version,'recognized_revenue_cents',
    'tenant:'||trusted::text,p_horizon_days,p_sample_count,
    p_predicted_value_cents,p_r_squared,p_evidence_confidence,p_direction,
    'empiredb_prospective_registration_source_claim_unverified',
    pg_catalog.jsonb_build_object(
       'status','SOURCE_FINGERPRINT_UNAUTHENTICATED',
       'source_evidence_sha256',p_source_evidence_sha256,
       'observed_through_utc',p_observed_through::text,
       'target_utc_date',target_day::text,
       'horizon_basis','registration_utc_day',
       'db_registration_clock',true,
       'independent_timestamp_custody',false,
       'original_source_authentication',false,
       'independent_financial_actuals',false,
       'calibration_authorized',false
    ),
    clock_at
 );
 -- No RETURNING: table has FORCE RLS and intentionally no business SELECT
 -- policy for definer; registration timestamp is already DB CLOCK_AT.
 captured_at := clock_at;
 RETURN QUERY SELECT key,captured_at;
END;
$register$;

REVOKE ALL ON FUNCTION public.register_predictive_revenue_forecast_v1(
 text,text,date,integer,integer,numeric,numeric,numeric,text,text
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.register_predictive_revenue_forecast_v1(
 text,text,date,integer,integer,numeric,numeric,numeric,text,text
) TO empire_predictive_forecast_registrar;

-- Business logins gain NO registry table rights and NO memberships here.
-- PostgreSQL owner can still alter schema: not an independent timestamp
-- authority. Independent immutable custody requires separate approval.
RESET ROLE;
COMMIT;
