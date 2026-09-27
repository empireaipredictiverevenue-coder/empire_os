-- Phase 4 Buyer Acquisition Scout candidate holding area.
-- Applied to canonical Supabase as migration 20260923082430.
-- Research evidence is not buyer verification, capacity, pricing,
-- outreach authority, payment or revenue.

BEGIN;

CREATE TABLE IF NOT EXISTS public.buyer_scout_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  domain text NOT NULL UNIQUE,
  business_name text,
  website text NOT NULL,
  description text,
  buyer_type text NOT NULL DEFAULT 'unknown',
  direct_buyer_score integer NOT NULL DEFAULT 0
    CHECK (direct_buyer_score BETWEEN 0 AND 100),
  explicit_direct_buyer_evidence boolean NOT NULL DEFAULT false,
  target_buyer_pools jsonb NOT NULL DEFAULT '[]'::jsonb,
  target_product_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
  target_corridor_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
  query_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  site_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  reconciliation_state text NOT NULL DEFAULT 'NEW_EXTERNAL_BUYER_CANDIDATE'
    CHECK (
      reconciliation_state IN (
        'NEW_EXTERNAL_BUYER_CANDIDATE',
        'EXISTING_CANONICAL_BUYER',
        'EXISTING_CANONICAL_PROSPECT',
        'BLOCKED_NO_DOMAIN',
        'REVIEW_READY',
        'REJECTED',
        'PROMOTED'
      )
    ),
  canonical_buyer_id uuid REFERENCES public.buyers(id) ON DELETE SET NULL,
  canonical_prospect_id uuid REFERENCES public.prospects(id) ON DELETE SET NULL,
  review_state text NOT NULL DEFAULT 'discovered'
    CHECK (
      review_state IN (
        'discovered',
        'reconciled',
        'review_ready',
        'rejected',
        'promoted'
      )
    ),
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  reviewed_at timestamptz,
  reviewed_by text,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_state_idx
  ON public.buyer_scout_candidates (
    reconciliation_state,
    review_state,
    direct_buyer_score DESC,
    last_seen_at DESC
  );

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_buyer_idx
  ON public.buyer_scout_candidates(canonical_buyer_id)
  WHERE canonical_buyer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS buyer_scout_candidates_prospect_idx
  ON public.buyer_scout_candidates(canonical_prospect_id)
  WHERE canonical_prospect_id IS NOT NULL;

ALTER TABLE public.buyer_scout_candidates ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.buyer_scout_candidates
FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT, UPDATE ON public.buyer_scout_candidates
TO service_role;

CREATE OR REPLACE FUNCTION public.propose_buyer_scout_candidate(
  p_domain text,
  p_business_name text,
  p_website text,
  p_description text,
  p_buyer_type text,
  p_direct_buyer_score integer,
  p_explicit_direct_buyer_evidence boolean,
  p_target_buyer_pools jsonb,
  p_target_product_codes jsonb,
  p_target_corridor_keys jsonb,
  p_query_evidence jsonb,
  p_site_evidence jsonb,
  p_provenance jsonb,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  candidate public.buyer_scout_candidates%ROWTYPE;
  normalized_domain text := lower(trim(COALESCE(p_domain,'')));
BEGIN
  IF normalized_domain=''
     OR trim(COALESCE(p_website,''))=''
     OR trim(COALESCE(p_actor,''))='' THEN
    RAISE EXCEPTION 'domain, website and actor required';
  END IF;

  IF p_direct_buyer_score < 0 OR p_direct_buyer_score > 100 THEN
    RAISE EXCEPTION 'direct buyer score out of bounds';
  END IF;

  IF jsonb_typeof(COALESCE(p_target_buyer_pools,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_target_product_codes,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_target_corridor_keys,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_query_evidence,'[]'::jsonb))<>'array'
     OR jsonb_typeof(COALESCE(p_site_evidence,'{}'::jsonb))<>'object'
     OR jsonb_typeof(COALESCE(p_provenance,'{}'::jsonb))<>'object' THEN
    RAISE EXCEPTION 'invalid buyer scout evidence shape';
  END IF;

  INSERT INTO public.buyer_scout_candidates(
    domain,
    business_name,
    website,
    description,
    buyer_type,
    direct_buyer_score,
    explicit_direct_buyer_evidence,
    target_buyer_pools,
    target_product_codes,
    target_corridor_keys,
    query_evidence,
    site_evidence,
    provenance
  ) VALUES (
    normalized_domain,
    NULLIF(trim(COALESCE(p_business_name,'')),''),
    trim(p_website),
    NULLIF(trim(COALESCE(p_description,'')),''),
    COALESCE(NULLIF(trim(COALESCE(p_buyer_type,'')),''),'unknown'),
    p_direct_buyer_score,
    COALESCE(p_explicit_direct_buyer_evidence,false),
    COALESCE(p_target_buyer_pools,'[]'::jsonb),
    COALESCE(p_target_product_codes,'[]'::jsonb),
    COALESCE(p_target_corridor_keys,'[]'::jsonb),
    COALESCE(p_query_evidence,'[]'::jsonb),
    COALESCE(p_site_evidence,'{}'::jsonb),
    COALESCE(p_provenance,'{}'::jsonb)
  )
  ON CONFLICT (domain) DO UPDATE
  SET business_name=COALESCE(
        excluded.business_name,
        public.buyer_scout_candidates.business_name
      ),
      website=excluded.website,
      description=COALESCE(
        excluded.description,
        public.buyer_scout_candidates.description
      ),
      buyer_type=excluded.buyer_type,
      direct_buyer_score=GREATEST(
        public.buyer_scout_candidates.direct_buyer_score,
        excluded.direct_buyer_score
      ),
      explicit_direct_buyer_evidence=(
        public.buyer_scout_candidates.explicit_direct_buyer_evidence
        OR excluded.explicit_direct_buyer_evidence
      ),
      target_buyer_pools=excluded.target_buyer_pools,
      target_product_codes=excluded.target_product_codes,
      target_corridor_keys=excluded.target_corridor_keys,
      query_evidence=excluded.query_evidence,
      site_evidence=excluded.site_evidence,
      provenance=(
        public.buyer_scout_candidates.provenance
        || excluded.provenance
      ),
      last_seen_at=clock_timestamp(),
      updated_at=clock_timestamp()
  RETURNING * INTO candidate;

  RETURN jsonb_build_object(
    'decision','candidate_recorded',
    'candidate_id',candidate.id,
    'domain',candidate.domain,
    'review_state',candidate.review_state,
    'reconciliation_state',candidate.reconciliation_state,
    'canonical_buyer_id',candidate.canonical_buyer_id,
    'canonical_prospect_id',candidate.canonical_prospect_id,
    'outreach_authorized',false,
    'commercial_terms_verified',false,
    'actual_revenue',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.propose_buyer_scout_candidate(
  text,text,text,text,text,integer,boolean,
  jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,text
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.propose_buyer_scout_candidate(
  text,text,text,text,text,integer,boolean,
  jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,text
) TO service_role;

COMMENT ON TABLE public.buyer_scout_candidates IS
  'Phase 4 research holding area. Discovery is not buyer verification, '
  'commercial terms, capacity, outreach authority, payment or revenue.';

COMMIT;
