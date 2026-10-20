-- Throw-away PostgreSQL database only. Synthetic tenant, order and settlement IDs.
CREATE ROLE empiredb_migrator NOLOGIN NOINHERIT;
CREATE ROLE empiredb_tenant_reader NOLOGIN NOINHERIT;
CREATE ROLE order_fixture_a LOGIN NOINHERIT PASSWORD 'synthetic-pg18-test-only';
CREATE ROLE order_fixture_b LOGIN NOINHERIT PASSWORD 'synthetic-pg18-test-only';
GRANT empiredb_tenant_reader TO order_fixture_a, order_fixture_b;
GRANT CREATE ON SCHEMA public TO empiredb_migrator;
GRANT USAGE ON SCHEMA public TO empiredb_tenant_reader;
SET ROLE empiredb_migrator;

CREATE TABLE public.empire_tenant_role_bindings (
  role_name name PRIMARY KEY,
  tenant_id uuid NOT NULL,
  active boolean NOT NULL DEFAULT true,
  evidence_ref text
);
REVOKE ALL ON public.empire_tenant_role_bindings FROM PUBLIC;
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,public AS $f$
 SELECT tenant_id FROM public.empire_tenant_role_bindings
 WHERE role_name=session_user AND active LIMIT 1
$f$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empiredb_tenant_reader;

CREATE TABLE public.buyers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL
);
CREATE TABLE public.fulfilment_orders (
  id uuid PRIMARY KEY,
  buyer_id uuid REFERENCES public.buyers(id)
);
CREATE TABLE public.commercial_events (
  id uuid PRIMARY KEY,
  buyer_id uuid
);
CREATE TABLE public.commercial_outcomes (
  id uuid PRIMARY KEY,
  fulfilment_order_id uuid
);
CREATE TABLE public.bsc_payment_requests (
  id uuid PRIMARY KEY,
  fulfilment_order_id uuid,
  buyer_id uuid
);
CREATE TABLE public.bsc_payment_evidence (
  id uuid PRIMARY KEY,
  request_id uuid,
  fulfilment_order_id uuid
);
CREATE TABLE public.bsc_escrow_agreements (
  id uuid PRIMARY KEY,
  request_id uuid
);
CREATE TABLE public.bsc_escrow_evidence (
  id uuid PRIMARY KEY,
  agreement_id uuid
);

ALTER TABLE public.buyers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fulfilment_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commercial_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commercial_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_payment_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_payment_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_escrow_agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bsc_escrow_evidence ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.buyers,public.fulfilment_orders,public.commercial_events
 TO empiredb_tenant_reader;
CREATE POLICY fixture_buyers_scope ON public.buyers FOR SELECT
 TO empiredb_tenant_reader USING (org_id=public.empire_current_tenant_id());
CREATE POLICY fixture_orders_scope ON public.fulfilment_orders FOR SELECT
 TO empiredb_tenant_reader USING (
   EXISTS(SELECT 1 FROM public.buyers b WHERE b.id=buyer_id
          AND b.org_id=public.empire_current_tenant_id())
 );
CREATE POLICY fixture_events_scope ON public.commercial_events FOR SELECT
 TO empiredb_tenant_reader USING (
   EXISTS(SELECT 1 FROM public.buyers b WHERE b.id=buyer_id
          AND b.org_id=public.empire_current_tenant_id())
 );

INSERT INTO public.empire_tenant_role_bindings(role_name,tenant_id,active)
VALUES
('order_fixture_a','10000000-0000-4000-8000-000000000001',true),
('order_fixture_b','20000000-0000-4000-8000-000000000002',true);
INSERT INTO public.buyers VALUES
('30000000-0000-4000-8000-000000000003','10000000-0000-4000-8000-000000000001'),
('40000000-0000-4000-8000-000000000004','20000000-0000-4000-8000-000000000002');
INSERT INTO public.fulfilment_orders VALUES
('50000000-0000-4000-8000-000000000005','30000000-0000-4000-8000-000000000003'),
('60000000-0000-4000-8000-000000000006','40000000-0000-4000-8000-000000000004');
INSERT INTO public.commercial_outcomes VALUES
('70000000-0000-4000-8000-000000000007','50000000-0000-4000-8000-000000000005'),
('80000000-0000-4000-8000-000000000008','60000000-0000-4000-8000-000000000006');
INSERT INTO public.bsc_payment_requests VALUES
('90000000-0000-4000-8000-000000000009','50000000-0000-4000-8000-000000000005','30000000-0000-4000-8000-000000000003'),
('a0000000-0000-4000-8000-00000000000a','60000000-0000-4000-8000-000000000006','40000000-0000-4000-8000-000000000004');
INSERT INTO public.bsc_payment_evidence VALUES
('b0000000-0000-4000-8000-00000000000b','90000000-0000-4000-8000-000000000009','50000000-0000-4000-8000-000000000005'),
('c0000000-0000-4000-8000-00000000000c','a0000000-0000-4000-8000-00000000000a','60000000-0000-4000-8000-000000000006');
INSERT INTO public.bsc_escrow_agreements VALUES
('d0000000-0000-4000-8000-00000000000d','90000000-0000-4000-8000-000000000009'),
('e0000000-0000-4000-8000-00000000000e','a0000000-0000-4000-8000-00000000000a');
INSERT INTO public.bsc_escrow_evidence VALUES
('f0000000-0000-4000-8000-00000000000f','d0000000-0000-4000-8000-00000000000d'),
('11000000-0000-4000-8000-000000000011','e0000000-0000-4000-8000-00000000000e');
RESET ROLE;
