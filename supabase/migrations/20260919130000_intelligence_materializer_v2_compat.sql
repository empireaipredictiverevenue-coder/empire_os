-- Reconcile Phase 3F Intelligence Materializer with Lead Scoring v2.
-- Staged only. Does not activate the runtime login or production writer.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.prospect_qualifications') IS NULL
     OR to_regclass('public.intelligence_scores') IS NULL
     OR to_regclass('public.intelligence_sources') IS NULL THEN
    RAISE EXCEPTION 'Intelligence materializer v2 dependency missing';
  END IF;
END $$;

INSERT INTO public.intelligence_sources(
  source_key,
  source_type,
  display_name,
  authority_score,
  metadata
)
VALUES (
  'empire.qualification.lead_scoring.v2',
  'first_party',
  'Empire evidence-aware lead qualification v2',
  1.0000,
  '{"authority_semantics":"authoritative_internal_score_record; evidence confidence is separate from commercial quality"}'::jsonb
)
ON CONFLICT (source_key) DO NOTHING;

DROP POLICY IF EXISTS intelligence_materializer_insert_scores
ON public.intelligence_scores;

CREATE POLICY intelligence_materializer_insert_scores
ON public.intelligence_scores
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  entity_type='company'
  AND score_type='lead_qualification'
  AND model_key IN (
    'empire_os.lead_scoring:v1',
    'empire_os.lead_scoring:v2'
  )
);

COMMENT ON POLICY intelligence_materializer_insert_scores
ON public.intelligence_scores IS
'Append-only v1/v2 qualification projection; v2 confidence must come from persisted evidence_confidence.';

COMMIT;
