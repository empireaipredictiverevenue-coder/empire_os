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
RESET ROLE;
SQL
psql -Xq -v ON_ERROR_STOP=1 -d empire_v415_fixture -f migrations/empiredb/067_predictive_direct_bsc_cash_candidate_held.sql
psql -Xq -v ON_ERROR_STOP=1 -d postgres <<'SQL'
GRANT empire_predictive_cash_candidate_reader TO empire_predictive_cash_candidate_login WITH INHERIT FALSE, SET TRUE;
SQL
password="$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
# Password in SQL passed over local ephemeral socket; never logged.
psql -Xq -v ON_ERROR_STOP=1 -d postgres -v password="$password" <<'SQL'
ALTER ROLE empire_predictive_cash_candidate_login PASSWORD :'password';
SQL
V415_EPHEMERAL_PASSWORD="$password" PYTHONPATH=. /srv/empire_os/.venv/bin/python -B scripts/rehearse_predictive_revenue_v415_cash_reader_20261025.py
echo 'V415_DISPOSABLE_PG18_PASS original_empiredb_modified=false settlement_executed=false'
