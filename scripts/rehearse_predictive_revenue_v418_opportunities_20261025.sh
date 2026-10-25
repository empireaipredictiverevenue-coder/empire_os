#!/usr/bin/env bash
# V4.15: disposable PostgreSQL18 ONLY. Never mutate live EmpireDB.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${PGHOST:?requires pg_virtualenv}" "${PGPORT:?requires pg_virtualenv}"
[[ "$PGHOST" == localhost && "$PGPORT" =~ ^[0-9]+$ ]] || exit 9
(( PGPORT >= 5433 )) || exit 9
pg_dir="$(psql -XAtq -v ON_ERROR_STOP=1 -d postgres -c 'SHOW data_directory')"
[[ "$pg_dir" == /tmp/pg_virtualenv.*/data/18/regress ]] || exit 9
psql -Xq -v ON_ERROR_STOP=1 -d postgres <<'SQL'
CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE empire_predictive_cash_candidate_reader NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_predictive_cash_candidate_login LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
CREATE ROLE empire_cash_untrusted_login LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
SQL
createdb -E UTF8 -T template0 empire_v415_fixture
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture <<'SQL'
GRANT USAGE,CREATE ON SCHEMA public TO empiredb_migrator;
SET ROLE empiredb_migrator;
CREATE TABLE public.empire_tenant_role_bindings(
 role_name name PRIMARY KEY,tenant_id uuid NOT NULL,active boolean NOT NULL
);
INSERT INTO public.empire_tenant_role_bindings VALUES
 ('empire_predictive_cash_candidate_login','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
CREATE FUNCTION public.empire_current_tenant_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path=''
AS $tenant$
 SELECT tenant_id FROM public.empire_tenant_role_bindings
 WHERE role_name=session_user AND active IS TRUE LIMIT 1
$tenant$;
REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC;
CREATE TABLE public.buyers(id uuid PRIMARY KEY,org_id uuid);
CREATE TABLE public.fulfilment_orders(
 id uuid PRIMARY KEY,buyer_id uuid,
 state text NOT NULL,settled_at timestamptz,
 price_cents bigint,commercial_payload jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE public.bsc_payment_requests(
 id uuid PRIMARY KEY,fulfilment_order_id uuid,buyer_id uuid,
 settlement_mode text,status text,approved_by text,approved_at timestamptz,
 amount_usdt numeric,commercial_terms_sha256 text,treasury_address text
);
CREATE TABLE public.bsc_payment_evidence(
 id uuid PRIMARY KEY,request_id uuid,fulfilment_order_id uuid,
 chain_id integer,token_contract text,confirmations integer,
 treasury_address text,commercial_terms_sha256 text,
 verified_at timestamptz,amount_raw numeric
);
INSERT INTO public.buyers VALUES
 ('11111111-1111-4111-8111-111111111111','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('22222222-2222-4222-8222-222222222222','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
INSERT INTO public.fulfilment_orders VALUES
 ('33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
 'settled',now()-interval '1 day',25000,
 jsonb_build_object('commercial_terms_sha256',repeat('a',64))),
 ('44444444-4444-4444-8444-444444444444','22222222-2222-4222-8222-222222222222',
 'settled',now()-interval '1 day',45000,
 jsonb_build_object('commercial_terms_sha256',repeat('b',64))),
 ('55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111',
 'settled',now()-interval '1 day',15000,
 jsonb_build_object('commercial_terms_sha256',repeat('c',64))),
 ('66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111',
 'settled',now()-interval '1 day',27000,
 jsonb_build_object('commercial_terms_sha256',repeat('d',64)));
INSERT INTO public.bsc_payment_requests VALUES
 ('77777777-7777-4777-8777-777777777777',
 '33333333-3333-4333-8333-333333333333','11111111-1111-4111-8111-111111111111',
 'direct','approved','founder',now()-interval '2 days',
 250,repeat('a',64),'0x1111111111111111111111111111111111111111'),
 ('88888888-8888-4888-8888-888888888888',
 '44444444-4444-4444-8444-444444444444','22222222-2222-4222-8222-222222222222',
 'direct','approved','founder',now()-interval '2 days',
 450,repeat('b',64),'0x2222222222222222222222222222222222222222'),
 ('99999999-9999-4999-8999-999999999999',
 '55555555-5555-4555-8555-555555555555','11111111-1111-4111-8111-111111111111',
 'escrow','approved','founder',now()-interval '2 days',
 150,repeat('c',64),'0x1111111111111111111111111111111111111111'),
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaab',
 '66666666-6666-4666-8666-666666666666','11111111-1111-4111-8111-111111111111',
 'direct','approved','founder',now()-interval '2 days',
 270,repeat('d',64),'0x1111111111111111111111111111111111111111');
INSERT INTO public.bsc_payment_evidence VALUES
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 '77777777-7777-4777-8777-777777777777',
 '33333333-3333-4333-8333-333333333333',
 56,'0x55d398326f99059ff775485246999027b3197955',15,
 '0x1111111111111111111111111111111111111111',repeat('a',64),
 now()-interval '1 day',250000000000000000000),
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 '88888888-8888-4888-8888-888888888888',
 '44444444-4444-4444-8444-444444444444',
 56,'0x55d398326f99059ff775485246999027b3197955',15,
 '0x2222222222222222222222222222222222222222',repeat('b',64),
 now()-interval '1 day',450000000000000000000),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd',
 '99999999-9999-4999-8999-999999999999',
 '55555555-5555-4555-8555-555555555555',
 56,'0x55d398326f99059ff775485246999027b3197955',15,
 '0x1111111111111111111111111111111111111111',repeat('c',64),
 now()-interval '1 day',150000000000000000000),
 ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaab',
 '66666666-6666-4666-8666-666666666666',
 56,'0x55d398326f99059ff775485246999027b3197955',11,
 '0x1111111111111111111111111111111111111111',repeat('d',64),
 now()-interval '1 day',270000000000000000000);
