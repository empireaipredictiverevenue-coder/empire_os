-- Phase 8 Revenue CRM canonical read model.
-- Staged only: no follow-up, commercial mutation or production apply.
BEGIN;

CREATE OR REPLACE VIEW public.revenue_crm_prospects
WITH (security_invoker=true)
AS
SELECT
  p.id AS prospect_id,
  p.business_name,
  p.niche,
  p.metro,
  p.status AS prospect_status,
  conversation.id AS conversation_id,
  conversation.channel AS conversation_channel,
  conversation.state AS conversation_state,
  conversation.updated_at AS conversation_updated_at,
  closer.id AS closer_case_id,
  closer.state AS closer_state,
  closer.updated_at AS closer_updated_at,
  fulfilment.id AS fulfilment_order_id,
  fulfilment.state AS fulfilment_state,
  fulfilment.price_cents,
  NULL::numeric AS deal_probability
FROM public.prospects p
LEFT JOIN LATERAL (
  SELECT c.id,c.channel,c.state,c.updated_at
  FROM public.empire_conversations c
  WHERE c.prospect_id=p.id
  ORDER BY c.updated_at DESC,c.id DESC
  LIMIT 1
) conversation ON true
LEFT JOIN LATERAL (
  SELECT c.id,c.state,c.updated_at
  FROM public.closer_cases c
  WHERE c.prospect_id=p.id
  ORDER BY c.updated_at DESC,c.id DESC
  LIMIT 1
) closer ON true
LEFT JOIN LATERAL (
  SELECT f.id,f.state,f.price_cents,f.updated_at
  FROM public.fulfilment_orders f
  WHERE f.prospect_id=p.id
  ORDER BY f.updated_at DESC,f.id DESC
  LIMIT 1
) fulfilment ON true;

COMMENT ON VIEW public.revenue_crm_prospects IS
'Phase 8 read-only canonical prospect CRM projection. Deal probability remains NULL until calibrated evidence exists.';
CREATE OR REPLACE VIEW public.revenue_crm_buyers
WITH (security_invoker=true)
AS
SELECT
  b.id AS buyer_id,
  b.buyer_name,
  b.niche,
  b.metro,
  b.status AS buyer_status,
  b.is_active,
  b.commercial_activation_state,
  b.daily_cap,
  b.calls_today,
  greatest(
    coalesce(b.daily_cap,0)-coalesce(b.calls_today,0),
    0
  ) AS available_capacity,
  b.per_lead_rate,
  b.capacity_verified_at,
  b.delivery_verified_at,
  b.commercial_terms_verified_at
FROM public.buyers b;

COMMENT ON VIEW public.revenue_crm_buyers IS
'Phase 8 read-only canonical buyer CRM projection using the same commercial activation and capacity fields as allocation.';

REVOKE ALL ON public.revenue_crm_prospects,
  public.revenue_crm_buyers
FROM PUBLIC,anon,authenticated;

GRANT SELECT ON public.revenue_crm_prospects,
  public.revenue_crm_buyers
TO service_role;

COMMIT;
