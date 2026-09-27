-- Phase 17 governed enterprise readiness registry.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_enterprise_registry_writer'
  ) THEN
    CREATE ROLE empire_enterprise_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_enterprise_registry_writer;
REVOKE empire_enterprise_registry_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.enterprise_readiness_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  readiness_key text NOT NULL UNIQUE,
  controls jsonb NOT NULL,
  slos jsonb NOT NULL,
  control_passes integer NOT NULL CHECK (control_passes >= 0),
  control_failures integer NOT NULL CHECK (control_failures >= 0),
  control_unknowns integer NOT NULL CHECK (control_unknowns >= 0),
  slo_passes integer NOT NULL CHECK (slo_passes >= 0),
  slo_failures integer NOT NULL CHECK (slo_failures >= 0),
  slo_unknowns integer NOT NULL CHECK (slo_unknowns >= 0),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.enterprise_readiness_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.enterprise_readiness_registry
FROM PUBLIC,anon,authenticated,service_role,empire_enterprise_registry_writer;

GRANT SELECT ON public.enterprise_readiness_registry TO service_role;

CREATE OR REPLACE FUNCTION public.record_enterprise_readiness(
  p_readiness_key text,
  p_controls jsonb,
  p_slos jsonb,
  p_control_passes integer,
  p_control_failures integer,
  p_control_unknowns integer,
  p_slo_passes integer,
  p_slo_failures integer,
  p_slo_unknowns integer,
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.enterprise_readiness_registry%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_readiness_key,''))='' THEN
    RAISE EXCEPTION 'readiness_key required';
  END IF;
  IF jsonb_typeof(COALESCE(p_controls,'[]'::jsonb)) <> 'array'
     OR jsonb_array_length(COALESCE(p_controls,'[]'::jsonb)) < 1 THEN
    RAISE EXCEPTION 'enterprise registry requires control evidence';
  END IF;
  IF jsonb_typeof(COALESCE(p_slos,'[]'::jsonb)) <> 'array'
     OR jsonb_array_length(COALESCE(p_slos,'[]'::jsonb)) < 1 THEN
    RAISE EXCEPTION 'enterprise registry requires SLO evidence';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'enterprise registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.enterprise_readiness_registry
  WHERE readiness_key=trim(p_readiness_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'registry_id',r.id,
      'readiness_key',r.readiness_key
    );
  END IF;

  INSERT INTO public.enterprise_readiness_registry(
    readiness_key,controls,slos,control_passes,control_failures,
    control_unknowns,slo_passes,slo_failures,slo_unknowns,evidence
  )
  VALUES(
    trim(p_readiness_key),p_controls,p_slos,p_control_passes,
    p_control_failures,p_control_unknowns,p_slo_passes,p_slo_failures,
    p_slo_unknowns,COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'registry_id',r.id,
    'readiness_key',r.readiness_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_enterprise_readiness(
  text,jsonb,jsonb,integer,integer,integer,integer,integer,integer,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_enterprise_readiness(
  text,jsonb,jsonb,integer,integer,integer,integer,integer,integer,jsonb
) TO empire_enterprise_registry_writer;

COMMIT;
