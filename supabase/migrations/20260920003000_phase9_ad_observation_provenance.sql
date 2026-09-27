-- Phase 9 advertising observation provenance hardening.
-- Staged only: no campaign creation, budget mutation, pause or retarget execution.
BEGIN;

CREATE OR REPLACE FUNCTION public.record_ad_performance_observation(
  p_campaign_id uuid,
  p_provider_observation_id text,
  p_observed_at timestamptz,
  p_spend_cents bigint,
  p_attributed_revenue_cents bigint,
  p_attributed_gross_profit_cents bigint,
  p_impressions bigint,
  p_clicks bigint,
  p_conversions bigint,
  p_source text,
  p_creative_id uuid,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  c public.ad_campaigns%ROWTYPE;
  cr public.ad_creatives%ROWTYPE;
  o public.ad_performance_observations%ROWTYPE;
  incoming_hash text;
  existing_hash text;
BEGIN
  SELECT * INTO c
  FROM public.ad_campaigns
  WHERE id=p_campaign_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'canonical ad campaign required';
  END IF;

  IF p_creative_id IS NOT NULL THEN
    SELECT * INTO cr
    FROM public.ad_creatives
    WHERE id=p_creative_id;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'canonical ad creative required';
    END IF;
    IF cr.campaign_id IS DISTINCT FROM p_campaign_id THEN
      RAISE EXCEPTION 'creative does not belong to campaign';
    END IF;
  END IF;

  IF trim(COALESCE(p_provider_observation_id,''))='' THEN
    RAISE EXCEPTION 'provider observation id required';
  END IF;
  IF p_observed_at IS NULL THEN
    RAISE EXCEPTION 'observed_at required';
  END IF;
  IF p_spend_cents IS NULL OR p_spend_cents < 0 THEN
    RAISE EXCEPTION 'nonnegative spend required';
  END IF;
  IF p_attributed_revenue_cents IS NOT NULL
     AND p_attributed_revenue_cents < 0 THEN
    RAISE EXCEPTION 'attributed revenue must be nonnegative';
  END IF;
  IF p_attributed_gross_profit_cents IS NOT NULL
     AND p_attributed_gross_profit_cents < 0 THEN
    RAISE EXCEPTION 'attributed gross profit must be nonnegative';
  END IF;
  IF trim(COALESCE(p_source,''))='' THEN
    RAISE EXCEPTION 'source required';
  END IF;

  incoming_hash := trim(
    COALESCE(p_evidence->>'payload_sha256','')
  );
  IF incoming_hash='' THEN
    RAISE EXCEPTION 'payload_sha256 evidence required';
  END IF;

  SELECT * INTO o
  FROM public.ad_performance_observations
  WHERE campaign_id=p_campaign_id
    AND provider_observation_id=trim(p_provider_observation_id);

  IF FOUND THEN
    existing_hash := trim(
      COALESCE(o.evidence->>'payload_sha256','')
    );
    IF existing_hash='' OR existing_hash <> incoming_hash THEN
      RETURN jsonb_build_object(
        'status','conflict',
        'reason','provider_observation_payload_mismatch',
        'observation_id',o.id,
        'campaign_id',o.campaign_id
      );
    END IF;

    IF o.creative_id IS DISTINCT FROM p_creative_id THEN
      RETURN jsonb_build_object(
        'status','conflict',
        'reason','provider_observation_creative_mismatch',
        'observation_id',o.id,
        'campaign_id',o.campaign_id
      );
    END IF;

    RETURN jsonb_build_object(
      'status','existing',
      'observation_id',o.id,
      'campaign_id',o.campaign_id
    );
  END IF;

  INSERT INTO public.ad_performance_observations(
    campaign_id,
    creative_id,
    provider_observation_id,
    observed_at,
    spend_cents,
    attributed_revenue_cents,
    attributed_gross_profit_cents,
    impressions,
    clicks,
    conversions,
    source,
    evidence
  )
  VALUES(
    p_campaign_id,
    p_creative_id,
    trim(p_provider_observation_id),
    p_observed_at,
    p_spend_cents,
    p_attributed_revenue_cents,
    p_attributed_gross_profit_cents,
    p_impressions,
    p_clicks,
    p_conversions,
    trim(p_source),
    COALESCE(p_evidence,'{}'::jsonb)
  )
  RETURNING * INTO o;

  RETURN jsonb_build_object(
    'status','recorded',
    'observation_id',o.id,
    'campaign_id',o.campaign_id
  );
END;
$$;

REVOKE ALL ON FUNCTION public.record_ad_performance_observation(
  uuid,text,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,
  text,uuid,jsonb
) FROM PUBLIC,anon,authenticated,service_role;

GRANT EXECUTE ON FUNCTION public.record_ad_performance_observation(
  uuid,text,timestamptz,bigint,bigint,bigint,bigint,bigint,bigint,
  text,uuid,jsonb
) TO empire_ad_observation_ingest;

COMMIT;
