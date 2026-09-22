-- Append-only public review-platform presence evidence.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.intelligence_sources') IS NULL
     OR to_regclass('public.intelligence_signals') IS NULL THEN
    RAISE EXCEPTION 'public review materializer dependency missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_intelligence_materializer'
  ) THEN
    RAISE EXCEPTION 'empire_intelligence_materializer role missing';
  END IF;
END $$;

INSERT INTO public.intelligence_sources(
  source_key,
  source_type,
  display_name,
  authority_score,
  enabled,
  metadata
)
VALUES (
  'empire.competitor_public_reviews.public.v1',
  'other',
  'Empire public review-platform presence evidence',
  0.8000,
  true,
  '{
    "owner":"empire_competitive_intelligence",
    "evidence_scope":"public_review_platform_presence",
    "review_sentiment_semantics":"not_inferred",
    "buyer_intent_semantics":"not_inferred",
    "commercial_intent_semantics":"not_inferred",
    "execution_authority":"none"
  }'::jsonb
)
ON CONFLICT (source_key) DO NOTHING;

GRANT SELECT ON public.intelligence_sources
TO empire_intelligence_materializer;

DROP POLICY IF EXISTS intelligence_materializer_insert_public_review_signal
ON public.intelligence_signals;

CREATE POLICY intelligence_materializer_insert_public_review_signal
ON public.intelligence_signals
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  signal_type='competitor_public_review_presence'
  AND signal_domain='competitive_intelligence'
  AND source_id=(
    SELECT id
    FROM public.intelligence_sources
    WHERE source_key='empire.competitor_public_reviews.public.v1'
  )
  AND COALESCE(payload->>'research_candidate','false')='true'
  AND COALESCE(payload->>'review_sentiment_inferred','false')='false'
  AND COALESCE(payload->>'buyer_intent','false')='false'
  AND COALESCE(payload->>'commercial_intent','false')='false'
  AND COALESCE(payload->>'prospect_created','false')='false'
  AND COALESCE(payload->>'outreach_enabled','false')='false'
);

COMMENT ON POLICY intelligence_materializer_insert_public_review_signal
ON public.intelligence_signals IS
'Append-only public review-platform presence; no review sentiment, buyer/commercial intent, prospect creation, or outbound authority inferred.';

COMMIT;
