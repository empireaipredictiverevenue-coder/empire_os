-- Phase 18 Full Autonomous Revenue OS observe-only integration packets.
-- Staged only: no spend, outreach, payment, allocation or deployment authority.
BEGIN;

CREATE TABLE IF NOT EXISTS public.revenue_os_decision_packets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  packet_key text NOT NULL UNIQUE,
  recommended_workstream text,
  recommended_job_type text,
  forecast_direction text,
  capital_candidate_id text,
  demand_plan_ref text,
  enterprise_blockers text[] NOT NULL DEFAULT '{}',
  evidence_refs text[] NOT NULL,
  mode text NOT NULL DEFAULT 'OBSERVE' CHECK (mode='OBSERVE'),
  side_effects text NOT NULL DEFAULT 'none' CHECK (side_effects='none'),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.revenue_os_decision_packets ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.revenue_os_decision_packets
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.revenue_os_decision_packets
TO service_role;

COMMIT;
