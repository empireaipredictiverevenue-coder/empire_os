-- Phase 16 governed SaaS/network-scale readiness registry.
-- Staged only: no tenant provisioning, billing, API-key issuance or subscription mutation.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_saas_registry_writer'
  ) THEN
    CREATE ROLE empire_saas_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_saas_registry_writer;
REVOKE empire_saas_registry_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.saas_readiness_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  readiness_key text NOT NULL UNIQUE,
  tenant_id text NOT NULL,
  active_members integer NOT NULL CHECK (active_members >= 0),
  observed_monthly_usage bigint NOT NULL CHECK (observed_monthly_usage >= 0),
  observed_usage_limit bigint NOT NULL CHECK (observed_usage_limit >= 0),
  active_subscription boolean NOT NULL,
  tenant_isolation_verified boolean NOT NULL,
  white_label_requested boolean NOT NULL DEFAULT false,
  white_label_configured boolean NOT NULL DEFAULT false,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  ready_for_review boolean NOT NULL DEFAULT true CHECK (ready_for_review),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  provisioning_execution boolean NOT NULL DEFAULT false
    CHECK (NOT provisioning_execution),
  billing_execution boolean NOT NULL DEFAULT false
    CHECK (NOT billing_execution),
  api_key_issuance boolean NOT NULL DEFAULT false
    CHECK (NOT api_key_issuance),
  subscription_mutation boolean NOT NULL DEFAULT false
    CHECK (NOT subscription_mutation),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.saas_readiness_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.saas_readiness_registry
FROM PUBLIC,anon,authenticated,service_role,empire_saas_registry_writer;

GRANT SELECT ON public.saas_readiness_registry TO service_role;

CREATE OR REPLACE FUNCTION public.guard_saas_readiness_registry_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'SaaS readiness registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_saas_readiness_registry_append_only
ON public.saas_readiness_registry;

CREATE TRIGGER guard_saas_readiness_registry_append_only
BEFORE UPDATE OR DELETE ON public.saas_readiness_registry
FOR EACH ROW EXECUTE FUNCTION
  public.guard_saas_readiness_registry_append_only();

CREATE OR REPLACE FUNCTION public.record_saas_readiness(
  p_readiness_key text,
  p_tenant_id text,
  p_active_members integer,
  p_observed_monthly_usage bigint,
  p_observed_usage_limit bigint,
  p_active_subscription boolean,
  p_tenant_isolation_verified boolean,
  p_white_label_requested boolean,
  p_white_label_configured boolean,
  p_evidence_refs jsonb,
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.saas_readiness_registry%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_readiness_key,''))='' THEN
    RAISE EXCEPTION 'readiness_key required';
  END IF;
  IF trim(COALESCE(p_tenant_id,''))='' THEN
    RAISE EXCEPTION 'tenant_id required';
  END IF;
  IF p_active_members < 0 OR p_observed_monthly_usage < 0 THEN
    RAISE EXCEPTION 'members and usage must be nonnegative';
  END IF;
  IF p_observed_usage_limit IS NULL OR p_observed_usage_limit < 0 THEN
    RAISE EXCEPTION 'usage limit required and nonnegative';
  END IF;
  IF NOT COALESCE(p_active_subscription,false) THEN
    RAISE EXCEPTION 'active subscription evidence required';
  END IF;
  IF NOT COALESCE(p_tenant_isolation_verified,false) THEN
    RAISE EXCEPTION 'tenant isolation evidence required';
  END IF;
  IF COALESCE(p_white_label_requested,false)
     AND NOT COALESCE(p_white_label_configured,false) THEN
    RAISE EXCEPTION 'white label configuration evidence required';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'SaaS registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.saas_readiness_registry
  WHERE readiness_key=trim(p_readiness_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'registry_id',r.id,
      'readiness_key',r.readiness_key,
      'tenant_id',r.tenant_id
    );
  END IF;

  INSERT INTO public.saas_readiness_registry(
    readiness_key,tenant_id,active_members,observed_monthly_usage,
    observed_usage_limit,active_subscription,tenant_isolation_verified,
    white_label_requested,white_label_configured,evidence_refs,evidence
  )
  VALUES(
    trim(p_readiness_key),trim(p_tenant_id),p_active_members,
    p_observed_monthly_usage,p_observed_usage_limit,
    p_active_subscription,p_tenant_isolation_verified,
    p_white_label_requested,p_white_label_configured,
    COALESCE(p_evidence_refs,'[]'::jsonb),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'registry_id',r.id,
    'readiness_key',r.readiness_key,
    'tenant_id',r.tenant_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_saas_readiness(
  text,text,integer,bigint,bigint,boolean,boolean,boolean,boolean,jsonb,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_saas_readiness(
  text,text,integer,bigint,bigint,boolean,boolean,boolean,boolean,jsonb,jsonb
) TO empire_saas_registry_writer;

COMMIT;
