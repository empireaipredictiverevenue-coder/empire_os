-- Lead Scoring v2 evidence semantics.
-- Staged only. v1 rows/consumers remain unchanged until separately approved.
BEGIN;

DO $$
BEGIN
  IF to_regclass('public.prospect_qualifications') IS NULL THEN
    RAISE EXCEPTION
      'Lead Scoring v2 dependency missing: public.prospect_qualifications';
  END IF;
END $$;

ALTER TABLE public.prospect_qualifications
  ADD COLUMN IF NOT EXISTS evidence_confidence numeric(5,4),
  ADD COLUMN IF NOT EXISTS observed_dimensions jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS unknown_dimensions jsonb NOT NULL DEFAULT '[]'::jsonb;

-- v1 still writes numeric values. v2 may persist NULL when a dimension is
-- genuinely unknown rather than coercing absence to zero.
ALTER TABLE public.prospect_qualifications
  ALTER COLUMN score DROP NOT NULL,
  ALTER COLUMN business_presence_score DROP NOT NULL,
  ALTER COLUMN market_fit_score DROP NOT NULL,
  ALTER COLUMN engagement_potential_score DROP NOT NULL,
  ALTER COLUMN enrichment_quality_score DROP NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid='public.prospect_qualifications'::regclass
      AND conname='prospect_qualifications_evidence_confidence_check'
  ) THEN
    ALTER TABLE public.prospect_qualifications
      ADD CONSTRAINT prospect_qualifications_evidence_confidence_check
      CHECK (
        evidence_confidence IS NULL
        OR evidence_confidence BETWEEN 0 AND 1
      );
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid='public.prospect_qualifications'::regclass
      AND conname='prospect_qualifications_observed_dimensions_array_check'
  ) THEN
    ALTER TABLE public.prospect_qualifications
      ADD CONSTRAINT prospect_qualifications_observed_dimensions_array_check
      CHECK (jsonb_typeof(observed_dimensions)='array');
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid='public.prospect_qualifications'::regclass
      AND conname='prospect_qualifications_unknown_dimensions_array_check'
  ) THEN
    ALTER TABLE public.prospect_qualifications
      ADD CONSTRAINT prospect_qualifications_unknown_dimensions_array_check
      CHECK (jsonb_typeof(unknown_dimensions)='array');
  END IF;
END $$;

COMMENT ON COLUMN public.prospect_qualifications.evidence_confidence IS
'0..1 evidence sufficiency for the score; separate from commercial quality.';
COMMENT ON COLUMN public.prospect_qualifications.observed_dimensions IS
'Scoring dimensions backed by observed evidence for this versioned run.';
COMMENT ON COLUMN public.prospect_qualifications.unknown_dimensions IS
'Scoring dimensions intentionally left unknown rather than coerced to zero.';

COMMIT;
