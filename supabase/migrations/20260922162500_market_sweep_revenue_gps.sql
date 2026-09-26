-- Canonical aggregate Market Sweeps / Revenue GPS read model.
BEGIN;

CREATE OR REPLACE FUNCTION public.get_market_sweep_revenue_gps(
  p_window_days integer DEFAULT 7,
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  v_days integer := LEAST(GREATEST(COALESCE(p_window_days,7),1),31);
  v_limit integer := LEAST(GREATEST(COALESCE(p_limit,100),1),200);
  v_start timestamptz := clock_timestamp() - make_interval(days => v_days);
BEGIN
  RETURN jsonb_build_object(
    'schema_version','empire.market_sweep_revenue_gps.v1',
    'generated_at',clock_timestamp(),
    'window_days',v_days,
    'window_start',v_start,
    'execution_authority','none',
    'buyer_intent_inferred',false,
    'commercial_intent_inferred',false,
    'market_share_inferred',false,
    'revenue_inferred',false,
    'markets',COALESCE((
      WITH base AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          min(trim(p.niche)) AS niche,
          min(trim(p.metro)) AS metro,
          count(DISTINCT p.id)::bigint AS prospect_count,
          count(DISTINCT pel.entity_id)::bigint AS canonical_company_count,
          count(DISTINCT CASE
            WHEN p.buy_signal_score IS NOT NULL THEN p.id
          END)::bigint AS scored_prospect_count
        FROM public.prospects p
        LEFT JOIN public.prospect_entity_links pel
          ON pel.prospect_id=p.id AND pel.active=true
        WHERE trim(COALESCE(p.niche,''))<>''
          AND trim(COALESCE(p.metro,''))<>''
        GROUP BY lower(trim(p.niche)), lower(trim(p.metro))
      ),
      acquisitions AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(*)::bigint AS acquisition_count
        FROM public.prospect_acquisitions a
        JOIN public.prospects p ON p.id=a.prospect_id
        WHERE a.created_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      qualifications AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(DISTINCT q.prospect_id)::bigint AS qualification_count
        FROM public.prospect_qualifications q
        JOIN public.prospects p ON p.id=q.prospect_id
        WHERE q.status='scored'
          AND q.scored_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      reviews AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(DISTINCT r.prospect_id)::bigint AS approved_buyer_count
        FROM public.buyer_candidate_reviews r
        JOIN public.prospects p ON p.id=r.prospect_id
        WHERE r.status='approved'
          AND r.reviewed_at>=v_start
          AND COALESCE(lower(r.evidence->>'outreach_ready'),'false')='true'
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      delivered AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(DISTINCT e.intent_id)::bigint AS delivered_outreach_count
        FROM public.outbound_events e
        JOIN public.outbound_intents i ON i.id=e.intent_id
        JOIN public.prospects p ON p.id=i.prospect_id
        WHERE e.event_type='delivered'
          AND e.occurred_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      replies AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(*)::bigint AS commercial_reply_count
        FROM public.outbound_replies r
        JOIN public.outbound_intents i ON i.id=r.intent_id
        JOIN public.prospects p ON p.id=i.prospect_id
        WHERE r.classification IN ('positive','question','objection')
          AND r.received_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      terms AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(*)::bigint AS commercial_terms_count
        FROM public.commercial_terms_reviews t
        JOIN public.fulfilment_orders o ON o.id=t.fulfilment_order_id
        JOIN public.prospects p ON p.id=o.prospect_id
        WHERE t.proposed_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      payments AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(*)::bigint AS verified_payment_count
        FROM public.bsc_payment_evidence pe
        JOIN public.fulfilment_orders o ON o.id=pe.fulfilment_order_id
        JOIN public.prospects p ON p.id=o.prospect_id
        WHERE pe.verified_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      revenue AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(*)::bigint AS recognized_revenue_event_count,
          COALESCE(sum(COALESCE(e.amount_cents,0)),0)::bigint AS recognized_revenue_cents,
          COALESCE(sum(COALESCE(e.margin_cents,0)),0)::bigint AS realized_margin_cents
        FROM public.commercial_events e
        JOIN public.prospects p ON p.id=e.prospect_id
        WHERE e.event_type='revenue_recognized'
          AND e.occurred_at>=v_start
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      ),
      competitive AS (
        SELECT
          lower(trim(p.niche)) AS niche_key,
          lower(trim(p.metro)) AS metro_key,
          count(DISTINCT pel.entity_id)::bigint AS competitive_entity_count,
          count(DISTINCT s.id)::bigint AS competitive_signal_count
        FROM public.prospects p
        JOIN public.prospect_entity_links pel
          ON pel.prospect_id=p.id AND pel.active=true
        JOIN public.intelligence_signals s
          ON s.entity_id=pel.entity_id
         AND s.signal_domain='competitive_intelligence'
        GROUP BY lower(trim(p.niche)),lower(trim(p.metro))
      )
      SELECT jsonb_agg(to_jsonb(q) ORDER BY
        q.acquisition_count DESC,
        q.approved_buyer_count DESC,
        q.canonical_company_count DESC,
        q.niche,
        q.metro
      )
      FROM (
        SELECT
          b.niche,
          b.metro,
          b.prospect_count,
          b.canonical_company_count,
          b.scored_prospect_count,
          COALESCE(a.acquisition_count,0)::bigint AS acquisition_count,
          COALESCE(q.qualification_count,0)::bigint AS qualification_count,
          COALESCE(rv.approved_buyer_count,0)::bigint AS approved_buyer_count,
          COALESCE(d.delivered_outreach_count,0)::bigint AS delivered_outreach_count,
          COALESCE(r.commercial_reply_count,0)::bigint AS commercial_reply_count,
          COALESCE(t.commercial_terms_count,0)::bigint AS commercial_terms_count,
          COALESCE(pay.verified_payment_count,0)::bigint AS verified_payment_count,
          COALESCE(rev.recognized_revenue_event_count,0)::bigint AS recognized_revenue_event_count,
          COALESCE(rev.recognized_revenue_cents,0)::bigint AS recognized_revenue_cents,
          COALESCE(rev.realized_margin_cents,0)::bigint AS realized_margin_cents,
          COALESCE(c.competitive_entity_count,0)::bigint AS competitive_entity_count,
          COALESCE(c.competitive_signal_count,0)::bigint AS competitive_signal_count
        FROM base b
        LEFT JOIN acquisitions a USING(niche_key,metro_key)
        LEFT JOIN qualifications q USING(niche_key,metro_key)
        LEFT JOIN reviews rv USING(niche_key,metro_key)
        LEFT JOIN delivered d USING(niche_key,metro_key)
        LEFT JOIN replies r USING(niche_key,metro_key)
        LEFT JOIN terms t USING(niche_key,metro_key)
        LEFT JOIN payments pay USING(niche_key,metro_key)
        LEFT JOIN revenue rev USING(niche_key,metro_key)
        LEFT JOIN competitive c USING(niche_key,metro_key)
        ORDER BY
          COALESCE(a.acquisition_count,0) DESC,
          COALESCE(rv.approved_buyer_count,0) DESC,
          b.canonical_company_count DESC
        LIMIT v_limit
      ) q
    ),'[]'::jsonb)
  );
END;
$$;

REVOKE ALL ON FUNCTION public.get_market_sweep_revenue_gps(integer,integer)
FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.get_market_sweep_revenue_gps(integer,integer)
TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_market_sweep_revenue_gps(integer,integer)
IS 'Read-only canonical niche/metro market sweep and Revenue GPS aggregate. Observed evidence only; no market-share, buyer-intent, revenue, payment or execution inference.';

COMMIT;
