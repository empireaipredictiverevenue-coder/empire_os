-- Append-only public competitor ecosystem evidence.
--
-- Adds a separate Intelligence Fabric source and a tightly-scoped INSERT
-- policy for first-party case-study/testimonial/partner observations.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.intelligence_sources') IS NULL
     OR to_regclass('public.intelligence_signals') IS NULL THEN
    RAISE EXCEPTION 'competitor ecosystem materializer dependency missing';
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
  'empire.competitor_ecosystem.public.v1',
  'other',
  'Empire public competitor ecosystem evidence',
  0.8000,
  true,
  '{
    "owner":"empire_competitive_intelligence",
    "evidence_scope":"public_first_party_company_ecosystem",
    "customer_relationship_semantics":"not_inferred",
    "partner_relationship_semantics":"not_inferred",
    "buyer_intent_semantics":"not_inferred",
    "commercial_intent_semantics":"not_inferred",
    "execution_authority":"none"
  }'::jsonb
)
ON CONFLICT (source_key) DO NOTHING;

GRANT SELECT ON public.intelligence_sources
TO empire_intelligence_materializer;

DROP POLICY IF EXISTS intelligence_materializer_insert_competitor_ecosystem_signal
ON public.intelligence_signals;

CREATE POLICY intelligence_materializer_insert_competitor_ecosystem_signal
ON public.intelligence_signals
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  signal_type='competitor_ecosystem_evidence'
  AND signal_domain='competitive_intelligence'
  AND source_id=(
    SELECT id
    FROM public.intelligence_sources
    WHERE source_key='empire.competitor_ecosystem.public.v1'
  )
  AND COALESCE(payload->>'research_candidate','false')='true'
  AND COALESCE(payload->>'customer_relationship_inferred','false')='false'
  AND COALESCE(payload->>'partner_relationship_inferred','false')='false'
  AND COALESCE(payload->>'buyer_intent','false')='false'
  AND COALESCE(payload->>'commercial_intent','false')='false'
  AND COALESCE(payload->>'prospect_created','false')='false'
  AND COALESCE(payload->>'outreach_enabled','false')='false'
);

COMMENT ON POLICY intelligence_materializer_insert_competitor_ecosystem_signal
ON public.intelligence_signals IS
'Append-only first-party competitor ecosystem observations; no inferred customer/partner status, buyer/commercial intent, prospect creation, or outbound authority.';

COMMIT;
