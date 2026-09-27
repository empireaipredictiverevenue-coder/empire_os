-- EmpireDB active runtime parity — schema, roles and RLS.
-- Source-derived from the existing governed Supabase migrations.
-- All source tables covered here were verified empty on 2026-09-27.
-- No data copy, no cutover, no outbound, no funds movement.

SET ROLE empiredb_migrator;

DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY[
    'empire_payment_approver',
    'empire_bsc_verifier',
    'empire_escrow_verifier',
    'empire_commercial_approver',
    'empire_outcome_recorder',
    'empire_revenue_recognizer',
    'empire_closer_planner',
    'empire_conversation_ingest',
    'empire_conversation_reader',
    'empire_revenue_exchange_ingest',
    'empire_revenue_exchange_reader'
  ] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN NOINHERIT', r);
    END IF;
  END LOOP;
END $$;

GRANT USAGE ON SCHEMA public TO
  empire_payment_approver,
  empire_bsc_verifier,
  empire_escrow_verifier,
  empire_commercial_approver,
  empire_outcome_recorder,
  empire_revenue_recognizer,
  empire_closer_planner,
  empire_conversation_ingest,
  empire_conversation_reader,
  empire_revenue_exchange_ingest,
  empire_revenue_exchange_reader;

CREATE TABLE IF NOT EXISTS public.bsc_payment_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  amount_usdt numeric NOT NULL CHECK (
    amount_usdt > 0 AND amount_usdt < 1e59
    AND amount_usdt = trunc(amount_usdt,18)
  ),
  payer_address text NOT NULL CHECK (payer_address ~ '^0x[0-9a-f]{40}$'),
  treasury_address text NOT NULL CHECK (treasury_address ~ '^0x[0-9a-f]{40}$'),
  commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
  min_block_number bigint NOT NULL CHECK (min_block_number > 0),
  status text NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending','approved','cancelled','expired')
  ),
  approved_by text,
  approved_at timestamptz,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  idempotency_key text CHECK (
    idempotency_key IS NULL OR length(trim(idempotency_key)) BETWEEN 8 AND 128
  ),
  settlement_mode text NOT NULL DEFAULT 'direct' CHECK (
    settlement_mode IN ('direct','escrow')
  ),
  CHECK (expires_at > created_at),
  CHECK (
    status <> 'approved'
    OR (
      approved_by IS NOT NULL
      AND length(trim(approved_by)) > 0
      AND approved_at IS NOT NULL
      AND approved_at < expires_at
    )
  )
);
CREATE INDEX IF NOT EXISTS bsc_payment_requests_buyer_idx
  ON public.bsc_payment_requests(buyer_id);
CREATE INDEX IF NOT EXISTS bsc_payment_requests_order_idx
  ON public.bsc_payment_requests(fulfilment_order_id);
