-- Phase 15 governed capital review registry.
-- Staged only: recommendation/review records cannot move funds or mutate budgets.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_capital_registry_writer'
  ) THEN
    CREATE ROLE empire_capital_registry_writer NOLOGIN NOINHERIT;
  END IF;
END $$;

GRANT USAGE ON SCHEMA public TO empire_capital_registry_writer;
REVOKE empire_capital_registry_writer FROM service_role;

CREATE TABLE IF NOT EXISTS public.capital_review_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_key text NOT NULL UNIQUE,
  candidate_id text NOT NULL,
  expected_return_cents bigint NOT NULL CHECK (expected_return_cents >= 0),
  required_capital_cents bigint NOT NULL CHECK (required_capital_cents > 0),
  downside_loss_cents bigint NOT NULL CHECK (downside_loss_cents >= 0),
  confidence numeric NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  time_to_revenue_days integer NOT NULL CHECK (time_to_revenue_days >= 0),
  risk_adjusted_score numeric NOT NULL,
  review_eligible boolean NOT NULL,
  minimum_confidence numeric NOT NULL CHECK (
    minimum_confidence >= 0 AND minimum_confidence <= 1
  ),
  maximum_downside_ratio numeric NOT NULL CHECK (
    maximum_downside_ratio >= 0
  ),
  blockers jsonb NOT NULL DEFAULT '[]'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  recommendation_only boolean NOT NULL DEFAULT true
    CHECK (recommendation_only),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  funds_movement boolean NOT NULL DEFAULT false
    CHECK (NOT funds_movement),
  budget_mutation boolean NOT NULL DEFAULT false
    CHECK (NOT budget_mutation),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE public.capital_review_registry ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.capital_review_registry
FROM PUBLIC,anon,authenticated,service_role,empire_capital_registry_writer;

GRANT SELECT ON public.capital_review_registry TO service_role;

CREATE OR REPLACE FUNCTION public.guard_capital_review_registry_append_only()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN
    RAISE EXCEPTION 'capital review registry is append-only';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_capital_review_registry_append_only
ON public.capital_review_registry;

CREATE TRIGGER guard_capital_review_registry_append_only
BEFORE UPDATE OR DELETE ON public.capital_review_registry
FOR EACH ROW EXECUTE FUNCTION
  public.guard_capital_review_registry_append_only();

CREATE OR REPLACE FUNCTION public.record_capital_review(
  p_review_key text,
  p_candidate_id text,
  p_expected_return_cents bigint,
  p_required_capital_cents bigint,
  p_downside_loss_cents bigint,
  p_confidence numeric,
  p_time_to_revenue_days integer,
  p_risk_adjusted_score numeric,
  p_review_eligible boolean,
  p_minimum_confidence numeric,
  p_maximum_downside_ratio numeric,
  p_blockers jsonb,
  p_evidence jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  r public.capital_review_registry%ROWTYPE;
BEGIN
  IF trim(COALESCE(p_review_key,''))='' THEN
    RAISE EXCEPTION 'review_key required';
  END IF;
  IF trim(COALESCE(p_candidate_id,''))='' THEN
    RAISE EXCEPTION 'candidate_id required';
  END IF;
  IF p_expected_return_cents < 0
     OR p_required_capital_cents <= 0
     OR p_downside_loss_cents < 0 THEN
    RAISE EXCEPTION 'invalid capital economics';
  END IF;
  IF p_confidence < 0 OR p_confidence > 1 THEN
    RAISE EXCEPTION 'confidence must be between zero and one';
  END IF;
  IF p_time_to_revenue_days < 0 THEN
    RAISE EXCEPTION 'time_to_revenue_days must be nonnegative';
  END IF;
  IF COALESCE(p_evidence,'{}'::jsonb)='{}'::jsonb THEN
    RAISE EXCEPTION 'capital registry requires evidence';
  END IF;

  SELECT * INTO r
  FROM public.capital_review_registry
  WHERE review_key=trim(p_review_key);

  IF FOUND THEN
    RETURN jsonb_build_object(
      'status','existing',
      'review_id',r.id,
      'review_key',r.review_key
    );
  END IF;

  INSERT INTO public.capital_review_registry(
    review_key,candidate_id,expected_return_cents,required_capital_cents,
    downside_loss_cents,confidence,time_to_revenue_days,
    risk_adjusted_score,review_eligible,minimum_confidence,
    maximum_downside_ratio,blockers,evidence
  )
  VALUES(
    trim(p_review_key),trim(p_candidate_id),p_expected_return_cents,
    p_required_capital_cents,p_downside_loss_cents,p_confidence,
    p_time_to_revenue_days,p_risk_adjusted_score,p_review_eligible,
    p_minimum_confidence,p_maximum_downside_ratio,
    COALESCE(p_blockers,'[]'::jsonb),COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'status','recorded',
    'review_id',r.id,
    'review_key',r.review_key
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_capital_review(
  text,text,bigint,bigint,bigint,numeric,integer,numeric,boolean,
  numeric,numeric,jsonb,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_capital_review(
  text,text,bigint,bigint,bigint,numeric,integer,numeric,boolean,
  numeric,numeric,jsonb,jsonb
) TO empire_capital_registry_writer;

COMMIT;
