-- Extend the existing Intelligence Fabric materializer for bounded,
-- append-only competitor-audience evidence.
--
-- Staged migration. This does not provision the runtime login password,
-- create prospects, enable outbound, or grant mutation authority over
-- canonical business entities.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.business_entities') IS NULL
     OR to_regclass('public.intelligence_sources') IS NULL
     OR to_regclass('public.intelligence_signals') IS NULL THEN
    RAISE EXCEPTION 'competitor audience materializer dependency missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_roles
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
  'empire.competitor_audience.public.v1',
  'other',
  'Empire public competitor audience evidence',
  0.7500,
  true,
  '{
    "owner":"empire_competitive_intelligence",
    "evidence_scope":"public_company_level",
    "buyer_intent_semantics":"not_inferred",
    "commercial_intent_semantics":"not_inferred",
    "execution_authority":"none"
  }'::jsonb
)
ON CONFLICT (source_key) DO NOTHING;

GRANT SELECT ON
  public.business_entities,
  public.intelligence_signals
TO empire_intelligence_materializer;

GRANT INSERT ON
  public.intelligence_signals
TO empire_intelligence_materializer;

REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON
  public.business_entities,
  public.intelligence_signals
FROM empire_intelligence_materializer;

DROP POLICY IF EXISTS intelligence_materializer_select_business_entities
ON public.business_entities;

CREATE POLICY intelligence_materializer_select_business_entities
ON public.business_entities
FOR SELECT
TO empire_intelligence_materializer
USING (true);

DROP POLICY IF EXISTS intelligence_materializer_select_signals
ON public.intelligence_signals;

CREATE POLICY intelligence_materializer_select_signals
ON public.intelligence_signals
FOR SELECT
TO empire_intelligence_materializer
USING (true);

DROP POLICY IF EXISTS intelligence_materializer_insert_competitor_audience_signal
ON public.intelligence_signals;

CREATE POLICY intelligence_materializer_insert_competitor_audience_signal
ON public.intelligence_signals
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  signal_type='competitor_audience_evidence'
  AND signal_domain='competitive_intelligence'
  AND source_id=(
    SELECT id
    FROM public.intelligence_sources
    WHERE source_key='empire.competitor_audience.public.v1'
  )
  AND COALESCE(payload->>'research_candidate','false')='true'
  AND COALESCE(payload->>'buyer_intent','false')='false'
  AND COALESCE(payload->>'commercial_intent','false')='false'
  AND COALESCE(payload->>'prospect_created','false')='false'
  AND COALESCE(payload->>'outreach_enabled','false')='false'
);

COMMENT ON POLICY intelligence_materializer_insert_competitor_audience_signal
ON public.intelligence_signals IS
'Append-only public competitor-audience evidence. Research candidate only; no buyer/commercial intent, prospect creation, or outbound authority.';

COMMIT;