CREATE UNIQUE INDEX IF NOT EXISTS bsc_payment_requests_idempotency_key_uidx
  ON public.bsc_payment_requests(idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS bsc_payment_requests_one_open_order_uidx
  ON public.bsc_payment_requests(fulfilment_order_id)
  WHERE status IN ('pending','approved');

CREATE TABLE IF NOT EXISTS public.bsc_payment_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL UNIQUE
    REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
  chain_id integer NOT NULL CHECK (chain_id=56),
  token_contract text NOT NULL CHECK (
    token_contract='0x55d398326f99059ff775485246999027b3197955'
  ),
  transaction_hash text NOT NULL UNIQUE
    CHECK (transaction_hash ~ '^0x[0-9a-f]{64}$'),
  block_hash text NOT NULL CHECK (block_hash ~ '^0x[0-9a-f]{64}$'),
  block_number bigint NOT NULL CHECK (block_number>0),
  log_index bigint NOT NULL CHECK (log_index>=0),
  amount_raw numeric NOT NULL CHECK (
    amount_raw>0 AND amount_raw<power(2::numeric,256)
    AND amount_raw=trunc(amount_raw)
  ),
  confirmations integer NOT NULL CHECK (confirmations>=12),
  verified_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now(),
  fulfilment_order_id uuid NOT NULL UNIQUE
    REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  sender_address text NOT NULL CHECK (sender_address ~ '^0x[0-9a-f]{40}$'),
  treasury_address text NOT NULL CHECK (treasury_address ~ '^0x[0-9a-f]{40}$'),
  commercial_terms_sha256 text NOT NULL
    CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS public.bsc_payment_request_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL
    REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
  event_type text NOT NULL CHECK (
    event_type IN ('proposed','approved','cancelled','expired','evidence_recorded')
  ),
  actor text NOT NULL CHECK (length(trim(actor)) BETWEEN 1 AND 200),
  db_role text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS bsc_payment_request_events_request_idx
  ON public.bsc_payment_request_events(request_id,created_at);

CREATE TABLE IF NOT EXISTS public.bsc_escrow_agreements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL UNIQUE
    REFERENCES public.bsc_payment_requests(id) ON DELETE RESTRICT,
  escrow_id text NOT NULL UNIQUE CHECK (escrow_id ~ '^0x[0-9a-f]{64}$'),
  contract_address text NOT NULL CHECK (contract_address ~ '^0x[0-9a-f]{40}$'),
  beneficiary_address text NOT NULL CHECK (beneficiary_address ~ '^0x[0-9a-f]{40}$'),
  runtime_sha256 text NOT NULL CHECK (runtime_sha256 ~ '^[0-9a-f]{64}$'),
  creation_transaction_hash text NOT NULL UNIQUE
    CHECK (creation_transaction_hash ~ '^0x[0-9a-f]{64}$'),
  creation_block_hash text NOT NULL CHECK (creation_block_hash ~ '^0x[0-9a-f]{64}$'),
  creation_block_number bigint NOT NULL CHECK (creation_block_number>0),
  creation_confirmations integer NOT NULL CHECK (creation_confirmations>=12),
  creation_chain_timestamp timestamptz NOT NULL,
  payer_address text NOT NULL CHECK (payer_address ~ '^0x[0-9a-f]{40}$'),
  amount_raw numeric NOT NULL CHECK (amount_raw>0 AND amount_raw=trunc(amount_raw)),
  commercial_terms_sha256 text NOT NULL
    CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
  funding_deadline timestamptz NOT NULL,
  refund_after timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (
    status IN ('open','funded','disputed','resolution_pending','released','refunded','cancelled')
  ),
  creation_verified_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (funding_deadline < refund_after)
);

CREATE TABLE IF NOT EXISTS public.bsc_escrow_evidence (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id uuid NOT NULL
    REFERENCES public.bsc_escrow_agreements(id) ON DELETE RESTRICT,
  action text NOT NULL CHECK (action IN ('funded','released','refunded')),
  transaction_hash text NOT NULL UNIQUE
    CHECK (transaction_hash ~ '^0x[0-9a-f]{64}$'),
  block_hash text NOT NULL CHECK (block_hash ~ '^0x[0-9a-f]{64}$'),
  block_number bigint NOT NULL CHECK (block_number>0),
  amount_raw numeric NOT NULL CHECK (amount_raw>0 AND amount_raw=trunc(amount_raw)),
  party_address text NOT NULL CHECK (party_address ~ '^0x[0-9a-f]{40}$'),
  confirmations integer NOT NULL CHECK (confirmations>=12),
  chain_timestamp timestamptz NOT NULL,
  verified_at timestamptz NOT NULL,
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE(agreement_id,action)
);
CREATE INDEX IF NOT EXISTS bsc_escrow_evidence_agreement_idx
  ON public.bsc_escrow_evidence(agreement_id,recorded_at);

CREATE TABLE IF NOT EXISTS public.commercial_terms_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fulfilment_order_id uuid NOT NULL
    REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','approved','rejected')),
  price_cents bigint NOT NULL CHECK (price_cents>0),
  acquisition_cost_cents bigint NOT NULL DEFAULT 0 CHECK (acquisition_cost_cents>=0),
  fulfilment_cost_cents bigint NOT NULL DEFAULT 0 CHECK (fulfilment_cost_cents>=0),
  expected_margin_cents bigint NOT NULL CHECK (expected_margin_cents>0),
  terms jsonb NOT NULL,
  commercial_terms_sha256 text NOT NULL
    CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
  idempotency_key text NOT NULL UNIQUE CHECK (length(trim(idempotency_key))>=8),
  proposed_by text NOT NULL CHECK (length(trim(proposed_by))>0),
  proposed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  decided_by text,
  decided_at timestamptz,
  decision_note text
);
CREATE UNIQUE INDEX IF NOT EXISTS commercial_terms_one_pending_order_uidx
  ON public.commercial_terms_reviews(fulfilment_order_id)
  WHERE status='pending';

