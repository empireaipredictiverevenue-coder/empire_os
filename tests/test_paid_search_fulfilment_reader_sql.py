"""Live-SQL-shape check in a disposable, socket-free PostgreSQL cluster.

No production DB credentials, orders, payment records or connections.
"""
from test_empiredb_materializer_bootstrap import execute
from test_paid_search_fulfilment_reader import OID,RID,BID,EID,PAYER
from empire_os.paid_search_fulfilment_review import TREASURY
from empire_os.paid_search_fulfilment_reader import ORDER_SQL,PAYMENT_SQL,EVIDENCE_SQL


def test_exact_existing_reader_sql_executes_under_current_financial_role(execute):
    execute("postgres","CREATE DATABASE empiredb;")
    execute("empiredb",f"""
      CREATE ROLE empire_revenue_recognizer NOLOGIN NOINHERIT;
      CREATE TABLE public.fulfilment_orders(
        id uuid PRIMARY KEY,buyer_id uuid,state text,price_cents bigint,
        commercial_payload jsonb,delivery_payload jsonb
      );
      CREATE TABLE public.bsc_payment_requests(
        id uuid PRIMARY KEY,buyer_id uuid,fulfilment_order_id uuid,
        settlement_mode text,status text,amount_usdt numeric,
        commercial_terms_sha256 text,payer_address text,treasury_address text,
        approved_by text,approved_at timestamptz,expires_at timestamptz,
        created_at timestamptz DEFAULT clock_timestamp()
      );
      CREATE TABLE public.bsc_payment_evidence(
        id uuid PRIMARY KEY,request_id uuid,fulfilment_order_id uuid,
        chain_id int,token_contract text,transaction_hash text,block_hash text,
        block_number bigint,log_index bigint,amount_raw numeric,
        confirmations int,verified_at timestamptz,sender_address text,
        treasury_address text,commercial_terms_sha256 text
      );
      INSERT INTO public.fulfilment_orders VALUES(
        '{OID}','{BID}','accepted',19900,
        '{{"product_code":"competitor_search_gap","buyer_terms_accepted":true,
           "settlement_mode":"direct","commercial_terms_sha256":"{'a'*64}",
           "payer_wallet":"{PAYER}"}}'::jsonb,
        '{{"target_domain":"example.com","email":"hidden@example.com"}}'::jsonb
      );
      INSERT INTO public.bsc_payment_requests(
        id,buyer_id,fulfilment_order_id,settlement_mode,status,amount_usdt,
        commercial_terms_sha256,payer_address,treasury_address,
        approved_by,approved_at,expires_at)
      VALUES(
        '{RID}','{BID}','{OID}','direct','approved',199,
        '{'a'*64}','{PAYER}','{TREASURY}','human',
        clock_timestamp()-interval '10 minutes',
        clock_timestamp()+interval '1 hour'
      );
      INSERT INTO public.bsc_payment_evidence VALUES(
        '{EID}','{RID}','{OID}',56,
        '0x55d398326f99059ff775485246999027b3197955',
        '0x{'b'*64}','0x{'c'*64}',1000,0,199000000000000000000,
        12,clock_timestamp(),'{PAYER}','{TREASURY}','{'a'*64}'
      );
      ALTER TABLE public.fulfilment_orders ENABLE ROW LEVEL SECURITY;
      ALTER TABLE public.bsc_payment_requests ENABLE ROW LEVEL SECURITY;
      ALTER TABLE public.bsc_payment_evidence ENABLE ROW LEVEL SECURITY;
      GRANT SELECT ON public.fulfilment_orders,public.bsc_payment_requests,
        public.bsc_payment_evidence TO empire_revenue_recognizer;
      CREATE POLICY order_recognizer ON public.fulfilment_orders FOR SELECT
        TO empire_revenue_recognizer USING (true);
      CREATE POLICY payment_recognizer ON public.bsc_payment_requests FOR SELECT
        TO empire_revenue_recognizer USING (true);
      CREATE POLICY evidence_recognizer ON public.bsc_payment_evidence FOR SELECT
        TO empire_revenue_recognizer USING (true);
    """)
    # Validate all three SQL projections actually execute against an isolated
    # PostgreSQL schema under only the dedicated recognizer permissions.
    for sql,identifier in (
        (ORDER_SQL,OID),(PAYMENT_SQL,OID),(EVIDENCE_SQL,RID)
    ):
        compiled=sql.replace("%s::uuid",f"'{identifier}'::uuid")
        assert compiled!=sql
        execute("empiredb","SET ROLE empire_revenue_recognizer;\n"+compiled+";\nRESET ROLE;")
    execute("empiredb",f"""
      SET ROLE empire_revenue_recognizer;
      SELECT id FROM public.fulfilment_orders WHERE id='{OID}';
      RESET ROLE;
    """)
