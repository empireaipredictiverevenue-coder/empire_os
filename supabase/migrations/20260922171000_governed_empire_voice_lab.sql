-- Governed Voice Lab outbound authority.
-- Additive only: bounded business-phone calling, canonical lifecycle evidence,
-- and Conversation OS transcript capture. No terms/payment/revenue authority.
BEGIN;

ALTER TABLE public.outbound_events
DROP CONSTRAINT IF EXISTS outbound_events_event_type_check;

ALTER TABLE public.outbound_events
ADD CONSTRAINT outbound_events_event_type_check CHECK (event_type IN (
  'proposed','approved','rejected','send_attempt','sent','delivered','failed',
  'reply_received','reply_classified','suppressed','cancelled',
  'delivery_delayed','bounced','complained','opened','clicked',
  'call_ringing','call_answered','call_completed','call_busy',
  'call_unanswered','call_rejected','call_failed'
));

CREATE OR REPLACE FUNCTION public.propose_call_ready_voice_intent(
  p_prospect_id uuid,
  p_recipient text,
  p_idempotency_key text,
  p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  p public.prospects%ROWTYPE;
  v_recipient text := trim(COALESCE(p_recipient,''));
  v_digits text;
  p_digits text;
  result jsonb;
BEGIN
  SELECT * INTO p FROM public.prospects WHERE id=p_prospect_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'canonical prospect required'; END IF;

  v_digits := regexp_replace(v_recipient,'[^0-9]','','g');
  p_digits := regexp_replace(COALESCE(p.phone,''),'[^0-9]','','g');
  IF length(v_digits)<10 OR right(v_digits,10)<>right(p_digits,10) THEN
    RAISE EXCEPTION 'canonical business phone mismatch';
  END IF;
  IF COALESCE(p.buy_signal_score,0)<70 THEN
    RAISE EXCEPTION 'buy signal below voice standing-authority floor';
  END IF;
  IF trim(COALESCE(p.website,''))='' THEN
    RAISE EXCEPTION 'first-party business website required';
  END IF;
  IF lower(COALESCE(p.niche,'')) !~ '(roof|hvac|plumb|solar|contractor|restoration)' THEN
    RAISE EXCEPTION 'prospect niche outside managed-service voice scope';
  END IF;
  IF COALESCE((p_metadata->>'call_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'call-ready evidence required';
  END IF;
  IF COALESCE(p_metadata->>'voice_legal_basis','') NOT IN (
    'prior_express_written_consent',
    'verified_business_landline_b2b'
  ) THEN
    RAISE EXCEPTION 'verified voice legal basis required';
  END IF;
  IF COALESCE(p_metadata->>'voice_legal_basis','')
      ='verified_business_landline_b2b'
     AND COALESCE(p_metadata->>'line_type','')
         NOT IN ('landline','landline_tollfree') THEN
    RAISE EXCEPTION 'verified business landline evidence required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE s.contact_type='phone'
      AND regexp_replace(s.normalized_contact,'[^0-9]','','g')=v_digits
  ) THEN
    RAISE EXCEPTION 'phone suppressed';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_intents i
    WHERE i.channel='voice'
      AND regexp_replace(i.normalized_recipient,'[^0-9]','','g')=v_digits
      AND i.status IN ('sent','delivered','replied','sending')
      AND i.created_at >= clock_timestamp()-interval '7 days'
  ) THEN
    RAISE EXCEPTION 'recent voice attempt already exists';
  END IF;

  result := public.propose_outbound_intent(
    NULL,p.id,NULL,NULL,'voice',v_recipient,NULL,
    'Governed Empire AI business call: identify or reach the decision maker, '
      || 'test relevance, and request permission for follow-up.',
    NULL,'managed_service',trim(p_idempotency_key),
    'voice-standing-authority',
    clock_timestamp()+interval '2 hours',
    COALESCE(p_metadata,'{}'::jsonb) || jsonb_build_object(
      'call_ready',true,
      'buy_signal_score',p.buy_signal_score,
      'business_name',p.business_name,
      'niche',p.niche,
      'metro',p.metro,
      'website',p.website,
      'actual_revenue',false,
      'terms_authority',false,
      'payment_authority',false
    )
  );
  RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.auto_approve_voice_intent(
  p_intent_id uuid,
  p_daily_cap integer DEFAULT 5
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  i public.outbound_intents%ROWTYPE;
  p public.prospects%ROWTYPE;
  approved_today integer;
  result jsonb;
BEGIN
  IF p_daily_cap IS NULL OR p_daily_cap<1 OR p_daily_cap>20 THEN
    RAISE EXCEPTION 'voice daily cap must be 1-20';
  END IF;

  SELECT * INTO i FROM public.outbound_intents
  WHERE id=p_intent_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'voice intent not found'; END IF;
  IF i.status='approved' THEN
    RETURN jsonb_build_object(
      'decision','existing','intent_id',i.id,'status',i.status,
      'actual_revenue',false
    );
  END IF;
  IF i.status<>'pending_approval' OR i.expires_at<=clock_timestamp() THEN
    RAISE EXCEPTION 'fresh pending voice intent required';
  END IF;
  IF i.channel<>'voice' OR i.offer_key<>'managed_service' THEN
    RAISE EXCEPTION 'managed-service voice intent required';
  END IF;
  IF COALESCE((i.metadata->>'call_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'call-ready evidence required';
  END IF;
  IF COALESCE(i.metadata->>'voice_legal_basis','') NOT IN (
    'prior_express_written_consent',
    'verified_business_landline_b2b'
  ) THEN
    RAISE EXCEPTION 'verified voice legal basis required';
  END IF;
  IF COALESCE(i.metadata->>'voice_legal_basis','')
      ='verified_business_landline_b2b'
     AND COALESCE(i.metadata->>'line_type','')
         NOT IN ('landline','landline_tollfree') THEN
    RAISE EXCEPTION 'verified business landline evidence required';
  END IF;
  IF i.prospect_id IS NULL THEN
    RAISE EXCEPTION 'canonical prospect required';
  END IF;

  SELECT * INTO p FROM public.prospects WHERE id=i.prospect_id;
  IF NOT FOUND OR COALESCE(p.buy_signal_score,0)<70 THEN
    RAISE EXCEPTION 'eligible canonical prospect required';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.outbound_suppressions s
    WHERE s.contact_type='phone'
      AND regexp_replace(s.normalized_contact,'[^0-9]','','g')
          =regexp_replace(i.normalized_recipient,'[^0-9]','','g')
  ) THEN
    RAISE EXCEPTION 'phone suppressed';
  END IF;

  SELECT count(*)::integer INTO approved_today
  FROM public.outbound_events e
  JOIN public.outbound_intents x ON x.id=e.intent_id
  WHERE e.event_type='approved'
    AND e.actor='voice-standing-authority'
    AND x.channel='voice'
    AND e.occurred_at>=date_trunc('day',clock_timestamp());

  IF approved_today>=p_daily_cap THEN
    RAISE EXCEPTION 'voice standing-authority daily cap reached';
  END IF;

  result := public.approve_outbound_intent(
    i.id,
    'voice-standing-authority',
    'Approved under bounded call-ready business-phone authority.'
  );
  RETURN result || jsonb_build_object(
    'standing_authority',true,
    'voice_daily_cap',p_daily_cap,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_voice_provider_event(
  p_intent_id uuid,
  p_external_call_id text,
  p_event_type text,
  p_payload jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  i public.outbound_intents%ROWTYPE;
  c public.empire_conversations%ROWTYPE;
  v_type text := lower(trim(COALESCE(p_event_type,'')));
  v_call text := trim(COALESCE(p_external_call_id,''));
BEGIN
  IF v_type NOT IN (
    'call_ringing','call_answered','call_completed','call_busy',
    'call_unanswered','call_rejected','call_failed'
  ) THEN RAISE EXCEPTION 'unsupported voice provider event'; END IF;
  IF v_call='' THEN RAISE EXCEPTION 'external call id required'; END IF;

  SELECT * INTO i FROM public.outbound_intents
  WHERE id=p_intent_id FOR UPDATE;
  IF NOT FOUND OR i.channel<>'voice' THEN
    RAISE EXCEPTION 'canonical voice intent required';
  END IF;

  SELECT * INTO c FROM public.empire_conversations
  WHERE outbound_intent_id=i.id
  ORDER BY opened_at DESC LIMIT 1;

  IF NOT FOUND THEN
    INSERT INTO public.empire_conversations(
      channel,state,prospect_id,entity_id,buyer_id,opportunity_id,
      outbound_intent_id,external_conversation_id,provider
    ) VALUES(
      'voice','open',i.prospect_id,i.entity_id,i.buyer_id,i.opportunity_id,
      i.id,v_call,'vonage'
    ) RETURNING * INTO c;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.outbound_events e
    WHERE e.intent_id=i.id
      AND e.event_type=v_type
      AND e.provider_message_id=v_call
  ) THEN
    RETURN jsonb_build_object(
      'decision','existing','intent_id',i.id,
      'conversation_id',c.id,'event_type',v_type,'actual_revenue',false
    );
  END IF;

  IF v_type='call_answered' AND i.status IN ('sent','failed') THEN
    UPDATE public.outbound_intents
    SET status='delivered',updated_at=clock_timestamp()
    WHERE id=i.id RETURNING * INTO i;
    UPDATE public.empire_conversations
    SET state='engaged',updated_at=clock_timestamp()
    WHERE id=c.id RETURNING * INTO c;
  ELSIF v_type IN (
    'call_busy','call_unanswered','call_rejected','call_failed'
  ) AND i.status IN ('sent','approved') THEN
    UPDATE public.outbound_intents
    SET status='failed',updated_at=clock_timestamp()
    WHERE id=i.id RETURNING * INTO i;
  ELSIF v_type='call_completed' THEN
    UPDATE public.empire_conversations
    SET state='closed',updated_at=clock_timestamp()
    WHERE id=c.id RETURNING * INTO c;
  END IF;

  INSERT INTO public.outbound_events(
    intent_id,event_type,actor,provider_message_id,payload
  ) VALUES(
    i.id,v_type,'vonage_webhook',v_call,COALESCE(p_payload,'{}'::jsonb)
  );

  INSERT INTO public.empire_conversation_events(
    conversation_id,event_type,direction,actor,provider_event_id,
    evidence,occurred_at
  ) VALUES(
    c.id,v_type,'internal','vonage_webhook',
    'vonage:'||v_call||':'||v_type,
    COALESCE(p_payload,'{}'::jsonb) || jsonb_build_object(
      'provider','vonage','external_conversation_id',v_call
    ),
    clock_timestamp()
  )
  ON CONFLICT(conversation_id,provider_event_id) DO NOTHING;

  RETURN jsonb_build_object(
    'decision','recorded','intent_id',i.id,'status',i.status,
    'conversation_id',c.id,'event_type',v_type,'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_voice_turn(
  p_intent_id uuid,
  p_external_call_id text,
  p_turn_index integer,
  p_direction text,
  p_body_text text,
  p_evidence jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  i public.outbound_intents%ROWTYPE;
  c public.empire_conversations%ROWTYPE;
  event_id text;
  event_type text;
BEGIN
  IF p_turn_index<0 OR p_turn_index>10000 THEN
    RAISE EXCEPTION 'invalid turn index';
  END IF;
  IF p_direction NOT IN ('inbound','outbound') THEN
    RAISE EXCEPTION 'voice turn direction required';
  END IF;
  IF trim(COALESCE(p_body_text,''))='' THEN
    RAISE EXCEPTION 'voice turn text required';
  END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=p_intent_id;
  IF NOT FOUND OR i.channel<>'voice' THEN
    RAISE EXCEPTION 'canonical voice intent required';
  END IF;
  SELECT * INTO c FROM public.empire_conversations
  WHERE outbound_intent_id=i.id
  ORDER BY opened_at DESC LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'voice conversation not initialized'; END IF;

  event_type := CASE
    WHEN p_direction='inbound' THEN 'transcript'
    ELSE 'agent_response'
  END;
  event_id := 'voice-turn:'||p_turn_index::text||':'||p_direction;

  INSERT INTO public.empire_conversation_events(
    conversation_id,event_type,direction,actor,body_text,
    provider_event_id,evidence,occurred_at
  ) VALUES(
    c.id,event_type,p_direction,
    CASE WHEN p_direction='inbound' THEN 'buyer' ELSE 'empire_voice_lab' END,
    p_body_text,event_id,
    COALESCE(p_evidence,'{}'::jsonb) || jsonb_build_object(
      'provider','vonage',
      'external_conversation_id',trim(p_external_call_id),
      'speech_vendor',NULL,
      'voice_engine','empire_voice_lab'
    ),
    clock_timestamp()
  )
  ON CONFLICT(conversation_id,provider_event_id) DO NOTHING;

  IF p_direction='inbound'
     AND lower(p_body_text) ~
       '(do not call|don''t call|stop calling|opt out|remove me|take me off)' THEN
    INSERT INTO public.outbound_suppressions(
      normalized_contact,contact_type,reason,source
    ) VALUES(
      i.normalized_recipient,'phone','voice_opt_out','empire_voice_lab'
    )
    ON CONFLICT(normalized_contact) DO NOTHING;

    UPDATE public.outbound_intents
    SET status='suppressed',updated_at=clock_timestamp()
    WHERE id=i.id;

    INSERT INTO public.outbound_events(
      intent_id,event_type,actor,provider_message_id,payload
    ) VALUES(
      i.id,'suppressed','empire_voice_lab',
      trim(p_external_call_id),
      jsonb_build_object(
        'reason','voice_opt_out',
        'turn_index',p_turn_index
      )
    );
  END IF;

  RETURN jsonb_build_object(
    'decision','recorded','conversation_id',c.id,
    'turn_index',p_turn_index,'direction',p_direction,
    'actual_revenue',false
  );
END;
$$;

REVOKE ALL ON FUNCTION public.propose_call_ready_voice_intent(
  uuid,text,text,jsonb
) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.auto_approve_voice_intent(
  uuid,integer
) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.record_voice_provider_event(
  uuid,text,text,jsonb
) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.record_voice_turn(
  uuid,text,integer,text,text,jsonb
) FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION public.propose_call_ready_voice_intent(
  uuid,text,text,jsonb
) TO service_role;
GRANT EXECUTE ON FUNCTION public.auto_approve_voice_intent(
  uuid,integer
) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_voice_provider_event(
  uuid,text,text,jsonb
) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_voice_turn(
  uuid,text,integer,text,text,jsonb
) TO service_role;

COMMENT ON FUNCTION public.auto_approve_voice_intent(uuid,integer) IS
'Bounded standing authority for canonical call-ready business-phone voice outreach; no terms, payment, or revenue authority.';
COMMIT;
