-- Phase 10 Predictive Cloud V3 governed forecast registry.
-- Staged only: evidence-backed forecast persistence, no commercial execution.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_predictive_registry_writer'
  ) THEN
    CREATE ROLE empire_predictive_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_predictive_registry_writer;
REVOKE empire_predictive_registry_writer FROM service_role;

ALTER TABLE public.predictive_forecasts
  ADD COLUMN IF NOT EXISTS forecast_key text,
  ADD COLUMN IF NOT EXISTS model_name text,
  ADD COLUMN IF NOT EXISTS model_version text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_predictive_forecast_key
  ON public.predictive_forecasts(forecast_key)
  WHERE forecast_key IS NOT NULL;

REVOKE ALL ON public.predictive_forecasts
FROM empire_predictive_registry_writer;

CREATE OR REPLACE FUNCTION public.record_predictive_forecast(
  p_forecast_key text,
  p_model_name text,
  p_model_version text,
  p_metric text,
  p_dimension_key text,
  p_horizon_days integer,
  p_sample_count integer,
  p_latest_observed_value numeric,
  p_predicted_value numeric,
  p_daily_slope numeric,
  p_r_squared numeric,
  p_evidence_confidence numeric,
  p_direction text,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  f public.predictive_forecasts%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_forecast_key,''))='' THEN
    RAISE EXCEPTION 'forecast_key required';
  END IF;
  IF trim(COALESCE(p_model_name,''))='' THEN
    RAISE EXCEPTION 'model_name required';
  END IF;
  IF trim(COALESCE(p_model_version,''))='' THEN
    RAISE EXCEPTION 'model_version required';
  END IF;
  IF trim(COALESCE(p_metric,''))='' THEN
    RAISE EXCEPTION 'metric required';
  END IF;
  IF p_horizon_days NOT BETWEEN 1 AND 365 THEN
    RAISE EXCEPTION 'forecast horizon out of bounds';
  END IF;
  IF p_sample_count < 7 THEN
    RAISE EXCEPTION 'forecast evidence gate not satisfied';
  END IF;
  IF p_predicted_value IS NULL THEN
    RAISE EXCEPTION 'predicted_value required';
  END IF;
  IF p_direction NOT IN ('up','down','flat') THEN
    RAISE EXCEPTION 'registered forecast direction must be bounded';
  END IF;
  IF p_r_squared IS NULL OR p_r_squared < 0 OR p_r_squared > 1 THEN
    RAISE EXCEPTION 'r_squared required between zero and one';
  END IF;
  IF p_evidence_confidence IS NULL
     OR p_evidence_confidence < 0
     OR p_evidence_confidence > 1 THEN
    RAISE EXCEPTION 'evidence_confidence required between zero and one';
  END IF;

  SELECT * INTO f
  FROM public.predictive_forecasts
  WHERE forecast_key=trim(p_forecast_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'forecast_id',f.id,
      'forecast_key',f.forecast_key
    );
  END IF;

  INSERT INTO public.predictive_forecasts(
    forecast_key,
    model_name,
    model_version,
    metric,
    dimension_key,
    horizon_days,
    sample_count,
    latest_observed_value,
    predicted_value,
    daily_slope,
    r_squared,
    evidence_confidence,
    direction,
    reason,
    source,
    evidence
  )
  VALUES(
    trim(p_forecast_key),
    trim(p_model_name),
    trim(p_model_version),
    trim(p_metric),
    COALESCE(NULLIF(trim(p_dimension_key),''),'global'),
    p_horizon_days,
    p_sample_count,
    p_latest_observed_value,
    p_predicted_value,
    p_daily_slope,
    p_r_squared,
    p_evidence_confidence,
    p_direction,
    NULL,
    'canonical_observed_time_series',
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO f;

  RETURN jsonb_build_object(
    'status','recorded',
    'forecast_id',f.id,
    'forecast_key',f.forecast_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_predictive_forecast(
  text,text,text,text,text,integer,integer,numeric,numeric,numeric,
  numeric,numeric,text,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_predictive_forecast(
  text,text,text,text,text,integer,integer,numeric,numeric,numeric,
  numeric,numeric,text,jsonb
) TO empire_predictive_registry_writer;

COMMIT;
