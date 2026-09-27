BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_commercial_approver') THEN
    CREATE ROLE empire_commercial_approver NOLOGIN NOINHERIT;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='empire_commercial_approver_login') THEN
    CREATE ROLE empire_commercial_approver_login LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;
ALTER ROLE empire_commercial_approver_login PASSWORD NULL;
GRANT empire_commercial_approver TO empire_commercial_approver_login;
ALTER ROLE empire_commercial_approver_login SET statement_timeout='15s';
ALTER ROLE empire_commercial_approver_login SET idle_in_transaction_session_timeout='30s';
COMMENT ON ROLE empire_commercial_approver_login IS 'Dedicated commercial approval login; password provisioned out of band.';

CREATE TABLE public.commercial_terms_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  price_cents bigint NOT NULL CHECK (price_cents > 0),
  acquisition_cost_cents bigint NOT NULL DEFAULT 0 CHECK (acquisition_cost_cents >= 0),
  fulfilment_cost_cents bigint NOT NULL DEFAULT 0 CHECK (fulfilment_cost_cents >= 0),
  expected_margin_cents bigint NOT NULL CHECK (expected_margin_cents > 0),
  terms jsonb NOT NULL,
  commercial_terms_sha256 text NOT NULL CHECK (commercial_terms_sha256 ~ '^[0-9a-f]{64}$'),
  idempotency_key text NOT NULL UNIQUE CHECK (length(trim(idempotency_key)) >= 8),
  proposed_by text NOT NULL CHECK (length(trim(proposed_by)) > 0),
  proposed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  decided_by text,
  decided_at timestamptz,
  decision_note text
);
CREATE UNIQUE INDEX commercial_terms_one_pending_order_uidx
  ON public.commercial_terms_reviews(fulfilment_order_id) WHERE status='pending';
CREATE TABLE public.commercial_terms_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id uuid NOT NULL REFERENCES public.commercial_terms_reviews(id) ON DELETE RESTRICT,
  fulfilment_order_id uuid NOT NULL REFERENCES public.fulfilment_orders(id) ON DELETE RESTRICT,
  event_type text NOT NULL CHECK (event_type IN ('proposed','approved','rejected','accepted')),
  actor text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX commercial_terms_events_order_idx
  ON public.commercial_terms_events(fulfilment_order_id, occurred_at DESC);

ALTER TABLE public.commercial_terms_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.commercial_terms_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.commercial_terms_reviews, public.commercial_terms_events
  FROM PUBLIC, anon, authenticated, service_role, empire_commercial_approver;
GRANT SELECT ON public.commercial_terms_reviews, public.commercial_terms_events TO service_role;
GRANT SELECT ON public.commercial_terms_reviews, public.commercial_terms_events TO empire_commercial_approver;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.fulfilment_orders
  FROM anon, authenticated, service_role;
GRANT SELECT ON public.fulfilment_orders TO service_role, empire_commercial_approver;

CREATE FUNCTION public.guard_commercial_terms_events_append_only()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'commercial terms events are append-only'; END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER guard_commercial_terms_events_append_only
BEFORE UPDATE OR DELETE ON public.commercial_terms_events
FOR EACH ROW EXECUTE FUNCTION public.guard_commercial_terms_events_append_only();