CREATE TABLE public.commercial_outcomes(
 id uuid PRIMARY KEY,fulfilment_order_id uuid NOT NULL,
 delivery_outcome text NOT NULL,recorded_at timestamptz NOT NULL
);
INSERT INTO public.commercial_outcomes VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
 '33333333-3333-4333-8333-333333333333','refunded',now()-interval '1 hour'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
 '55555555-5555-4555-8555-555555555555','failed',now()-interval '1 hour'),
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc',
 '44444444-4444-4444-8444-444444444444','refunded',now()-interval '1 hour');
ALTER TABLE public.fulfilment_orders ADD COLUMN created_at timestamptz NOT NULL DEFAULT now(), ADD COLUMN opportunity_id uuid;
UPDATE public.fulfilment_orders SET created_at=now()-interval '7 days';
UPDATE public.fulfilment_orders SET opportunity_id=CASE
 WHEN id='33333333-3333-4333-8333-333333333333'::uuid THEN 'a0000000-0000-4000-8000-000000000001'::uuid
 WHEN id='55555555-5555-4555-8555-555555555555'::uuid THEN 'a0000000-0000-4000-8000-000000000002'::uuid
 WHEN id='66666666-6666-4666-8666-666666666666'::uuid THEN 'a0000000-0000-4000-8000-000000000002'::uuid
 ELSE NULL END;
INSERT INTO public.fulfilment_orders(id,buyer_id,state,settled_at,price_cents,commercial_payload,created_at,opportunity_id)
VALUES
 ('10000000-0000-4000-8000-000000000001','11111111-1111-4111-8111-111111111111','rejected',NULL,0,'{}',now()-interval '7 days','a0000000-0000-4000-8000-000000000003'),
 ('10000000-0000-4000-8000-000000000002','11111111-1111-4111-8111-111111111111','cancelled',NULL,0,'{}',now()-interval '7 days',NULL),
 ('10000000-0000-4000-8000-000000000003','11111111-1111-4111-8111-111111111111','raw',NULL,0,'{}',now()-interval '7 days','a0000000-0000-4000-8000-000000000004'),
 ('10000000-0000-4000-8000-000000000004','11111111-1111-4111-8111-111111111111','outcome_captured',now()-interval '1 day',20000,'{}',now()-interval '7 days','a0000000-0000-4000-8000-000000000005'),
 ('10000000-0000-4000-8000-000000000005','11111111-1111-4111-8111-111111111111','rejected',NULL,0,'{}',now()-interval '80 days','a0000000-0000-4000-8000-000000000006');
CREATE TABLE public.gtm_opportunities (id uuid PRIMARY KEY);
INSERT INTO public.gtm_opportunities VALUES
 ('a0000000-0000-4000-8000-000000000001'),
 ('a0000000-0000-4000-8000-000000000002'),
 ('a0000000-0000-4000-8000-000000000003'),
 ('a0000000-0000-4000-8000-000000000004'),
 ('a0000000-0000-4000-8000-000000000005'),
 ('a0000000-0000-4000-8000-000000000006'),
 ('a0000000-0000-4000-8000-000000000007'),
 ('a0000000-0000-4000-8000-000000000008'),
 ('b0000000-0000-4000-8000-000000000001');
RESET ROLE;
SQL
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture -f migrations/empiredb/067_predictive_direct_bsc_cash_candidate_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture -f migrations/empiredb/068_predictive_revenue_operational_reversal_signals_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture -f migrations/empiredb/069_predictive_revenue_tenant_order_cohort_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture -f migrations/empiredb/070_predictive_revenue_gtm_opportunity_custody_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture <<'SQL'
SET ROLE empiredb_migrator;
INSERT INTO public.empire_predictive_opportunity_custody_v418
 (opportunity_id,tenant_id,source_evidence_digest,owner_evidence_digest,first_seen_at,acquisition_cost_minor,currency_code)
