-- Phase 3 bounded automation for buyer-stated price evidence.
BEGIN;

CREATE OR REPLACE FUNCTION public.list_auto_verifiable_commercial_evidence(
  p_limit integer DEFAULT 25
) RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=''
AS $$
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'evidence_id',e.id,
        'buyer_id',e.buyer_id,
        'closer_case_id',e.closer_case_id,
        'source_reference',e.source_reference,
        'observed_at',e.observed_at
      )
      ORDER BY e.created_at,e.id
    ),
    '[]'::jsonb
  )
  FROM (
    SELECT *
    FROM public.commercial_evidence_registry
    WHERE status='pending'
      AND evidence_kind='price'
      AND source_type='buyer_stated'
    ORDER BY created_at,id
    LIMIT LEAST(GREATEST(COALESCE(p_limit,25),1),100)
  ) e;
$$;

CREATE OR REPLACE FUNCTION public.auto_verify_buyer_stated_commercial_evidence(
  p_evidence_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=''
AS $$
DECLARE
  x public.commercial_evidence_registry%ROWTYPE;
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  v_reply_id uuid;
  v_phrase text;
  v_match text[];
  v_amount_cents bigint;
  v_unit text;
BEGIN
  SELECT * INTO x
  FROM public.commercial_evidence_registry
  WHERE id=p_evidence_id
  FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'commercial evidence not found';
  END IF;
  IF x.status='verified' THEN
    RETURN jsonb_build_object(
      'decision','existing_verification',
      'evidence_id',x.id,
      'status',x.status,
      'actual_revenue',false
    );
  END IF;
  IF x.status<>'pending'
     OR x.evidence_kind<>'price'
     OR x.source_type<>'buyer_stated' THEN
    RAISE EXCEPTION 'pending buyer-stated price evidence required';
  END IF;
  IF x.valid_until IS NOT NULL
     AND x.valid_until<=clock_timestamp() THEN
    RAISE EXCEPTION 'commercial evidence expired';
  END IF;
  IF x.buyer_id IS NULL OR x.closer_case_id IS NULL THEN
    RAISE EXCEPTION 'buyer and closer case binding required';
  END IF;

  BEGIN
    v_reply_id := (x.evidence->>'reply_id')::uuid;
  EXCEPTION WHEN others THEN
    RAISE EXCEPTION 'valid reply_id evidence required';
  END;
  IF x.source_reference <> 'reply:' || v_reply_id::text || ':price' THEN
    RAISE EXCEPTION 'reply source reference mismatch';
  END IF;

  SELECT * INTO c
  FROM public.closer_cases
  WHERE id=x.closer_case_id;
  IF NOT FOUND OR c.buyer_id IS DISTINCT FROM x.buyer_id THEN
    RAISE EXCEPTION 'closer case buyer binding mismatch';
  END IF;

  SELECT * INTO r
  FROM public.outbound_replies
  WHERE id=v_reply_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'reply evidence not found';
  END IF;

  SELECT * INTO i
  FROM public.outbound_intents
  WHERE id=r.intent_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'reply intent not found';
  END IF;
  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','')
         IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;
  IF abs(extract(epoch FROM (x.observed_at-r.received_at))) > 1 THEN
    RAISE EXCEPTION 'reply observation timestamp mismatch';
  END IF;

  v_phrase := trim(COALESCE(x.evidence->>'price_match',''));
  IF v_phrase='' OR position(lower(v_phrase) in lower(COALESCE(r.body_text,'')))=0 THEN
    RAISE EXCEPTION 'literal price phrase not present in reply';
  END IF;

  v_match := regexp_match(
    lower(v_phrase),
    '.*\$[[:space:]]*([0-9]{1,6}([.][0-9]{1,2})?)[[:space:]]*(/|per[[:space:]]+|a[[:space:]]+)(lead|call)s?[[:space:]]*$',
    'i'
  );
  IF v_match IS NULL THEN
    RAISE EXCEPTION 'buyer-stated price phrase is not deterministic';
  END IF;

  v_amount_cents := round((v_match[1])::numeric * 100)::bigint;
  v_unit := CASE v_match[4]
    WHEN 'lead' THEN 'per_lead'
    WHEN 'call' THEN 'per_call'
    ELSE NULL
  END;
  IF v_amount_cents IS DISTINCT FROM x.amount_cents
     OR v_unit IS DISTINCT FROM x.unit
     OR upper(x.currency)<>'USD' THEN
    RAISE EXCEPTION 'buyer-stated price amount or unit mismatch';
  END IF;

  RETURN public.verify_commercial_evidence(
    x.id,
    'commercial-evidence-standing-authority'
  );
END;
$$;
REVOKE ALL ON FUNCTION
  public.verify_commercial_evidence(uuid,text)
FROM service_role;

REVOKE ALL ON FUNCTION
  public.reject_commercial_evidence(uuid,text,text)
FROM service_role;

REVOKE ALL ON FUNCTION
  public.list_auto_verifiable_commercial_evidence(integer)
FROM PUBLIC,anon,authenticated;

REVOKE ALL ON FUNCTION
  public.auto_verify_buyer_stated_commercial_evidence(uuid)
FROM PUBLIC,anon,authenticated;

GRANT EXECUTE ON FUNCTION
  public.list_auto_verifiable_commercial_evidence(integer)
TO service_role;

GRANT EXECUTE ON FUNCTION
  public.auto_verify_buyer_stated_commercial_evidence(uuid)
TO service_role;

COMMIT;