CREATE FUNCTION public.propose_commercial_terms(
  p_fulfilment_order_id uuid,
  p_price_cents bigint,
  p_acquisition_cost_cents bigint,
  p_fulfilment_cost_cents bigint,
  p_terms jsonb,
  p_idempotency_key text,
  p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  r public.commercial_terms_reviews%ROWTYPE;
  v_margin bigint;
  v_hash text;
  v_key text := trim(COALESCE(p_idempotency_key,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_price_cents IS NULL OR p_price_cents <= 0 THEN RAISE EXCEPTION 'positive price required'; END IF;
  IF COALESCE(p_acquisition_cost_cents,0) < 0 OR COALESCE(p_fulfilment_cost_cents,0) < 0 THEN
    RAISE EXCEPTION 'costs cannot be negative';
  END IF;
  v_margin := p_price_cents-COALESCE(p_acquisition_cost_cents,0)-COALESCE(p_fulfilment_cost_cents,0);
  IF v_margin <= 0 THEN RAISE EXCEPTION 'positive expected margin required'; END IF;
  IF jsonb_typeof(p_terms) <> 'object' OR p_terms='{}'::jsonb THEN RAISE EXCEPTION 'commercial terms object required'; END IF;
  IF lower(trim(COALESCE(p_terms->>'currency',''))) <> 'usd'
     OR upper(trim(COALESCE(p_terms->>'settlement_asset',''))) <> 'USDT'
     OR upper(trim(COALESCE(p_terms->>'settlement_chain',''))) <> 'BSC' THEN
    RAISE EXCEPTION 'canonical USD price with USDT/BSC settlement terms required';
  END IF;
  IF v_actor='' OR length(v_key)<8 THEN RAISE EXCEPTION 'actor and idempotency key required'; END IF;
  v_hash := encode(sha256(convert_to(p_terms::text,'UTF8')),'hex');

  SELECT * INTO o FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.buyer_id IS NULL OR o.prospect_id IS NULL THEN RAISE EXCEPTION 'allocated buyer and prospect required'; END IF;
  IF o.state NOT IN ('matched','qualified') THEN RAISE EXCEPTION 'matched or qualified order required'; END IF;

  SELECT * INTO r FROM public.commercial_terms_reviews WHERE idempotency_key=v_key;
  IF FOUND THEN
    IF r.fulfilment_order_id IS DISTINCT FROM o.id OR r.price_cents IS DISTINCT FROM p_price_cents
       OR r.commercial_terms_sha256 IS DISTINCT FROM v_hash THEN
      RAISE EXCEPTION 'idempotency key belongs to different commercial terms';
    END IF;
    RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,
                              'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false);
  END IF;

  INSERT INTO public.commercial_terms_reviews(
    fulfilment_order_id,price_cents,acquisition_cost_cents,fulfilment_cost_cents,
    expected_margin_cents,terms,commercial_terms_sha256,idempotency_key,proposed_by
  ) VALUES (o.id,p_price_cents,COALESCE(p_acquisition_cost_cents,0),COALESCE(p_fulfilment_cost_cents,0),
            v_margin,p_terms,v_hash,v_key,v_actor) RETURNING * INTO r;
  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,'proposed',v_actor,jsonb_build_object(
    'price_cents',r.price_cents,'expected_margin_cents',r.expected_margin_cents,
    'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision','proposed','review_id',r.id,'status',r.status,
                            'price_cents',r.price_cents,'expected_margin_cents',r.expected_margin_cents,
                            'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false);
END;
$$;

CREATE FUNCTION public.decide_commercial_terms(
  p_review_id uuid,
  p_decision text,
  p_actor text,
  p_note text DEFAULT ''
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  r public.commercial_terms_reviews%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_decision text := lower(trim(COALESCE(p_decision,'')));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_decision NOT IN ('approved','rejected') THEN RAISE EXCEPTION 'approved or rejected decision required'; END IF;
  IF v_actor='' THEN RAISE EXCEPTION 'decision actor required'; END IF;
  SELECT * INTO r FROM public.commercial_terms_reviews WHERE id=p_review_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'commercial terms review not found'; END IF;
  IF r.status<>'pending' THEN
    RETURN jsonb_build_object('decision','existing','review_id',r.id,'status',r.status,'actual_revenue',false);
  END IF;
  SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state NOT IN ('matched','qualified') THEN RAISE EXCEPTION 'order is no longer reviewable'; END IF;

  UPDATE public.commercial_terms_reviews
     SET status=v_decision,decided_by=v_actor,decided_at=clock_timestamp(),decision_note=trim(COALESCE(p_note,''))
   WHERE id=r.id RETURNING * INTO r;

  IF v_decision='approved' THEN
    UPDATE public.fulfilment_orders
       SET state='offered',price_cents=r.price_cents,
           acquisition_cost_cents=r.acquisition_cost_cents,
           fulfilment_cost_cents=r.fulfilment_cost_cents,
           expected_margin_cents=r.expected_margin_cents,
           commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) || jsonb_build_object(
             'commercial_terms_sha256',r.commercial_terms_sha256,
             'commercial_terms_review_id',r.id,
             'commercial_terms',r.terms,
             'terms_approved_by',v_actor,
             'terms_approved_at',r.decided_at
           ),updated_at=clock_timestamp()
     WHERE id=o.id;
  END IF;

  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,v_decision,v_actor,jsonb_build_object('note',trim(COALESCE(p_note,'')),
         'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision',v_decision,'review_id',r.id,'status',r.status,
                            'fulfilment_order_id',o.id,'actual_revenue',false);
END;
$$;
CREATE FUNCTION public.record_commercial_acceptance(
  p_review_id uuid,
  p_evidence_kind text,
  p_evidence_reference text,
  p_accepted_at timestamptz,
  p_actor text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  r public.commercial_terms_reviews%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_ref text := trim(COALESCE(p_evidence_reference,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_kind NOT IN ('outbound_reply','signed_agreement','manual_verified') THEN
    RAISE EXCEPTION 'supported buyer acceptance evidence required';
  END IF;
  IF v_ref='' OR v_actor='' OR p_accepted_at IS NULL THEN RAISE EXCEPTION 'acceptance evidence, time and actor required'; END IF;
  IF p_accepted_at > clock_timestamp()+interval '5 minutes' THEN RAISE EXCEPTION 'acceptance time cannot be in the future'; END IF;

  SELECT * INTO r FROM public.commercial_terms_reviews WHERE id=p_review_id FOR UPDATE;
  IF NOT FOUND OR r.status<>'approved' THEN RAISE EXCEPTION 'approved commercial terms review required'; END IF;
  IF p_accepted_at < r.decided_at THEN RAISE EXCEPTION 'acceptance cannot predate approved terms'; END IF;
  SELECT * INTO o FROM public.fulfilment_orders WHERE id=r.fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state='accepted' THEN
    RETURN jsonb_build_object('decision','existing_acceptance','fulfilment_order_id',o.id,'actual_revenue',false);
  END IF;
  IF o.state<>'offered' THEN RAISE EXCEPTION 'offered fulfilment order required'; END IF;
  UPDATE public.fulfilment_orders
     SET state='accepted',updated_at=clock_timestamp(),
         commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) || jsonb_build_object(
           'buyer_acceptance_kind',v_kind,
           'buyer_acceptance_reference',v_ref,
           'buyer_accepted_at',p_accepted_at,
           'buyer_acceptance_recorded_by',v_actor
         )
   WHERE id=o.id;
  INSERT INTO public.commercial_terms_events(review_id,fulfilment_order_id,event_type,actor,payload)
  VALUES(r.id,o.id,'accepted',v_actor,jsonb_build_object(
    'evidence_kind',v_kind,'evidence_reference',v_ref,'accepted_at',p_accepted_at,
    'commercial_terms_sha256',r.commercial_terms_sha256,'actual_revenue',false));
  RETURN jsonb_build_object('decision','accepted','review_id',r.id,
                            'fulfilment_order_id',o.id,'state','accepted','actual_revenue',false);
END;
$$;

CREATE FUNCTION public.get_commercial_terms_review(p_review_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
  SELECT jsonb_build_object(
    'review_id',r.id,'fulfilment_order_id',r.fulfilment_order_id,'status',r.status,
    'price_cents',r.price_cents,'acquisition_cost_cents',r.acquisition_cost_cents,
    'fulfilment_cost_cents',r.fulfilment_cost_cents,'expected_margin_cents',r.expected_margin_cents,
    'terms',r.terms,'commercial_terms_sha256',r.commercial_terms_sha256,
    'proposed_by',r.proposed_by,'proposed_at',r.proposed_at,
    'decided_by',r.decided_by,'decided_at',r.decided_at,'decision_note',r.decision_note,
    'actual_revenue',false)
  FROM public.commercial_terms_reviews r WHERE r.id=p_review_id;
$$;
REVOKE ALL ON FUNCTION public.propose_commercial_terms(uuid,bigint,bigint,bigint,jsonb,text,text)
  FROM PUBLIC, anon, authenticated, empire_commercial_approver;
REVOKE ALL ON FUNCTION public.decide_commercial_terms(uuid,text,text,text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.record_commercial_acceptance(uuid,text,text,timestamptz,text)
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.get_commercial_terms_review(uuid)
  FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.propose_commercial_terms(uuid,bigint,bigint,bigint,jsonb,text,text)
  TO service_role;
GRANT EXECUTE ON FUNCTION public.decide_commercial_terms(uuid,text,text,text)
  TO empire_commercial_approver;
GRANT EXECUTE ON FUNCTION public.record_commercial_acceptance(uuid,text,text,timestamptz,text)
  TO empire_commercial_approver;
GRANT EXECUTE ON FUNCTION public.get_commercial_terms_review(uuid)
  TO service_role, empire_commercial_approver;

COMMIT;