SELECT id,
 CASE WHEN id::text LIKE 'b%' THEN 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid
 ELSE 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid END,
 repeat('a',64),repeat('b',64),
 now()-CASE WHEN id='a0000000-0000-4000-8000-000000000008'::uuid THEN interval '80 days' ELSE interval '7 days' END,
 100,'USD'
FROM public.gtm_opportunities;
INSERT INTO public.empire_predictive_opportunity_states_v418
 (opportunity_id,state_seq,state_name,state_at,state_evidence_digest)
SELECT id,1,'OPEN',now()-interval '6 days',repeat('c',64)
FROM public.gtm_opportunities WHERE id::text NOT LIKE '%000000000007';
INSERT INTO public.empire_predictive_opportunity_states_v418
 (opportunity_id,state_seq,state_name,state_at,state_evidence_digest)
VALUES
 ('a0000000-0000-4000-8000-000000000001',2,'CONVERTED',now()-interval '4 days',repeat('d',64)),
 ('a0000000-0000-4000-8000-000000000002',2,'DEAD',now()-interval '4 days',repeat('d',64)),
 ('a0000000-0000-4000-8000-000000000003',2,'DISQUALIFIED',now()-interval '4 days',repeat('d',64)),
 ('a0000000-0000-4000-8000-000000000005',2,'CONVERTED',now()-interval '4 days',repeat('d',64));
DO $negative$
DECLARE blocked boolean; reason text;
BEGIN
 blocked:=false;
 BEGIN
   INSERT INTO public.empire_predictive_opportunity_states_v418
   (opportunity_id,state_seq,state_name,state_at,state_evidence_digest)
   VALUES('a0000000-0000-4000-8000-000000000007',1,'DEAD',now(),repeat('e',64));
 EXCEPTION WHEN raise_exception THEN
   GET STACKED DIAGNOSTICS reason=MESSAGE_TEXT;
   blocked:=reason LIKE '%V418_FIRST_STATE_MUST_BE_OPEN%';
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'V418_FIRST_STATE_INVALID_NOT_DENIED'; END IF;
 blocked:=false;
 BEGIN
   INSERT INTO public.empire_predictive_opportunity_states_v418
   (opportunity_id,state_seq,state_name,state_at,state_evidence_digest)
   VALUES('a0000000-0000-4000-8000-000000000004',2,'CONVERTED',now(),repeat('f',64));
 EXCEPTION WHEN raise_exception THEN
   GET STACKED DIAGNOSTICS reason=MESSAGE_TEXT;
   blocked:=reason LIKE '%V418_CROSS_TENANT_OR_MISSING_CONVERSION_ORDER%';
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'V418_UNLINKED_CONVERSION_NOT_DENIED'; END IF;
 blocked:=false;
 BEGIN
   INSERT INTO public.empire_predictive_opportunity_states_v418
   (opportunity_id,state_seq,state_name,state_at,state_evidence_digest)
   VALUES('a0000000-0000-4000-8000-000000000001',3,'DEAD',now(),repeat('f',64));
 EXCEPTION WHEN raise_exception THEN
   GET STACKED DIAGNOSTICS reason=MESSAGE_TEXT;
   blocked:=reason LIKE '%V418_INVALID_TERMINAL_TRANSITION%';
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'V418_TERMINAL_REOPEN_NOT_DENIED'; END IF;
 blocked:=false;
 BEGIN
   UPDATE public.empire_predictive_opportunity_custody_v418 SET acquisition_cost_minor=999
   WHERE opportunity_id='a0000000-0000-4000-8000-000000000001';
 EXCEPTION WHEN raise_exception THEN
   GET STACKED DIAGNOSTICS reason=MESSAGE_TEXT;
   blocked:=reason LIKE '%V418_APPEND_ONLY_CUSTODY_EVENTS%';
 END;
 IF NOT blocked THEN RAISE EXCEPTION 'V418_CUSTODY_MUTATION_NOT_DENIED'; END IF;
END;
$negative$;
RESET ROLE;
SQL
psql -Xq -v ON_ERROR_STOP=1 -d postgres <<'SQL'
GRANT empire_predictive_cash_candidate_reader TO empire_predictive_cash_candidate_login WITH INHERIT FALSE, SET TRUE;
SQL
password="$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
# Password in SQL passed over local ephemeral socket; never logged.
psql -Xq -v ON_ERROR_STOP=1 -d postgres -v password="$password" <<'SQL'
ALTER ROLE empire_predictive_cash_candidate_login PASSWORD :'password';
SQL
V415_EPHEMERAL_PASSWORD="$password" PYTHONPATH=. /srv/empire_os/.venv/bin/python -B scripts/rehearse_predictive_revenue_v418_opportunities_20261025.py
echo 'V418_DISPOSABLE_PG18_PASS original_empiredb_modified=false settlement_executed=false'
