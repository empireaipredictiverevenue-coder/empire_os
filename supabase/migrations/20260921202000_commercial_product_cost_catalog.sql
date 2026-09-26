-- Canonical versioned commercial product + cost catalog.
-- Extends commercial_products without inventing prices or treating zero as
-- verified/free. Binding commercial terms remain fail-closed.

BEGIN;

ALTER TABLE public.commercial_products
  ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'USD',
  ADD COLUMN IF NOT EXISTS catalog_state text NOT NULL DEFAULT 'UNKNOWN',
  ADD COLUMN IF NOT EXISTS provenance jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Legacy scalar price columns remain compatibility-only fields. Their numeric
-- values, including zero, are never sufficient evidence for catalog
-- verification or binding commercial terms. Canonical readiness uses only the
-- versioned evidence-backed basis objects below.

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='commercial_products_catalog_state_check'
  ) THEN
    ALTER TABLE public.commercial_products
      ADD CONSTRAINT commercial_products_catalog_state_check
      CHECK (catalog_state IN ('UNKNOWN','DRAFT','VERIFIED','RETIRED'));
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.commercial_product_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid NOT NULL REFERENCES public.commercial_products(id) ON DELETE CASCADE,
  version integer NOT NULL CHECK (version > 0),
  version_state text NOT NULL DEFAULT 'UNKNOWN'
    CHECK (version_state IN ('UNKNOWN','DRAFT','PENDING','VERIFIED','RETIRED','REJECTED')),
  billing_model text NOT NULL,
  currency text NOT NULL DEFAULT 'USD',
  price_basis jsonb NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
  acquisition_cost_basis jsonb NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
  fulfilment_cost_basis jsonb NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
  margin_policy jsonb NOT NULL DEFAULT '{"state":"UNKNOWN"}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  effective_from timestamptz,
  effective_until timestamptz,
  verified_at timestamptz,
  verified_by text,
  rejected_at timestamptz,
  rejected_by text,
  rejection_reason text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(product_id,version),
  CHECK (
    effective_until IS NULL
    OR effective_from IS NULL
    OR effective_until > effective_from
  )
);

CREATE INDEX IF NOT EXISTS commercial_product_versions_product_idx
  ON public.commercial_product_versions(product_id,version DESC);

CREATE INDEX IF NOT EXISTS commercial_product_versions_state_idx
  ON public.commercial_product_versions(version_state,effective_from,effective_until);

CREATE TABLE IF NOT EXISTS public.commercial_product_catalog_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id uuid NOT NULL REFERENCES public.commercial_products(id) ON DELETE CASCADE,
  product_version_id uuid REFERENCES public.commercial_product_versions(id) ON DELETE SET NULL,
  event_type text NOT NULL,
  actor text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS commercial_product_catalog_events_product_idx
  ON public.commercial_product_catalog_events(product_id,occurred_at DESC);

