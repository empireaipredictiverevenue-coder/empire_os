-- Synthetic, throw-away PostgreSQL 18 fixture extension only.
-- Assumes original 056 fixture and migration already loaded.
BEGIN;
SET ROLE empiredb_migrator;

ALTER POLICY fixture_buyers_scope ON public.buyers
  RENAME TO buyers_tenant_reader_select;
ALTER POLICY fixture_orders_scope ON public.fulfilment_orders
  RENAME TO fulfilment_orders_tenant_reader_select;
ALTER POLICY fixture_events_scope ON public.commercial_events
  RENAME TO commercial_events_tenant_reader_select;

ALTER TABLE public.fulfilment_orders
  ADD COLUMN product_id uuid,
  ADD COLUMN opportunity_id uuid,
  ADD COLUMN commercial_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN created_at timestamptz NOT NULL DEFAULT now() - interval '2 days',
  ADD COLUMN delivered_at timestamptz,
  ADD COLUMN confirmed_at timestamptz;

ALTER TABLE public.commercial_outcomes
  ADD COLUMN conversion_outcome text NOT NULL DEFAULT 'lost',
  ADD COLUMN recorded_at timestamptz NOT NULL DEFAULT now() - interval '1 day',
  ADD COLUMN evidence jsonb NOT NULL DEFAULT
    '{"verified":true,"synthetic":false,"forecast_derived":false}'::jsonb;

ALTER TABLE public.commercial_events
  ADD COLUMN fulfilment_order_id uuid,
  ADD COLUMN product_id uuid,
  ADD COLUMN opportunity_id uuid,
  ADD COLUMN event_type text,
  ADD COLUMN payload jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE public.fulfilment_orders SET
  product_id='a1111111-1111-4111-8111-111111111111'::uuid,
  commercial_payload=jsonb_build_object('causal_lineage',jsonb_build_object(
    'tenant_id',CASE WHEN buyer_id='30000000-0000-4000-8000-000000000003'::uuid
                    THEN '10000000-0000-4000-8000-000000000001'
                    ELSE '20000000-0000-4000-8000-000000000002' END));

UPDATE public.commercial_outcomes
  SET conversion_outcome='won'
  WHERE fulfilment_order_id='60000000-0000-4000-8000-000000000006'::uuid;
UPDATE public.fulfilment_orders SET delivered_at=now()-interval '1 day 12 hours'
  WHERE id='60000000-0000-4000-8000-000000000006'::uuid;

INSERT INTO public.commercial_events
  (id,buyer_id,fulfilment_order_id,product_id,opportunity_id,event_type,payload)
VALUES
  ('dd000000-0000-4000-8000-000000000001'::uuid,
   '40000000-0000-4000-8000-000000000004'::uuid,
   '60000000-0000-4000-8000-000000000006'::uuid,
   'a1111111-1111-4111-8111-111111111111'::uuid,
   NULL,'revenue_recognized','{"actual_revenue":true}'::jsonb);

RESET ROLE;
COMMIT;
