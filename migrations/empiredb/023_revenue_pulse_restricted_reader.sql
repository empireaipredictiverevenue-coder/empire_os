-- Canonical bounded Revenue Pulse projection for the restricted materializer.
-- Read-only intelligence only: no send, payment, terms, fulfilment or revenue authority.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $pulse_guard$
DECLARE
  relation text;
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin
      AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'Revenue Pulse requires guarded non-login migrator';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer'
      AND NOT rolcanlogin
      AND NOT rolsuper
  ) OR NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer_login'
      AND rolcanlogin
      AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'Revenue Pulse materializer roles missing or unsafe';
  END IF;

  IF NOT pg_catalog.pg_has_role(
      'empire_intelligence_materializer_login',
      'empire_intelligence_materializer',
      'MEMBER'
  ) THEN
    RAISE EXCEPTION 'materializer login lacks capability membership';
  END IF;

  IF pg_catalog.pg_has_role(
      'empire_intelligence_materializer',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empire_intelligence_materializer_login',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empiredb_app',
      'empiredb_migrator',
      'MEMBER'
  ) OR pg_catalog.pg_has_role(
      'empiredb_app',
      'empire_intelligence_materializer',
      'MEMBER'
  ) THEN
    RAISE EXCEPTION 'Revenue Pulse authority boundary violated';
  END IF;

  FOREACH relation IN ARRAY ARRAY[
    'public.prospect_acquisitions',
    'public.prospect_qualifications',
    'public.buyer_candidate_reviews',
    'public.outbound_events',
    'public.outbound_replies',
    'public.commercial_terms_reviews',
    'public.bsc_payment_evidence',
    'public.fulfilment_orders',
    'public.commercial_events'
  ] LOOP
    IF pg_catalog.to_regclass(relation) IS NULL THEN
      RAISE EXCEPTION 'Revenue Pulse relation missing: %', relation;
    END IF;
  END LOOP;
END;
$pulse_guard$;

CREATE OR REPLACE FUNCTION public.get_revenue_pulse_window(
  p_start timestamp with time zone,
  p_end timestamp with time zone
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $pulse$
DECLARE
  payload jsonb;
BEGIN
  IF p_start IS NULL OR p_end IS NULL THEN
    RAISE EXCEPTION 'pulse window timestamps required';
  END IF;

  IF p_end <= p_start THEN
    RAISE EXCEPTION 'pulse window end must be after start';
  END IF;

  IF p_end - p_start > interval '31 days' THEN
    RAISE EXCEPTION 'pulse window exceeds 31 days';
  END IF;

  SELECT pg_catalog.jsonb_build_object(
    'acquisitions',
      (SELECT count(*)
       FROM public.prospect_acquisitions a
       WHERE a.created_at >= p_start AND a.created_at < p_end),

    'qualified',
      (SELECT count(*)
       FROM public.prospect_qualifications q
       WHERE q.status = 'scored'
         AND q.scored_at >= p_start AND q.scored_at < p_end),

    'buyer_reviews',
      (SELECT count(*)
       FROM public.buyer_candidate_reviews r
       WHERE r.status = 'approved'
         AND r.reviewed_at >= p_start AND r.reviewed_at < p_end
         AND pg_catalog.jsonb_typeof(r.evidence) = 'object'
         AND r.evidence->'outreach_ready' = 'true'::jsonb
         AND EXISTS (
           SELECT 1
           FROM pg_catalog.jsonb_array_elements(
             CASE
               WHEN pg_catalog.jsonb_typeof(r.evidence->'verified_contacts') = 'array'
               THEN r.evidence->'verified_contacts'
               ELSE '[]'::jsonb
             END
           ) AS c(contact)
           WHERE pg_catalog.jsonb_typeof(c.contact) = 'object'
             AND c.contact->'bound_to_decision_maker' = 'true'::jsonb
             AND c.contact->'is_valid' = 'true'::jsonb
             AND pg_catalog.btrim(COALESCE(c.contact->>'email','')) <> ''
         )),

    'delivered_outreach',
      (SELECT count(*)
       FROM public.outbound_events e
       WHERE e.event_type = 'delivered'
         AND e.occurred_at >= p_start AND e.occurred_at < p_end),

    'commercial_replies',
      (SELECT count(*)
       FROM public.outbound_replies r
       WHERE pg_catalog.lower(pg_catalog.btrim(COALESCE(r.classification,'')))
             IN ('positive','question','objection')
         AND r.received_at >= p_start AND r.received_at < p_end),

    'commercial_terms',
      (SELECT count(*)
       FROM public.commercial_terms_reviews t
       WHERE t.proposed_at >= p_start AND t.proposed_at < p_end),

    'verified_payments',
      (SELECT count(*)
       FROM public.bsc_payment_evidence p
       WHERE p.verified_at >= p_start AND p.verified_at < p_end),

    'fulfilments',
      (SELECT count(*)
       FROM public.fulfilment_orders f
       WHERE f.delivered_at >= p_start AND f.delivered_at < p_end),

    'recognized_revenue_cents',
      (SELECT COALESCE(sum(e.amount_cents),0)
       FROM public.commercial_events e
       WHERE e.event_type = 'revenue_recognized'
         AND e.occurred_at >= p_start AND e.occurred_at < p_end),

    'realized_gp_cents',
      (SELECT COALESCE(sum(e.margin_cents),0)
       FROM public.commercial_events e
       WHERE e.event_type = 'revenue_recognized'
         AND e.occurred_at >= p_start AND e.occurred_at < p_end)
  )
  INTO payload;

  RETURN payload;
END;
$pulse$;

REVOKE ALL ON FUNCTION public.get_revenue_pulse_window(
  timestamp with time zone, timestamp with time zone
) FROM PUBLIC, empire_intelligence_materializer_login, empiredb_app;

GRANT EXECUTE ON FUNCTION public.get_revenue_pulse_window(
  timestamp with time zone, timestamp with time zone
) TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_revenue_pulse_window(
  timestamp with time zone, timestamp with time zone
) IS 'Bounded read-only canonical Revenue Pulse projection. No execution or accounting authority.';

COMMIT;
