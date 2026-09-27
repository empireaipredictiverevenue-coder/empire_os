-- Empire Data Cloud — canonical core schema parity
-- Migration: empiredb/008_core_schema_parity
-- Source of truth: live canonical production schema, 2026-09-27.
-- Shadow-only schema parity. No data copy and no production cutover.

ALTER TABLE public.commercial_products
    ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS catalog_state TEXT NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN IF NOT EXISTS provenance JSONB NOT NULL DEFAULT '{}'::jsonb;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='commercial_products_catalog_state_check'
          AND conrelid='public.commercial_products'::regclass
    ) THEN
        ALTER TABLE public.commercial_products
            ADD CONSTRAINT commercial_products_catalog_state_check
            CHECK (catalog_state = ANY (
                ARRAY['UNKNOWN','DRAFT','VERIFIED','RETIRED']::text[]
            ));
    END IF;
END;
$$;

ALTER TABLE public.gtm_opportunities
    ADD COLUMN IF NOT EXISTS niche_family TEXT;

CREATE INDEX IF NOT EXISTS idx_gtm_opportunities_niche_family
    ON public.gtm_opportunities (niche_family);
