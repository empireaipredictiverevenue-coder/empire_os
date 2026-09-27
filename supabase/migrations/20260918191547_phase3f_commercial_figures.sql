-- Phase 3F commercial figures and read-only reporting identity.
-- Forward-only extension of the committed Phase 3F outcome/revenue schema.
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_outcome_reader'
  ) THEN
    CREATE ROLE empire_outcome_reader
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname='empire_outcome_reader_login'
  ) THEN
    CREATE ROLE empire_outcome_reader_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_outcome_reader_login PASSWORD NULL;
GRANT empire_outcome_reader TO empire_outcome_reader_login;
GRANT USAGE ON SCHEMA public TO empire_outcome_reader;
REVOKE empire_outcome_reader FROM service_role;

ALTER ROLE empire_outcome_reader_login SET statement_timeout='15s';
ALTER ROLE empire_outcome_reader_login
  SET idle_in_transaction_session_timeout='30s';

COMMENT ON ROLE empire_outcome_reader IS
'Phase 3F read-only commercial figures/outcome projection role.';
COMMENT ON ROLE empire_outcome_reader_login IS
'Phase 3F figures reader login; password provisioned out of band.';

CREATE FUNCTION public.get_phase3f_commercial_scorecard(
  p_days integer DEFAULT 30
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path='' AS $$
DECLARE
  v_since timestamptz;
  result jsonb;
BEGIN
  IF p_days IS NULL OR p_days<1 OR p_days>3650 THEN
    RAISE EXCEPTION 'scorecard days must be 1-3650';
  END IF;
  v_since := clock_timestamp() - make_interval(days=>p_days);

  WITH latest_outcomes AS (
    SELECT DISTINCT ON (co.fulfilment_order_id)
      co.fulfilment_order_id,
      co.conversion_outcome,
      co.buyer_satisfaction,
      co.recorded_at
    FROM public.commercial_outcomes co
    WHERE co.recorded_at>=v_since
    ORDER BY co.fulfilment_order_id,co.recorded_at DESC,co.id DESC
  ),
  revenue AS (
    SELECT
      ce.fulfilment_order_id,
      ce.buyer_id,
      ce.prospect_id,
      ce.amount_cents,
      ce.cost_cents,
      ce.margin_cents,
      ce.occurred_at
    FROM public.commercial_events ce
    WHERE ce.event_type='revenue_recognized'
      AND ce.occurred_at>=v_since
  ),
  totals AS (
    SELECT
      (SELECT count(*) FROM latest_outcomes) AS outcome_orders,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='won') AS won,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='lost') AS lost,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='booked') AS booked,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='qualified') AS qualified,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='no_response') AS no_response,
      (SELECT count(*) FROM latest_outcomes WHERE conversion_outcome='unknown') AS unknown,
      (SELECT avg(buyer_satisfaction)
         FROM latest_outcomes
        WHERE buyer_satisfaction IS NOT NULL) AS avg_satisfaction,
      (SELECT count(*) FROM revenue) AS revenue_orders,
      (SELECT COALESCE(sum(amount_cents),0) FROM revenue) AS revenue_cents,
      (SELECT COALESCE(sum(cost_cents),0) FROM revenue) AS cost_cents,
      (SELECT COALESCE(sum(margin_cents),0) FROM revenue) AS profit_cents
  ),
  niche_rows AS (
    SELECT
      COALESCE(p.niche,b.niche,'unknown') AS niche,
      COALESCE(p.metro,b.metro,'unknown') AS metro,
      count(*) AS recognized_orders,
      COALESCE(sum(r.amount_cents),0) AS revenue_cents,
      COALESCE(sum(r.cost_cents),0) AS cost_cents,
      COALESCE(sum(r.margin_cents),0) AS profit_cents
    FROM revenue r
    LEFT JOIN public.prospects p ON p.id=r.prospect_id
    LEFT JOIN public.buyers b ON b.id=r.buyer_id
    GROUP BY 1,2
  ),
  buyer_rows AS (
    SELECT
      r.buyer_id,
      COALESCE(b.niche,'unknown') AS niche,
      COALESCE(b.metro,'unknown') AS metro,
      count(*) AS recognized_orders,
      COALESCE(sum(r.amount_cents),0) AS revenue_cents,
      COALESCE(sum(r.cost_cents),0) AS cost_cents,
      COALESCE(sum(r.margin_cents),0) AS profit_cents
    FROM revenue r
    LEFT JOIN public.buyers b ON b.id=r.buyer_id
    GROUP BY r.buyer_id,b.niche,b.metro
  )
  SELECT jsonb_build_object(
    'period_days',p_days,
    'generated_at',clock_timestamp(),
    'currency','USD',
    'settlement_asset','USDT',
    'settlement_chain','BSC',
    'outcome_orders',t.outcome_orders,
    'won',t.won,
    'lost',t.lost,
    'booked',t.booked,
    'qualified',t.qualified,
    'no_response',t.no_response,
    'unknown',t.unknown,
    'conversion_rate',CASE WHEN t.outcome_orders>0
      THEN round(t.won::numeric/t.outcome_orders,4) ELSE 0 END,
    'conversion_rate_pct',CASE WHEN t.outcome_orders>0
      THEN round(100*t.won::numeric/t.outcome_orders,2) ELSE 0 END,
    'average_buyer_satisfaction',CASE WHEN t.avg_satisfaction IS NULL
      THEN NULL ELSE round(t.avg_satisfaction,2) END,
    'recognized_revenue_orders',t.revenue_orders,
    'actual_revenue_cents',t.revenue_cents,
    'actual_cost_cents',t.cost_cents,
    'gross_profit_cents',t.profit_cents,
    'gross_margin_rate',CASE WHEN t.revenue_cents>0
      THEN round(t.profit_cents::numeric/t.revenue_cents,4) ELSE 0 END,
    'gross_margin_pct',CASE WHEN t.revenue_cents>0
      THEN round(100*t.profit_cents::numeric/t.revenue_cents,2) ELSE 0 END,
    'revenue_per_recognized_order_cents',CASE WHEN t.revenue_orders>0
      THEN round(t.revenue_cents::numeric/t.revenue_orders) ELSE 0 END,
    'by_niche',COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'niche',niche,
        'metro',metro,
        'recognized_orders',recognized_orders,
        'actual_revenue_cents',revenue_cents,
        'actual_cost_cents',cost_cents,
        'gross_profit_cents',profit_cents,
        'gross_margin_rate',CASE WHEN revenue_cents>0
          THEN round(profit_cents::numeric/revenue_cents,4) ELSE 0 END
      ) ORDER BY profit_cents DESC,niche,metro)
      FROM niche_rows
    ),'[]'::jsonb),
    'by_buyer',COALESCE((
      SELECT jsonb_agg(jsonb_build_object(
        'buyer_id',buyer_id,
        'niche',niche,
        'metro',metro,
        'recognized_orders',recognized_orders,
        'actual_revenue_cents',revenue_cents,
        'actual_cost_cents',cost_cents,
        'gross_profit_cents',profit_cents,
        'gross_margin_rate',CASE WHEN revenue_cents>0
          THEN round(profit_cents::numeric/revenue_cents,4) ELSE 0 END
      ) ORDER BY profit_cents DESC,buyer_id)
      FROM buyer_rows
    ),'[]'::jsonb)
  )
  INTO result
  FROM totals t;

  RETURN result;
END;
$$;

REVOKE ALL ON FUNCTION public.get_phase3f_commercial_scorecard(integer)
  FROM PUBLIC,anon,authenticated,empire_outcome_recorder,
       empire_revenue_recognizer,empire_outcome_reader;
GRANT EXECUTE ON FUNCTION public.get_phase3f_commercial_scorecard(integer)
  TO service_role,empire_outcome_reader;

REVOKE ALL ON FUNCTION public.get_commercial_outcome_feedback(integer)
  FROM empire_outcome_reader;
GRANT EXECUTE ON FUNCTION public.get_commercial_outcome_feedback(integer)
  TO empire_outcome_reader;

COMMENT ON FUNCTION public.get_phase3f_commercial_scorecard(integer) IS
'Hard Phase 3F figures: revenue, cost, gross profit, margin, conversion, satisfaction, buyer and niche performance.';

COMMIT;
