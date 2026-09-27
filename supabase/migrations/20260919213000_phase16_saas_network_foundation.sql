-- Phase 16 SaaS / Network Scale canonical access and usage layer.
-- Staged only: no billing execution or tenant migration.
BEGIN;

CREATE TABLE IF NOT EXISTS public.saas_tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_key text NOT NULL UNIQUE,
  display_name text NOT NULL,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','disabled')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.saas_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL
    REFERENCES public.saas_tenants(id) ON DELETE RESTRICT,
  user_key text NOT NULL,
  role text NOT NULL CHECK (
    role IN ('owner','admin','operator','analyst','viewer')
  ),
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','disabled')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(tenant_id,user_key)
);

CREATE TABLE IF NOT EXISTS public.saas_usage_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL
    REFERENCES public.saas_tenants(id) ON DELETE RESTRICT,
  metric text NOT NULL,
  value bigint NOT NULL CHECK (value >= 0),
  period text NOT NULL,
  source text NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.saas_subscription_states (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL
    REFERENCES public.saas_tenants(id) ON DELETE RESTRICT,
  plan_key text NOT NULL,
  status text NOT NULL,
  billing_provider text,
  external_subscription_ref text,
  observed_at timestamptz NOT NULL,
  source text NOT NULL
);

ALTER TABLE public.saas_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_usage_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_subscription_states ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.saas_tenants,public.saas_memberships,
  public.saas_usage_observations,public.saas_subscription_states
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.saas_tenants,public.saas_memberships,
  public.saas_usage_observations,public.saas_subscription_states
TO service_role;

COMMIT;
