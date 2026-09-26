-- Phase 12 governed demand-plan registry.
-- Staged only: no publishing, outbound, ad spend or provider activation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_demand_registry_writer'
  ) THEN
    CREATE ROLE empire_demand_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_demand_registry_writer;
REVOKE empire_demand_registry_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.demand_plan_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id text NOT NULL UNIQUE,
  channel text NOT NULL,
  objective text NOT NULL,
  audience text NOT NULL,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  success_metric text NOT NULL,
  evidence_score numeric NOT NULL CHECK (
    evidence_score >= 0 AND evidence_score <= 1
  ),
  readiness_reason text NOT NULL,
  missing_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  approval_required boolean NOT NULL DEFAULT true
    CHECK (approval_required),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  publishing_enabled boolean NOT NULL DEFAULT false
    CHECK (NOT publishing_enabled),
  outbound_enabled boolean NOT NULL DEFAULT false
    CHECK (NOT outbound_enabled),
  ad_spend_enabled boolean NOT NULL DEFAULT false
    CHECK (NOT ad_spend_enabled),
  provider_activation_enabled boolean NOT NULL DEFAULT false
    CHECK (NOT provider_activation_enabled),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.demand_plan_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.demand_plan_registry
FROM PUBLIC,anon,authenticated,service_role,empire_demand_registry_writer;

GRANT SELECT ON public.demand_plan_registry TO service_role;

CREATE OR REPLACE FUNCTION public.guard_demand_plan_registry_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'demand plan registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_demand_plan_registry_append_only
ON public.demand_plan_registry;

CREATE TRIGGER guard_demand_plan_registry_append_only
BEFORE UPDATE OR DELETE ON public.demand_plan_registry
FOR EACH ROW EXECUTE FUNCTION
  public.guard_demand_plan_registry_append_only();

CREATE OR REPLACE FUNCTION public.record_demand_plan_registry(
  p_plan_id text,
  p_channel text,
  p_objective text,
  p_audience text,
  p_evidence_refs jsonb,
  p_success_metric text,
  p_evidence_score numeric,
  p_readiness_reason text,
  p_missing_evidence jsonb,
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.demand_plan_registry%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_plan_id,''))='' THEN
    RAISE EXCEPTION 'plan_id required';
  END IF;
  IF trim(COALESCE(p_channel,''))='' THEN
    RAISE EXCEPTION 'channel required';
  END IF;
  IF trim(COALESCE(p_objective,''))='' THEN
    RAISE EXCEPTION 'objective required';
  END IF;
  IF trim(COALESCE(p_audience,''))='' THEN
    RAISE EXCEPTION 'audience required';
  END IF;
  IF trim(COALESCE(p_success_metric,''))='' THEN
    RAISE EXCEPTION 'success_metric required';
  END IF;
  IF p_evidence_score IS NULL OR p_evidence_score < 0.5 THEN
    RAISE EXCEPTION 'demand plan not review-ready';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'demand registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.demand_plan_registry
  WHERE plan_id=trim(p_plan_id);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'registry_id',r.id,
      'plan_id',r.plan_id
    );
  END IF;

  INSERT INTO public.demand_plan_registry(
    plan_id,channel,objective,audience,evidence_refs,success_metric,
    evidence_score,readiness_reason,missing_evidence,evidence
  )
  VALUES(
    trim(p_plan_id),trim(p_channel),trim(p_objective),trim(p_audience),
    COALESCE(p_evidence_refs,'[]'::jsonb),trim(p_success_metric),
    p_evidence_score,trim(p_readiness_reason),
    COALESCE(p_missing_evidence,'[]'::jsonb),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'registry_id',r.id,
    'plan_id',r.plan_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_demand_plan_registry(
  text,text,text,text,jsonb,text,numeric,text,jsonb,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_demand_plan_registry(
  text,text,text,text,jsonb,text,numeric,text,jsonb,jsonb
) TO empire_demand_registry_writer;

COMMIT;
