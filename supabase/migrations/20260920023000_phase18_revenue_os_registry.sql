-- Phase 18 governed Revenue OS decision-packet registry.
-- Staged only: no spend, outreach, payment, allocation or deployment execution.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_revenue_os_registry_writer'
  ) THEN
    CREATE ROLE empire_revenue_os_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_revenue_os_registry_writer;
REVOKE empire_revenue_os_registry_writer FROM service_role;

ALTER TABLE public.revenue_os_decision_packets
  ADD COLUMN IF NOT EXISTS ready_for_operator_review boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS readiness_blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS spend_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS outreach_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS payment_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS allocation_execution boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS deployment_execution boolean NOT NULL DEFAULT false;

ALTER TABLE public.revenue_os_decision_packets
  DROP CONSTRAINT IF EXISTS revenue_os_spend_execution_check,
  ADD CONSTRAINT revenue_os_spend_execution_check
    CHECK (NOT spend_execution),
  DROP CONSTRAINT IF EXISTS revenue_os_outreach_execution_check,
  ADD CONSTRAINT revenue_os_outreach_execution_check
    CHECK (NOT outreach_execution),
  DROP CONSTRAINT IF EXISTS revenue_os_payment_execution_check,
  ADD CONSTRAINT revenue_os_payment_execution_check
    CHECK (NOT payment_execution),
  DROP CONSTRAINT IF EXISTS revenue_os_allocation_execution_check,
  ADD CONSTRAINT revenue_os_allocation_execution_check
    CHECK (NOT allocation_execution),
  DROP CONSTRAINT IF EXISTS revenue_os_deployment_execution_check,
  ADD CONSTRAINT revenue_os_deployment_execution_check
    CHECK (NOT deployment_execution);

CREATE OR REPLACE FUNCTION public.guard_revenue_os_packets_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'Revenue OS packet registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_revenue_os_packets_append_only
ON public.revenue_os_decision_packets;

CREATE TRIGGER guard_revenue_os_packets_append_only
BEFORE UPDATE OR DELETE ON public.revenue_os_decision_packets
FOR EACH ROW EXECUTE FUNCTION
  public.guard_revenue_os_packets_append_only();

REVOKE ALL ON public.revenue_os_decision_packets
FROM empire_revenue_os_registry_writer;

CREATE OR REPLACE FUNCTION public.record_revenue_os_packet(
  p_packet_key text,
  p_recommended_workstream text,
  p_recommended_job_type text,
  p_forecast_direction text,
  p_capital_candidate_id text,
  p_demand_plan_ref text,
  p_enterprise_blockers jsonb,
  p_evidence_refs jsonb,
  p_ready_for_operator_review boolean,
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.revenue_os_decision_packets%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_packet_key,''))='' THEN
    RAISE EXCEPTION 'packet_key required';
  END IF;
  IF jsonb_typeof(COALESCE(p_evidence_refs,'[]'::jsonb)) <> 'array'
     OR jsonb_array_length(COALESCE(p_evidence_refs,'[]'::jsonb)) < 1 THEN
    RAISE EXCEPTION 'integration packet requires evidence';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'Revenue OS registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.revenue_os_decision_packets
  WHERE packet_key=trim(p_packet_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'packet_id',r.id,
      'packet_key',r.packet_key
    );
  END IF;

  INSERT INTO public.revenue_os_decision_packets(
    packet_key,recommended_workstream,recommended_job_type,
    forecast_direction,capital_candidate_id,demand_plan_ref,
    enterprise_blockers,evidence_refs,ready_for_operator_review,
    readiness_blockers,evidence
  )
  VALUES(
    trim(p_packet_key),NULLIF(trim(COALESCE(p_recommended_workstream,'')),''),
    NULLIF(trim(COALESCE(p_recommended_job_type,'')),''),
    NULLIF(trim(COALESCE(p_forecast_direction,'')),''),
    NULLIF(trim(COALESCE(p_capital_candidate_id,'')),''),
    NULLIF(trim(COALESCE(p_demand_plan_ref,'')),''),
    ARRAY(
      SELECT jsonb_array_elements_text(
        COALESCE(p_enterprise_blockers,'[]'::jsonb)
      )
    ),
    ARRAY(
      SELECT jsonb_array_elements_text(
        COALESCE(p_evidence_refs,'[]'::jsonb)
      )
    ),
    COALESCE(p_ready_for_operator_review,false),
    CASE
      WHEN COALESCE(p_ready_for_operator_review,false)
      THEN '[]'::jsonb
      ELSE COALESCE(p_enterprise_blockers,'[]'::jsonb)
    END,
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'packet_id',r.id,
    'packet_key',r.packet_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_revenue_os_packet(
  text,text,text,text,text,text,jsonb,jsonb,boolean,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_revenue_os_packet(
  text,text,text,text,text,text,jsonb,jsonb,boolean,jsonb
) TO empire_revenue_os_registry_writer;

COMMIT;
