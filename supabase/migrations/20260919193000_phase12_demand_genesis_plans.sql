-- Phase 12 Demand Genesis governed planning records.
-- Staged only: no publishing, outbound, ad spend or provider activation.
BEGIN;

CREATE TABLE IF NOT EXISTS public.demand_genesis_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL CHECK (
    channel IN (
      'content','aeo','geo','community','partnership',
      'agent_distribution','ads','voice'
    )
  ),
  objective text NOT NULL,
  audience text NOT NULL,
  success_metric text NOT NULL,
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  approval_required boolean NOT NULL DEFAULT true
    CHECK (approval_required=true),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','review','approved','rejected','archived')),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.demand_genesis_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id uuid NOT NULL
    REFERENCES public.demand_genesis_plans(id) ON DELETE RESTRICT,
  evidence_ref text NOT NULL,
  evidence_kind text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(plan_id,evidence_ref)
);

ALTER TABLE public.demand_genesis_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.demand_genesis_evidence ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.demand_genesis_plans,
  public.demand_genesis_evidence
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.demand_genesis_plans,
  public.demand_genesis_evidence
TO service_role;

COMMIT;
