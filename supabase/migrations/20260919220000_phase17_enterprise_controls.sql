-- Phase 17 Enterprise control-evidence and SLO observations.
-- Staged only: no infrastructure migration or production deployment.
BEGIN;

CREATE TABLE IF NOT EXISTS public.enterprise_control_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  control_key text NOT NULL,
  family text NOT NULL CHECK (
    family IN (
      'access_control','data_isolation','auditability',
      'security_monitoring','backup_dr','reliability','compliance'
    )
  ),
  tenant_key text,
  status text NOT NULL CHECK (status IN ('pass','fail','unknown')),
  evidence_refs text[] NOT NULL,
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.enterprise_slo_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  service_key text NOT NULL,
  metric text NOT NULL,
  target numeric NOT NULL,
  observed numeric,
  window text NOT NULL,
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_enterprise_control_family
  ON public.enterprise_control_evidence(
    family,tenant_key,observed_at DESC
  );

CREATE INDEX IF NOT EXISTS idx_enterprise_slo_service
  ON public.enterprise_slo_observations(
    service_key,metric,observed_at DESC
  );

ALTER TABLE public.enterprise_control_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.enterprise_slo_observations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.enterprise_control_evidence,
  public.enterprise_slo_observations
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.enterprise_control_evidence,
  public.enterprise_slo_observations
TO service_role;

COMMIT;
