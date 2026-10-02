-- Founder commercial funnel restricted reader.
-- Read-only projection only: no send, terms, payment, fulfilment, accounting,
-- revenue-recognition, or authority-expansion capability.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $funnel_guard$
DECLARE
  relation text;
  privilege text;
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'EmpireDB required';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'commercial funnel requires guarded non-login migrator';
  END IF;

  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer'
      AND NOT rolcanlogin AND NOT rolsuper
  ) OR NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_intelligence_materializer_login'
      AND rolcanlogin AND NOT rolsuper
  ) THEN
    RAISE EXCEPTION 'commercial funnel materializer roles missing or unsafe';
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
    RAISE EXCEPTION 'commercial funnel authority boundary violated';
  END IF;

  FOREACH relation IN ARRAY ARRAY[
    'public.prospect_acquisitions',
    'public.buyer_candidate_reviews',
    'public.outbound_intents',
    'public.outbound_events',
    'public.outbound_replies',
    'public.closer_cases',
    'public.commercial_terms_reviews',
    'public.bsc_payment_requests',
    'public.bsc_payment_evidence',
    'public.fulfilment_orders',
    'public.commercial_outcomes',
    'public.commercial_events'
  ] LOOP
    IF pg_catalog.to_regclass(relation) IS NULL THEN
      RAISE EXCEPTION 'commercial funnel relation missing: %', relation;
    END IF;
    FOREACH privilege IN ARRAY ARRAY[
      'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
    ] LOOP
      IF pg_catalog.has_table_privilege(
          'empire_intelligence_materializer',
          relation,
          privilege
      ) THEN
        RAISE EXCEPTION
          'unexpected materializer table authority: % %',
          relation, privilege;
      END IF;
    END LOOP;
  END LOOP;
END;
$funnel_guard$;

CREATE OR REPLACE FUNCTION public.get_founder_commercial_funnel()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $funnel$
DECLARE
  payload jsonb;
BEGIN
  SELECT pg_catalog.jsonb_build_object(
    'schema_version','empire.founder_commercial_funnel.v1',
    'generated_at',pg_catalog.clock_timestamp(),
    'counts',pg_catalog.jsonb_build_object(
      'prospect_acquisitions',
        (SELECT count(*) FROM public.prospect_acquisitions),
      'buyer_reviews',
        (SELECT count(*) FROM public.buyer_candidate_reviews),
      'buyer_reviews_approved',
        (SELECT count(*) FROM public.buyer_candidate_reviews
          WHERE status='approved'),
      'outbound_intents',
        (SELECT count(*) FROM public.outbound_intents),
      'outbound_delivered',
        (SELECT count(*) FROM public.outbound_intents
          WHERE status='delivered'),
      'commercial_replies',
        (SELECT count(*) FROM public.outbound_replies
          WHERE classification IN ('positive','question','objection')),
      'unsubscribe_replies',
        (SELECT count(*) FROM public.outbound_replies
          WHERE classification='unsubscribe'),
      'closer_cases',
        (SELECT count(*) FROM public.closer_cases),
      'commercial_terms_reviews',
        (SELECT count(*) FROM public.commercial_terms_reviews),
      'commercial_terms_approved',
        (SELECT count(*) FROM public.commercial_terms_reviews
          WHERE status='approved'),
      'payment_requests',
        (SELECT count(*) FROM public.bsc_payment_requests),
      'verified_payment_evidence',
        (SELECT count(*) FROM public.bsc_payment_evidence),
      'fulfilment_orders',
        (SELECT count(*) FROM public.fulfilment_orders),
      'fulfilled_orders',
        (SELECT count(*) FROM public.fulfilment_orders
          WHERE state IN (
            'delivered','confirmed','invoiced','paid','settled',
            'outcome_captured'
          )),
      'commercial_outcomes',
        (SELECT count(*) FROM public.commercial_outcomes),
      'recognized_revenue_events',
        (SELECT count(*) FROM public.commercial_events
          WHERE event_type='revenue_recognized')
    ),
    'outbound_status_counts',
      COALESCE((
        SELECT pg_catalog.jsonb_object_agg(status,total)
        FROM (
          SELECT status,count(*) AS total
          FROM public.outbound_intents
          GROUP BY status
          ORDER BY status
        ) q
      ),'{}'::jsonb),
    'reply_classification_counts',
      COALESCE((
        SELECT pg_catalog.jsonb_object_agg(classification,total)
        FROM (
          SELECT classification,count(*) AS total
          FROM public.outbound_replies
          GROUP BY classification
          ORDER BY classification
        ) q
      ),'{}'::jsonb),
    'recognized_revenue_cents',
      (SELECT COALESCE(sum(amount_cents),0)
       FROM public.commercial_events
       WHERE event_type='revenue_recognized'),
    'realized_margin_cents',
      (SELECT COALESCE(sum(margin_cents),0)
       FROM public.commercial_events
       WHERE event_type='revenue_recognized'),
    'actual_revenue',
      EXISTS (
        SELECT 1 FROM public.commercial_events
        WHERE event_type='revenue_recognized'
      ),
    'execution_authority','none'
  )
  INTO payload;

  RETURN payload;
END;
$funnel$;

REVOKE ALL ON FUNCTION public.get_founder_commercial_funnel()
  FROM PUBLIC, empire_intelligence_materializer_login, empiredb_app;
GRANT EXECUTE ON FUNCTION public.get_founder_commercial_funnel()
  TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_founder_commercial_funnel()
IS 'Read-only canonical Founder commercial funnel projection. No execution or accounting authority.';

COMMIT;