CREATE OR REPLACE FUNCTION public.get_commercial_product_catalog(
  p_product_code text DEFAULT NULL,
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  WITH ranked AS (
    SELECT
      v.*,
      row_number() OVER (
        PARTITION BY v.product_id
        ORDER BY
          CASE
            WHEN v.version_state='VERIFIED'
             AND (v.effective_from IS NULL OR v.effective_from <= now())
             AND (v.effective_until IS NULL OR v.effective_until > now())
            THEN 0
            ELSE 1
          END,
          v.version DESC
      ) AS readiness_rank
    FROM public.commercial_product_versions v
  ),
  latest AS (
    SELECT *
    FROM ranked
    WHERE readiness_rank=1
  )
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'product_id',p.id,
        'product_code',p.product_code,
        'product_name',p.product_name,
        'product_family',p.product_family,
        'active',p.active,
        'catalog_state',p.catalog_state,
        'currency',p.currency,
        'product_provenance',p.provenance,
        'version_id',v.id,
        'version',v.version,
        'version_state',COALESCE(v.version_state,'UNKNOWN'),
        'billing_model',COALESCE(v.billing_model,p.billing_model),
        'price_basis',COALESCE(v.price_basis,'{"state":"UNKNOWN"}'::jsonb),
        'acquisition_cost_basis',COALESCE(v.acquisition_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
        'fulfilment_cost_basis',COALESCE(v.fulfilment_cost_basis,'{"state":"UNKNOWN"}'::jsonb),
        'margin_policy',COALESCE(v.margin_policy,'{"state":"UNKNOWN"}'::jsonb),
        'provenance',COALESCE(v.provenance,'{}'::jsonb),
        'evidence_refs',COALESCE(v.evidence_refs,'[]'::jsonb),
        'effective_from',v.effective_from,
        'effective_until',v.effective_until,
        'verified_at',v.verified_at,
        'verified_by',v.verified_by,
        'binding_terms_ready',(
          p.active IS TRUE
          AND p.catalog_state='VERIFIED'
          AND v.version_state='VERIFIED'
          AND COALESCE(v.price_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.acquisition_cost_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.fulfilment_cost_basis->>'state','UNKNOWN')='VERIFIED'
          AND COALESCE(v.margin_policy->>'state','UNKNOWN')='VERIFIED'
          AND (v.effective_from IS NULL OR v.effective_from <= now())
          AND (v.effective_until IS NULL OR v.effective_until > now())
        ),
        'actual_revenue',false
      )
      ORDER BY p.product_code
    ),
    '[]'::jsonb
  )
  FROM (
    SELECT *
    FROM public.commercial_products
    WHERE p_product_code IS NULL OR product_code=p_product_code
    ORDER BY product_code
    LIMIT LEAST(GREATEST(COALESCE(p_limit,100),1),500)
  ) p
  LEFT JOIN latest v ON v.product_id=p.id;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_product_readiness(
  p_product_code text
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  WITH rows AS (
    SELECT public.get_commercial_product_catalog(p_product_code,1) AS payload
  ),
  item AS (
    SELECT payload->0 AS x FROM rows
  )
  SELECT CASE
    WHEN x IS NULL THEN jsonb_build_object(
      'product_code',p_product_code,
      'exists',false,
      'binding_terms_ready',false,
      'blockers',jsonb_build_array('product_not_found'),
      'actual_revenue',false
    )
    ELSE jsonb_build_object(
      'product_code',x->>'product_code',
      'exists',true,
      'binding_terms_ready',COALESCE((x->>'binding_terms_ready')::boolean,false),
      'blockers',to_jsonb(ARRAY_REMOVE(ARRAY[
        CASE WHEN COALESCE((x->>'active')::boolean,false) IS NOT TRUE THEN 'product_inactive' END,
        CASE WHEN COALESCE(x->>'catalog_state','UNKNOWN')<>'VERIFIED' THEN 'catalog_unverified' END,
        CASE WHEN COALESCE(x->>'version_state','UNKNOWN')<>'VERIFIED' THEN 'version_unverified' END,
        CASE WHEN COALESCE(x->'price_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'price_basis_unverified' END,
        CASE WHEN COALESCE(x->'acquisition_cost_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'acquisition_cost_basis_unverified' END,
        CASE WHEN COALESCE(x->'fulfilment_cost_basis'->>'state','UNKNOWN')<>'VERIFIED' THEN 'fulfilment_cost_basis_unverified' END,
        CASE WHEN COALESCE(x->'margin_policy'->>'state','UNKNOWN')<>'VERIFIED' THEN 'margin_policy_unverified' END,
        CASE
          WHEN x->>'effective_from' IS NOT NULL
           AND (x->>'effective_from')::timestamptz > now()
          THEN 'version_not_yet_effective'
        END,
        CASE
          WHEN x->>'effective_until' IS NOT NULL
           AND (x->>'effective_until')::timestamptz <= now()
          THEN 'version_expired'
        END
      ],NULL)),
      'catalog',x,
      'actual_revenue',false
    )
  END
  FROM item;
$$;

REVOKE ALL ON FUNCTION public.get_commercial_product_catalog(text,integer)
FROM PUBLIC,anon,authenticated;

REVOKE ALL ON FUNCTION public.get_commercial_product_readiness(text)
FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_catalog(text,integer)
TO service_role;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_readiness(text)
TO service_role;

COMMIT;