CREATE TABLE IF NOT EXISTS public.commercial_terms_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id uuid NOT NULL
    REFERENCES public.commercial_terms_reviews(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid NOT NULL
    REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  event_type text NOT NULL CHECK (
    event_type IN ('proposed','approved','rejected','accepted')
  ),
  actor text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS commercial_terms_events_order_idx
  ON public.commercial_terms_events(fulfilment_order_id,occurred_at DESC);

CREATE TABLE IF NOT EXISTS public.buyer_capacity_intakes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  closer_case_id uuid NOT NULL UNIQUE
    REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  buyer_id uuid NOT NULL REFERENCES public.buyers(id) ON DELETE RESTRICT,
  source_reply_ids uuid[] NOT NULL DEFAULT '{}'::uuid[],
  territory text,
  daily_cap integer CHECK (daily_cap IS NULL OR daily_cap BETWEEN 1 AND 10000),
  delivery_route text CHECK (
    delivery_route IS NULL OR delivery_route IN ('email','webhook','phone','api')
  ),
  delivery_reference text,
  state text NOT NULL DEFAULT 'partial'
    CHECK (state IN ('partial','complete')),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.commercial_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fulfilment_order_id uuid NOT NULL
    REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  delivery_outcome text NOT NULL CHECK (
    delivery_outcome IN ('delivered','confirmed','rejected','failed','refunded','unknown')
  ),
  conversion_outcome text NOT NULL CHECK (
    conversion_outcome IN ('unknown','qualified','booked','won','lost','no_response')
  ),
  buyer_satisfaction numeric(3,2)
    CHECK (buyer_satisfaction IS NULL OR buyer_satisfaction BETWEEN 1 AND 5),
  evidence_kind text NOT NULL CHECK (
    evidence_kind IN (
      'outbound_reply','buyer_feedback','delivery_receipt',
      'crm','provider_event','manual_verified'
    )
  ),
  evidence_reference text NOT NULL CHECK (length(trim(evidence_reference))>0),
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotency_key text NOT NULL UNIQUE
    CHECK (length(trim(idempotency_key)) BETWEEN 8 AND 160),
  actor text NOT NULL CHECK (length(trim(actor)) BETWEEN 1 AND 200),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS commercial_outcomes_order_idx
  ON public.commercial_outcomes(fulfilment_order_id,recorded_at DESC);

CREATE TABLE IF NOT EXISTS public.empire_conversations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL CHECK (channel IN ('email','sms','voice','a2a')),
  state text NOT NULL DEFAULT 'open'
    CHECK (state IN ('open','engaged','paused','closed')),
  prospect_id uuid REFERENCES public.prospects(id) ON DELETE RESTRICT,
  entity_id uuid REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  buyer_id uuid REFERENCES public.buyers(id) ON DELETE RESTRICT,
  opportunity_id uuid REFERENCES public.gtm_opportunities(id) ON DELETE RESTRICT,
  closer_case_id uuid REFERENCES public.closer_cases(id) ON DELETE RESTRICT,
  outbound_intent_id uuid REFERENCES public.outbound_intents(id) ON DELETE RESTRICT,
  external_conversation_id text,
  provider text,
  opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CHECK (
    prospect_id IS NOT NULL OR entity_id IS NOT NULL
    OR buyer_id IS NOT NULL OR closer_case_id IS NOT NULL
  )
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_empire_conversation_external
  ON public.empire_conversations(channel,provider,external_conversation_id)
  WHERE external_conversation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_empire_conversations_participants
  ON public.empire_conversations(prospect_id,buyer_id,updated_at DESC);

CREATE TABLE IF NOT EXISTS public.empire_conversation_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL
    REFERENCES public.empire_conversations(id) ON DELETE RESTRICT,
  event_type text NOT NULL,
  direction text NOT NULL CHECK (direction IN ('inbound','outbound','internal')),
  actor text,
  body_text text,
  provider_event_id text,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_empire_conversation_provider_event
  ON public.empire_conversation_events(conversation_id,provider_event_id)
  WHERE provider_event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.intelligence_employment (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL
    REFERENCES public.intelligence_people(id) ON DELETE RESTRICT,
  entity_id uuid NOT NULL
    REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  title text NOT NULL,
  normalized_title text NOT NULL,
  seniority text,
  department text,
  buying_role text CHECK (
    buying_role IS NULL OR buying_role IN (
      'economic_buyer','functional_buyer','champion','technical_approver',
      'commercial_approver','influencer','user','unknown'
    )
  ),
  is_current boolean NOT NULL DEFAULT true,
  valid_from timestamptz,
  valid_to timestamptz,
  confidence numeric(5,4) NOT NULL DEFAULT 0
    CHECK (confidence BETWEEN 0 AND 1),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS intelligence_employment_entity_idx
  ON public.intelligence_employment(entity_id,is_current);
CREATE INDEX IF NOT EXISTS intelligence_employment_person_idx
  ON public.intelligence_employment(person_id,is_current);

CREATE TABLE IF NOT EXISTS public.intelligence_segment_membership (
  entity_id uuid NOT NULL
    REFERENCES public.business_entities(id) ON DELETE RESTRICT,
  segment_id uuid NOT NULL
    REFERENCES public.intelligence_segments(id) ON DELETE RESTRICT,
  score numeric(7,4) NOT NULL CHECK (score BETWEEN 0 AND 100),
  confidence numeric(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  scored_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(entity_id,segment_id)
);

CREATE TABLE IF NOT EXISTS public.revenue_exchange_observations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  niche text NOT NULL,
  metro text NOT NULL,
  qualified_inventory_count integer NOT NULL
    CHECK (qualified_inventory_count>=0),
  active_buyer_capacity integer NOT NULL
    CHECK (active_buyer_capacity>=0),
  verified_price_per_lead_cents integer[] NOT NULL DEFAULT '{}',
  observed_at timestamptz NOT NULL,
  source text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  observation_key text,
  CHECK (0 < ALL (verified_price_per_lead_cents))
);
CREATE INDEX IF NOT EXISTS idx_revenue_exchange_market_time
  ON public.revenue_exchange_observations(niche,metro,observed_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_revenue_exchange_observation_key
  ON public.revenue_exchange_observations(observation_key)
  WHERE observation_key IS NOT NULL;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'bsc_payment_requests','bsc_payment_evidence',
    'bsc_payment_request_events','bsc_escrow_agreements',
    'bsc_escrow_evidence','commercial_terms_reviews',
    'commercial_terms_events','buyer_capacity_intakes',
    'commercial_outcomes','empire_conversations',
    'empire_conversation_events','intelligence_employment',
    'intelligence_segment_membership','revenue_exchange_observations'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC',t);
  END LOOP;
END $$;

-- Generic application visibility: reads only on governed commercial lanes.
GRANT SELECT ON
  public.bsc_payment_requests,
  public.bsc_payment_evidence,
  public.bsc_payment_request_events,
  public.bsc_escrow_agreements,
  public.bsc_escrow_evidence,
  public.commercial_terms_reviews,
  public.commercial_terms_events,
  public.buyer_capacity_intakes,
  public.commercial_outcomes,
  public.empire_conversations,
  public.empire_conversation_events,
  public.revenue_exchange_observations
TO empiredb_app;

-- Intelligence materialization remains an application capability.
GRANT SELECT,INSERT,UPDATE ON
  public.intelligence_employment,
  public.intelligence_segment_membership
TO empiredb_app;

-- Canonical conversation creation/update remains app-owned;
-- provider event ingestion is separated in migration 016.
GRANT INSERT,UPDATE ON public.empire_conversations TO empiredb_app;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'bsc_payment_requests','bsc_payment_evidence',
    'bsc_payment_request_events','bsc_escrow_agreements',
    'bsc_escrow_evidence','commercial_terms_reviews',
    'commercial_terms_events','buyer_capacity_intakes',
    'commercial_outcomes','empire_conversations',
    'empire_conversation_events','intelligence_employment',
    'intelligence_segment_membership','revenue_exchange_observations'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',t||'_app_select',t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I FOR SELECT TO empiredb_app USING (true)',
      t||'_app_select',t
    );
  END LOOP;
END $$;

CREATE POLICY intelligence_employment_app_insert
ON public.intelligence_employment FOR INSERT TO empiredb_app
WITH CHECK (true);
CREATE POLICY intelligence_employment_app_update
ON public.intelligence_employment FOR UPDATE TO empiredb_app
USING (true) WITH CHECK (true);

CREATE POLICY intelligence_segment_membership_app_insert
ON public.intelligence_segment_membership FOR INSERT TO empiredb_app
WITH CHECK (true);
CREATE POLICY intelligence_segment_membership_app_update
ON public.intelligence_segment_membership FOR UPDATE TO empiredb_app
USING (true) WITH CHECK (true);

CREATE POLICY empire_conversations_app_insert
ON public.empire_conversations FOR INSERT TO empiredb_app
WITH CHECK (true);
CREATE POLICY empire_conversations_app_update
ON public.empire_conversations FOR UPDATE TO empiredb_app
USING (true) WITH CHECK (true);

RESET ROLE;
