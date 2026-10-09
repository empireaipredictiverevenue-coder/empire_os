-- V2C runtime causal lineage continuity. HELD: do not apply without approval.
-- Canonical function upgrades and lineage integrity trigger; no new table/role or RLS/authority changes.
-- Python governed producer resolves canonical persisted work; SQL does not authenticate filesystem records.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
DO $$ BEGIN
  IF current_database()<>'empiredb' THEN RAISE EXCEPTION 'EmpireDB required'; END IF;
  IF to_regprocedure('public.get_verified_actual_cost_evidence(uuid)') IS NULL THEN
    RAISE EXCEPTION 'existing actual-cost recognition hardening required';
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.validate_commercial_causal_lineage(p jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path='' AS $$
DECLARE k text; v text; eligible boolean;
BEGIN
  IF p IS NULL OR p='null'::jsonb THEN RETURN NULL; END IF;
  IF jsonb_typeof(p)<>'object' OR (SELECT count(*) FROM jsonb_object_keys(p))<>15
     OR p->>'schema_version' IS DISTINCT FROM 'empire.commercial_causal_lineage.v1'
     OR p->>'execution_authority' IS DISTINCT FROM 'none' THEN
    RAISE EXCEPTION 'malformed causal lineage or authority';
  END IF;
  FOREACH k IN ARRAY ARRAY['tenant_id','opportunity_key','opportunity_id','prediction_ref',
    'decision_ref','execution_ref','selection_authority_ref','source_ref','state_ref','task_key'] LOOP
    IF NOT p ? k OR jsonb_typeof(p->k) NOT IN ('null','string')
       OR (jsonb_typeof(p->k)='string' AND (trim(p->>k)='' OR trim(p->>k)<>p->>k)) THEN
      RAISE EXCEPTION 'invalid causal lineage reference: %',k;
    END IF;
  END LOOP;
  FOREACH k IN ARRAY ARRAY['execution_performed','causal_eligible','shadow_only'] LOOP
    IF jsonb_typeof(p->k) IS DISTINCT FROM 'boolean' THEN
      RAISE EXCEPTION 'explicit causal lineage truth flags required';
    END IF;
  END LOOP;
  IF (p->>'shadow_only')::boolean AND
       (p->>'selection_authority_ref' IS NOT NULL OR (p->>'execution_performed')::boolean) THEN
    RAISE EXCEPTION 'shadow lineage cannot claim execution or authority';
  END IF;
  IF p->>'decision_ref' IS NOT NULL AND NOT (p->>'shadow_only')::boolean
     AND p->>'selection_authority_ref' IS NULL THEN
    RAISE EXCEPTION 'selection authority evidence required';
  END IF;
  eligible := (p->>'execution_performed')::boolean AND NOT (p->>'shadow_only')::boolean
    AND p->>'decision_ref' IS NOT NULL AND p->>'selection_authority_ref' IS NOT NULL;
  IF ((p->>'execution_ref' IS NOT NULL) IS DISTINCT FROM (p->>'execution_performed')::boolean)
     OR ((p->>'causal_eligible')::boolean IS DISTINCT FROM eligible)
     OR ((p->>'execution_performed')::boolean AND NOT eligible) THEN
    RAISE EXCEPTION 'invalid canonical execution claim';
  END IF;
  IF (p->>'execution_performed')::boolean AND (p->>'task_key' IS NULL
      OR p->>'execution_ref' IS DISTINCT FROM 'department_work:'||(p->>'task_key')) THEN
    RAISE EXCEPTION 'canonical department work execution reference required';
  END IF;
  RETURN p;
END;
$$;

CREATE OR REPLACE FUNCTION public.merge_commercial_causal_lineage(p jsonb, lineage jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE SECURITY INVOKER SET search_path='' AS $$
DECLARE k text; checked jsonb;
BEGIN
  IF jsonb_typeof(COALESCE(p,'{}'::jsonb))<>'object' THEN
    RAISE EXCEPTION 'commercial evidence object required';
  END IF;
  checked := public.validate_commercial_causal_lineage(lineage);
  IF checked IS NULL THEN
    IF p ? 'causal_lineage' OR p ?| ARRAY['prediction_ref','decision_ref','execution_ref'] THEN
      RAISE EXCEPTION 'caller lineage lacks canonical order provenance';
    END IF;
    RETURN COALESCE(p,'{}'::jsonb);
  END IF;
  IF p ? 'causal_lineage' AND p->'causal_lineage' IS DISTINCT FROM checked THEN
    RAISE EXCEPTION 'contradictory commercial causal lineage';
  END IF;
  FOR k IN SELECT jsonb_object_keys(checked) LOOP
    IF k<>'schema_version' AND p ? k AND p->k IS DISTINCT FROM checked->k THEN
      RAISE EXCEPTION 'contradictory causal field: %',k;
    END IF;
  END LOOP;
  RETURN COALESCE(p,'{}'::jsonb)||jsonb_build_object('causal_lineage',checked);
END;
$$;

CREATE OR REPLACE FUNCTION public.guard_order_causal_lineage()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
BEGIN
  IF TG_OP='UPDATE' AND OLD.commercial_payload ? 'causal_lineage'
     AND (OLD.commercial_payload->'causal_lineage' IS DISTINCT FROM NEW.commercial_payload->'causal_lineage'
          OR OLD.opportunity_id IS DISTINCT FROM NEW.opportunity_id
          OR OLD.buyer_id IS DISTINCT FROM NEW.buyer_id) THEN
    RAISE EXCEPTION 'persisted order causal lineage is immutable';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS guard_order_causal_lineage ON public.fulfilment_orders;
CREATE TRIGGER guard_order_causal_lineage BEFORE UPDATE ON public.fulfilment_orders
FOR EACH ROW EXECUTE FUNCTION public.guard_order_causal_lineage();
CREATE OR REPLACE FUNCTION public.get_closer_reply_context(
    p_case_id uuid,
    p_reply_id uuid
) RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  root_metadata jsonb;
  lineage_key text;
BEGIN
  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;

  SELECT * INTO r FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=r.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply intent not found'; END IF;

  SELECT root.metadata INTO root_metadata FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id;
  FOREACH lineage_key IN ARRAY ARRAY['opportunity_key','department_work_id','causal_lineage'] LOOP
    IF i.metadata ? lineage_key AND root_metadata ? lineage_key
       AND i.metadata->lineage_key IS DISTINCT FROM root_metadata->lineage_key THEN
      RAISE EXCEPTION 'reply provenance contradicts original intent';
    END IF;
  END LOOP;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  RETURN jsonb_build_object(
    'case_id',c.id,
    'case_state',c.state,
    'reply_id',r.id,
    'classification',r.classification,
    'confidence',r.confidence,
    'received_at',r.received_at,
    'reply_subject',r.subject,
    'reply_body_text',r.body_text,
    'from_contact',r.from_contact,
    'root_intent_id',c.outbound_intent_id,
    'source_intent_id',i.id,
    'root_subject',COALESCE(
      (SELECT root.subject FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id),
      i.subject
    ),
    'offer_key',i.offer_key,
    'prospect_id',c.prospect_id,
    'entity_id',c.entity_id,
    'buyer_id',c.buyer_id,
    'opportunity_id',c.opportunity_id,
    'tenant_id',(SELECT b.org_id FROM public.buyers b WHERE b.id=c.buyer_id),
    'opportunity_key',COALESCE(i.metadata->>'opportunity_key',
      (SELECT root.metadata->>'opportunity_key' FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id)),
    'department_work_id',COALESCE(i.metadata->>'department_work_id',
      (SELECT root.metadata->>'department_work_id' FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id)),
    'causal_lineage',COALESCE(i.metadata->'causal_lineage',
      (SELECT root.metadata->'causal_lineage' FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id)),
    'business_name',i.metadata->'candidate_evidence'->>'business_name',
    'niche',i.metadata->'candidate_evidence'->>'niche',
    'metro',i.metadata->'candidate_evidence'->>'metro',
    'contact_name',(
      SELECT br.contact_name
        FROM public.buyer_candidate_reviews br
       WHERE br.id=CASE
         WHEN COALESCE(i.metadata->>'buyer_candidate_review_id','') ~
              '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$'
         THEN (i.metadata->>'buyer_candidate_review_id')::uuid
         ELSE NULL
       END
       LIMIT 1
    ),
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_buyer_capacity_intake(
  p_case_id uuid,
  p_reply_id uuid,
  p_territory text,
  p_daily_cap integer,
  p_delivery_route text,
  p_delivery_reference text,
  p_evidence jsonb,
  p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  r public.outbound_replies%ROWTYPE;
  i public.outbound_intents%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  v_territory text := NULLIF(trim(COALESCE(p_territory,'')),'');
  v_route text := NULLIF(lower(trim(COALESCE(p_delivery_route,''))),'');
  v_ref text := NULLIF(trim(COALESCE(p_delivery_reference,'')),'');
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL THEN RAISE EXCEPTION 'buyer-bound closer case required'; END IF;

  SELECT * INTO r FROM public.outbound_replies WHERE id=p_reply_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply not found'; END IF;

  SELECT * INTO i FROM public.outbound_intents WHERE id=r.intent_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'reply intent not found'; END IF;

  IF r.id IS DISTINCT FROM c.reply_id
     AND COALESCE(i.metadata->>'closer_case_id','') IS DISTINCT FROM c.id::text THEN
    RAISE EXCEPTION 'reply does not belong to closer case';
  END IF;

  IF r.classification NOT IN ('positive','question','objection') THEN
    RAISE EXCEPTION 'commercially engaged inbound reply required';
  END IF;

  IF p_daily_cap IS NOT NULL AND (p_daily_cap < 1 OR p_daily_cap > 10000) THEN
    RAISE EXCEPTION 'daily capacity must be between 1 and 10000';
  END IF;

  IF v_route IS NOT NULL AND v_route NOT IN ('email','webhook','phone','api') THEN
    RAISE EXCEPTION 'unsupported delivery route';
  END IF;

  IF v_territory IS NULL AND p_daily_cap IS NULL AND v_route IS NULL AND v_ref IS NULL THEN
    RAISE EXCEPTION 'at least one explicit capacity field required';
  END IF;

  IF p_evidence ? 'causal_lineage' THEN
    PERFORM public.validate_commercial_causal_lineage(p_evidence->'causal_lineage');
    IF p_evidence->'causal_lineage'->>'tenant_id' IS DISTINCT FROM
         (SELECT b.org_id::text FROM public.buyers b WHERE b.id=c.buyer_id)
       OR p_evidence->'causal_lineage'->>'opportunity_id' IS DISTINCT FROM c.opportunity_id::text
       OR p_evidence->'causal_lineage'->>'opportunity_key' IS DISTINCT FROM COALESCE(i.metadata->>'opportunity_key',
            (SELECT root.metadata->>'opportunity_key' FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id))
       OR p_evidence->'causal_lineage'->>'task_key' IS DISTINCT FROM COALESCE(i.metadata->>'department_work_id',
            (SELECT root.metadata->>'department_work_id' FROM public.outbound_intents root WHERE root.id=c.outbound_intent_id))
       OR p_evidence->'causal_lineage'->>'task_key' IS NULL THEN
      RAISE EXCEPTION 'capacity causal scope or explicit work linkage mismatch';
    END IF;
    IF (p_evidence->'causal_lineage'->>'execution_performed')::boolean
       AND p_evidence->'causal_lineage'->>'execution_ref' IS DISTINCT FROM
           'department_work:'||(p_evidence->'causal_lineage'->>'task_key') THEN
      RAISE EXCEPTION 'capacity canonical work execution mismatch';
    END IF;
  END IF;
  PERFORM 1 FROM public.buyer_capacity_intakes WHERE closer_case_id=c.id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM public.buyer_capacity_intakes existing
       WHERE existing.closer_case_id=c.id AND existing.evidence ? 'causal_lineage'
         AND p_evidence ? 'causal_lineage'
         AND existing.evidence->'causal_lineage' IS DISTINCT FROM p_evidence->'causal_lineage') THEN
    RAISE EXCEPTION 'capacity lineage is immutable';
  END IF;

  INSERT INTO public.buyer_capacity_intakes(
    closer_case_id,buyer_id,source_reply_ids,
    territory,daily_cap,delivery_route,delivery_reference,
    evidence,state
  ) VALUES (
    c.id,c.buyer_id,ARRAY[r.id]::uuid[],
    v_territory,p_daily_cap,v_route,v_ref,
    COALESCE(p_evidence,'{}'::jsonb),
    CASE
      WHEN v_territory IS NOT NULL AND p_daily_cap IS NOT NULL AND v_route IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END
  )
  ON CONFLICT (closer_case_id)
  DO UPDATE SET
    buyer_id=EXCLUDED.buyer_id,
    source_reply_ids=CASE
      WHEN r.id=ANY(public.buyer_capacity_intakes.source_reply_ids)
      THEN public.buyer_capacity_intakes.source_reply_ids
      ELSE array_append(public.buyer_capacity_intakes.source_reply_ids,r.id)
    END,
    territory=COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory),
    daily_cap=COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap),
    delivery_route=COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route),
    delivery_reference=COALESCE(EXCLUDED.delivery_reference,public.buyer_capacity_intakes.delivery_reference),
    evidence=public.buyer_capacity_intakes.evidence
      || COALESCE(EXCLUDED.evidence,'{}'::jsonb)
      || jsonb_build_object('latest_reply_id',r.id,'latest_actor',v_actor),
    state=CASE
      WHEN COALESCE(EXCLUDED.territory,public.buyer_capacity_intakes.territory) IS NOT NULL
       AND COALESCE(EXCLUDED.daily_cap,public.buyer_capacity_intakes.daily_cap) IS NOT NULL
       AND COALESCE(EXCLUDED.delivery_route,public.buyer_capacity_intakes.delivery_route) IS NOT NULL
      THEN 'complete'
      ELSE 'partial'
    END,
    updated_at=clock_timestamp()
  RETURNING * INTO x;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'buyer_capacity_intake_updated',
    v_actor,
    jsonb_build_object(
      'capacity_intake_id',x.id,
      'reply_id',r.id,
      'state',x.state,
      'territory_present',x.territory IS NOT NULL,
      'daily_cap_present',x.daily_cap IS NOT NULL,
      'delivery_route_present',x.delivery_route IS NOT NULL,
      'buyer_stated_only',true,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','recorded',
    'capacity_intake_id',x.id,
    'case_id',c.id,
    'buyer_id',c.buyer_id,
    'state',x.state,
    'territory',x.territory,
    'daily_cap',x.daily_cap,
    'delivery_route',x.delivery_route,
    'delivery_reference',x.delivery_reference,
    'buyer_stated_only',true,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.prepare_fulfilment_order_from_capacity(
  p_case_id uuid,
  p_actor text DEFAULT 'empire_closer_planner'
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $$
DECLARE
  c public.closer_cases%ROWTYPE;
  x public.buyer_capacity_intakes%ROWTYPE;
  o public.fulfilment_orders%ROWTYPE;
  lineage jsonb;
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF v_actor='' THEN RAISE EXCEPTION 'actor required'; END IF;

  SELECT * INTO c FROM public.closer_cases WHERE id=p_case_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'closer case not found'; END IF;
  IF c.state IN ('won','lost','paused') THEN RAISE EXCEPTION 'active closer case required'; END IF;
  IF c.buyer_id IS NULL OR c.prospect_id IS NULL THEN
    RAISE EXCEPTION 'buyer and prospect binding required';
  END IF;

  SELECT * INTO x FROM public.buyer_capacity_intakes WHERE closer_case_id=c.id FOR UPDATE;
  lineage := public.validate_commercial_causal_lineage(x.evidence->'causal_lineage');
  IF lineage IS NOT NULL AND (lineage->>'tenant_id' IS DISTINCT FROM
       (SELECT b.org_id::text FROM public.buyers b WHERE b.id=c.buyer_id)
       OR lineage->>'opportunity_id' IS DISTINCT FROM c.opportunity_id::text) THEN
    RAISE EXCEPTION 'order causal scope mismatch';
  END IF;

  IF c.fulfilment_order_id IS NOT NULL THEN
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=c.fulfilment_order_id;
    IF FOUND THEN
      IF o.opportunity_id IS DISTINCT FROM c.opportunity_id OR o.buyer_id IS DISTINCT FROM c.buyer_id
         OR o.commercial_payload->'causal_lineage' IS DISTINCT FROM lineage THEN
        RAISE EXCEPTION 'existing order causal lineage mismatch';
      END IF;
      RETURN jsonb_build_object(
        'decision','existing',
        'fulfilment_order_id',o.id,
        'state',o.state,
        'actual_revenue',false
      );
    END IF;
  END IF;

  SELECT * INTO x
    FROM public.buyer_capacity_intakes
   WHERE closer_case_id=c.id
   FOR UPDATE;
  IF NOT FOUND OR x.state<>'complete' THEN
    RAISE EXCEPTION 'complete buyer-stated capacity intake required';
  END IF;

  INSERT INTO public.fulfilment_orders(
    opportunity_id,
    prospect_id,
    entity_id,
    buyer_id,
    state,
    quantity,
    price_cents,
    acquisition_cost_cents,
    fulfilment_cost_cents,
    expected_margin_cents,
    delivery_payload,
    commercial_payload
  ) VALUES (
    c.opportunity_id,
    c.prospect_id,
    c.entity_id,
    c.buyer_id,
    'qualified',
    1,
    0,
    0,
    0,
    0,
    jsonb_build_object(
      'territory',x.territory,
      'daily_cap',x.daily_cap,
      'delivery_route',x.delivery_route,
      'delivery_reference',x.delivery_reference,
      'capacity_source','buyer_stated'
    ),
    jsonb_build_object(
      'buyer_capacity_intake_id',x.id,
      'capacity_evidence_state','buyer_stated_unverified',
      'binding_commercial_terms',false,
      'actual_revenue',false
    ) || CASE WHEN lineage IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('causal_lineage',lineage) END
  )
  RETURNING * INTO o;

  UPDATE public.closer_cases
     SET fulfilment_order_id=o.id,
         updated_at=clock_timestamp()
   WHERE id=c.id;

  INSERT INTO public.closer_events(case_id,event_type,actor,payload)
  VALUES(
    c.id,
    'fulfilment_order_prepared',
    v_actor,
    jsonb_build_object(
      'fulfilment_order_id',o.id,
      'order_state',o.state,
      'buyer_capacity_intake_id',x.id,
      'binding_commercial_terms',false,
      'actual_revenue',false
    )
  );

  RETURN jsonb_build_object(
    'decision','prepared',
    'fulfilment_order_id',o.id,
    'state',o.state,
    'buyer_capacity_intake_id',x.id,
    'binding_commercial_terms',false,
    'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.record_commercial_outcome(
  p_fulfilment_order_id uuid,
  p_delivery_outcome text,
  p_conversion_outcome text,
  p_buyer_satisfaction numeric,
  p_evidence_kind text,
  p_evidence_reference text,
  p_evidence jsonb,
  p_idempotency_key text,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  x public.commercial_outcomes%ROWTYPE;
  merged_evidence jsonb;
  lineage jsonb;
  v_delivery text := lower(trim(COALESCE(p_delivery_outcome,'')));
  v_conversion text := lower(trim(COALESCE(p_conversion_outcome,'')));
  v_kind text := lower(trim(COALESCE(p_evidence_kind,'')));
  v_ref text := trim(COALESCE(p_evidence_reference,''));
  v_key text := trim(COALESCE(p_idempotency_key,''));
  v_actor text := trim(COALESCE(p_actor,''));
BEGIN
  IF p_fulfilment_order_id IS NULL THEN RAISE EXCEPTION 'fulfilment order required'; END IF;
  IF v_delivery NOT IN ('delivered','confirmed','rejected','failed','refunded','unknown') THEN
    RAISE EXCEPTION 'unsupported delivery outcome';
  END IF;
  IF v_conversion NOT IN ('unknown','qualified','booked','won','lost','no_response') THEN
    RAISE EXCEPTION 'unsupported conversion outcome';
  END IF;
  IF p_buyer_satisfaction IS NOT NULL
     AND (p_buyer_satisfaction < 1 OR p_buyer_satisfaction > 5) THEN
    RAISE EXCEPTION 'buyer satisfaction must be 1-5';
  END IF;
  IF v_kind NOT IN (
    'outbound_reply','buyer_feedback','delivery_receipt',
    'crm','provider_event','manual_verified'
  ) THEN RAISE EXCEPTION 'supported outcome evidence required'; END IF;
  IF v_ref='' OR length(v_key)<8 OR length(v_key)>160 OR v_actor='' THEN
    RAISE EXCEPTION 'evidence reference, idempotency key and actor required';
  END IF;
  IF jsonb_typeof(COALESCE(p_evidence,'{}'::jsonb)) <> 'object' THEN
    RAISE EXCEPTION 'outcome evidence object required';
  END IF;

  SELECT * INTO o FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  IF o.state NOT IN (
    'delivered','confirmed','invoiced','paid','settled','outcome_captured'
  ) THEN RAISE EXCEPTION 'post-delivery fulfilment order required'; END IF;

  lineage := public.validate_commercial_causal_lineage(o.commercial_payload->'causal_lineage');
  IF lineage IS NOT NULL AND lineage->>'opportunity_id' IS DISTINCT FROM o.opportunity_id::text THEN
    RAISE EXCEPTION 'outcome order opportunity mismatch';
  END IF;
  merged_evidence := public.merge_commercial_causal_lineage(p_evidence,lineage);
  SELECT * INTO x FROM public.commercial_outcomes WHERE idempotency_key=v_key;
  IF FOUND THEN
    IF x.fulfilment_order_id IS DISTINCT FROM o.id
       OR x.delivery_outcome IS DISTINCT FROM v_delivery
       OR x.conversion_outcome IS DISTINCT FROM v_conversion
       OR x.evidence_kind IS DISTINCT FROM v_kind
       OR x.evidence_reference IS DISTINCT FROM v_ref
       OR x.evidence IS DISTINCT FROM merged_evidence
       OR x.buyer_satisfaction IS DISTINCT FROM p_buyer_satisfaction THEN
      RAISE EXCEPTION 'idempotency key belongs to different outcome';
    END IF;
    RETURN jsonb_build_object(
      'decision','existing_outcome','outcome_id',x.id,
      'fulfilment_order_id',o.id,'actual_revenue',false
    );
  END IF;

  INSERT INTO public.commercial_outcomes(
    fulfilment_order_id,delivery_outcome,conversion_outcome,buyer_satisfaction,
    evidence_kind,evidence_reference,evidence,idempotency_key,actor
  ) VALUES (
    o.id,v_delivery,v_conversion,p_buyer_satisfaction,v_kind,v_ref,
    merged_evidence,v_key,v_actor
  ) RETURNING * INTO x;

  UPDATE public.fulfilment_orders
     SET outcome_at=COALESCE(outcome_at,x.recorded_at),
         state=CASE WHEN state='settled' THEN 'outcome_captured' ELSE state END,
         updated_at=clock_timestamp()
   WHERE id=o.id;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'outcome_recorded',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'outcome_feedback',v_actor,0,0,0,
    jsonb_build_object(
      'outcome_id',x.id,'delivery_outcome',x.delivery_outcome,
      'conversion_outcome',x.conversion_outcome,
      'buyer_satisfaction',x.buyer_satisfaction,
      'evidence_kind',x.evidence_kind,'evidence_reference',x.evidence_reference,
      'actual_revenue',false,
      'outcome_ref','canonical:commercial_outcomes:'||x.id::text,
      'evidence',x.evidence
    ) || CASE WHEN lineage IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('causal_lineage',lineage) END,
    x.recorded_at,'outcome:'||x.id::text
  );

  RETURN jsonb_build_object(
    'decision','recorded_outcome','outcome_id',x.id,
    'fulfilment_order_id',o.id,'actual_revenue',false
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.recognize_bsc_revenue(
  p_fulfilment_order_id uuid,
  p_actor text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  o public.fulfilment_orders%ROWTYPE;
  r public.bsc_payment_requests%ROWTYPE;
  d public.bsc_payment_evidence%ROWTYPE;
  a public.bsc_escrow_agreements%ROWTYPE;
  e public.bsc_escrow_evidence%ROWTYPE;
  existing public.commercial_events%ROWTYPE;
  v_actor text := trim(COALESCE(p_actor,''));
  v_source text;
  v_evidence_id uuid;
  v_tx text;
  v_paid_at timestamptz;
  v_cost bigint;
  v_margin bigint;
  v_key text;
  lineage jsonb;
  v_actual_cost jsonb;
  v_acquisition_actual bigint;
  v_fulfilment_actual bigint;
BEGIN
  IF p_fulfilment_order_id IS NULL OR v_actor='' THEN
    RAISE EXCEPTION 'fulfilment order and actor required';
  END IF;

  v_key := 'revenue:'||p_fulfilment_order_id::text||':v1';

  SELECT * INTO existing
    FROM public.commercial_events
   WHERE idempotency_key=v_key;
  IF FOUND THEN
    SELECT * INTO o FROM public.fulfilment_orders WHERE id=p_fulfilment_order_id;
    IF existing.event_type<>'revenue_recognized' OR existing.payload->>'actual_revenue' IS DISTINCT FROM 'true'
       OR existing.fulfilment_order_id IS DISTINCT FROM o.id
       OR existing.payload->'causal_lineage' IS DISTINCT FROM o.commercial_payload->'causal_lineage' THEN
      RAISE EXCEPTION 'existing recognized revenue lineage mismatch';
    END IF;
    RETURN jsonb_build_object(
      'decision','existing_revenue',
      'fulfilment_order_id',existing.fulfilment_order_id,
      'amount_cents',existing.amount_cents,
      'cost_cents',existing.cost_cents,
      'margin_cents',existing.margin_cents,
      'actual_revenue',true
    );
  END IF;

  SELECT * INTO o
    FROM public.fulfilment_orders
   WHERE id=p_fulfilment_order_id
   FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'fulfilment order not found'; END IF;
  lineage := public.validate_commercial_causal_lineage(o.commercial_payload->'causal_lineage');
  IF lineage IS NOT NULL AND lineage->>'opportunity_id' IS DISTINCT FROM o.opportunity_id::text THEN
    RAISE EXCEPTION 'recognized order opportunity lineage mismatch';
  END IF;
  IF o.buyer_id IS NULL OR o.price_cents<=0 THEN
    RAISE EXCEPTION 'priced buyer fulfilment order required';
  END IF;
  IF lower(COALESCE(o.commercial_payload->>'commercial_terms_sha256',''))
     !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'approved commercial terms required';
  END IF;

  SELECT rr.* INTO r
    FROM public.bsc_payment_requests rr
    JOIN public.bsc_payment_evidence dd ON dd.request_id=rr.id
   WHERE rr.fulfilment_order_id=o.id
     AND rr.settlement_mode='direct'
     AND rr.status='approved'
     AND rr.approved_at IS NOT NULL
     AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
   ORDER BY dd.verified_at DESC
   LIMIT 1;

  IF FOUND THEN
    SELECT * INTO d
      FROM public.bsc_payment_evidence
     WHERE request_id=r.id
     ORDER BY verified_at DESC
     LIMIT 1;
    v_source := 'direct_payment';
    v_evidence_id := d.id;
    v_tx := d.transaction_hash;
    v_paid_at := d.verified_at;
  ELSE
    SELECT rr.* INTO r
      FROM public.bsc_payment_requests rr
      JOIN public.bsc_escrow_agreements aa ON aa.request_id=rr.id
      JOIN public.bsc_escrow_evidence ee
        ON ee.agreement_id=aa.id AND ee.action='released'
     WHERE rr.fulfilment_order_id=o.id
       AND rr.settlement_mode='escrow'
       AND rr.status='approved'
       AND rr.approved_at IS NOT NULL
       AND NULLIF(trim(COALESCE(rr.approved_by,'')),'') IS NOT NULL
       AND aa.status='released'
     ORDER BY ee.verified_at DESC
     LIMIT 1;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'no revenue-eligible verified BSC settlement evidence';
    END IF;

    SELECT * INTO a
      FROM public.bsc_escrow_agreements
     WHERE request_id=r.id;
    SELECT * INTO e
      FROM public.bsc_escrow_evidence
     WHERE agreement_id=a.id AND action='released'
     ORDER BY verified_at DESC
     LIMIT 1;

    v_source := 'escrow_release';
    v_evidence_id := e.id;
    v_tx := e.transaction_hash;
    v_paid_at := e.verified_at;
  END IF;

  IF r.commercial_terms_sha256 IS DISTINCT FROM
     lower(o.commercial_payload->>'commercial_terms_sha256') THEN
    RAISE EXCEPTION 'payment evidence commercial terms mismatch';
  END IF;
  IF r.amount_usdt*100 IS DISTINCT FROM o.price_cents::numeric THEN
    RAISE EXCEPTION 'settlement amount does not equal approved USD price';
  END IF;

  SELECT public.get_verified_actual_cost_evidence(o.id)
    INTO v_actual_cost;

  IF COALESCE((v_actual_cost->>'actual_cost_ready')::boolean,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'verified order-bound actual acquisition and fulfilment cost evidence required';
  END IF;

  v_acquisition_actual :=
    (v_actual_cost->'acquisition_cost'->>'amount_cents')::bigint;
  v_fulfilment_actual :=
    (v_actual_cost->'fulfilment_cost'->>'amount_cents')::bigint;
  v_cost := v_acquisition_actual + v_fulfilment_actual;
  v_margin := o.price_cents-v_cost;
  IF v_cost<0 OR v_margin<=0 THEN
    RAISE EXCEPTION 'positive realized margin required';
  END IF;

  INSERT INTO public.commercial_events(
    event_type,opportunity_id,fulfilment_order_id,prospect_id,entity_id,buyer_id,
    product_id,channel,actor,amount_cents,cost_cents,margin_cents,payload,
    occurred_at,idempotency_key
  ) VALUES (
    'revenue_recognized',o.opportunity_id,o.id,o.prospect_id,o.entity_id,o.buyer_id,
    o.product_id,'bsc_usdt',v_actor,o.price_cents,v_cost,v_margin,
    jsonb_build_object(
      'settlement_source',v_source,
      'payment_request_id',r.id,
      'evidence_id',v_evidence_id,
      'transaction_hash',v_tx,
      'commercial_terms_sha256',r.commercial_terms_sha256,
      'settlement_asset','USDT','settlement_chain','BSC',
      'actual_cost_evidence',v_actual_cost,
      'actual_cost_evidence_verified',true,
      'actual_revenue',true
    ) || CASE WHEN lineage IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('causal_lineage',lineage) END,
    v_paid_at,v_key
  );

  UPDATE public.fulfilment_orders
     SET state=CASE
           WHEN EXISTS(
             SELECT 1 FROM public.commercial_outcomes co
              WHERE co.fulfilment_order_id=o.id
           ) THEN 'outcome_captured'
           ELSE 'settled'
         END,
         actual_margin_cents=v_margin,
         paid_at=COALESCE(paid_at,v_paid_at),
         settled_at=COALESCE(settled_at,v_paid_at),
         commercial_payload=COALESCE(commercial_payload,'{}'::jsonb) ||
           jsonb_build_object(
             'recognized_revenue_cents',o.price_cents,
             'recognized_revenue_source',v_source,
             'recognized_revenue_evidence_id',v_evidence_id,
             'recognized_revenue_transaction_hash',v_tx,
             'recognized_revenue_at',v_paid_at,
             'actual_acquisition_cost_cents',v_acquisition_actual,
             'actual_fulfilment_cost_cents',v_fulfilment_actual,
             'actual_cost_evidence',v_actual_cost
           ),
         updated_at=clock_timestamp()
   WHERE id=o.id;

  RETURN jsonb_build_object(
    'decision','revenue_recognized',
    'fulfilment_order_id',o.id,
    'amount_cents',o.price_cents,
    'cost_cents',v_cost,
    'margin_cents',v_margin,
    'settlement_source',v_source,
    'evidence_id',v_evidence_id,
    'actual_revenue',true
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_commercial_outcome_feedback(
  p_limit integer DEFAULT 100
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path='' AS $$
DECLARE
  result jsonb;
BEGIN
  IF p_limit IS NULL OR p_limit<1 OR p_limit>1000 THEN
    RAISE EXCEPTION 'feedback limit must be 1-1000';
  END IF;

  SELECT COALESCE(jsonb_agg(row_data ORDER BY updated_at DESC), '[]'::jsonb)
  INTO result
  FROM (
    SELECT
      o.updated_at,
      jsonb_build_object(
        'id',co.id,
        'outcome_ref',CASE WHEN co.id IS NULL THEN NULL ELSE 'canonical:commercial_outcomes:'||co.id::text END,
        'evidence',co.evidence,
        'evidence_kind',co.evidence_kind,'evidence_reference',co.evidence_reference,
        'recorded_at',co.recorded_at,
        'tenant_id',o.commercial_payload->'causal_lineage'->>'tenant_id',
        'causal_lineage',o.commercial_payload->'causal_lineage',
        'fulfilment_order',to_jsonb(o),
        'revenue_event',to_jsonb(ce),
        'verified',co.evidence->'verified',
        'synthetic',co.evidence->'synthetic','forecast_derived',co.evidence->'forecast_derived',
        'fulfilment_order_id',o.id,
        'opportunity_id',o.opportunity_id,
        'prospect_id',o.prospect_id,
        'entity_id',o.entity_id,
        'buyer_id',o.buyer_id,
        'product_id',o.product_id,
        'state',o.state,
        'price_cents',o.price_cents,
        'acquisition_cost_cents',o.acquisition_cost_cents,
        'fulfilment_cost_cents',o.fulfilment_cost_cents,
        'actual_margin_cents',o.actual_margin_cents,
        'delivery_outcome',co.delivery_outcome,
        'conversion_outcome',co.conversion_outcome,
        'buyer_satisfaction',co.buyer_satisfaction,
        'outcome_recorded_at',co.recorded_at,
        'actual_revenue',ce.id IS NOT NULL,
        'actual_revenue_cents',COALESCE(ce.amount_cents,0),
        'actual_cost_cents',COALESCE(ce.cost_cents,0),
        'gross_profit_cents',COALESCE(ce.margin_cents,0),
        'revenue_recognized_at',ce.occurred_at,
        'previous_purchase',(ce.id IS NOT NULL),
        'booked',(co.conversion_outcome IN ('booked','won')),
        'converted',(co.conversion_outcome='won')
      ) AS row_data
    FROM public.fulfilment_orders o
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_outcomes x
       WHERE x.fulfilment_order_id=o.id
       ORDER BY x.recorded_at DESC,x.id DESC
       LIMIT 1
    ) co ON true
    LEFT JOIN LATERAL (
      SELECT x.*
        FROM public.commercial_events x
       WHERE x.idempotency_key='revenue:'||o.id::text||':v1'
       LIMIT 1
    ) ce ON true
    WHERE co.id IS NOT NULL OR ce.id IS NOT NULL
    ORDER BY o.updated_at DESC
    LIMIT p_limit
  ) q;

  RETURN result;
END;
$$;
-- Existing function signatures retain their existing capability grants.
-- New helpers are pure validators only, not business capabilities.
REVOKE ALL ON FUNCTION public.validate_commercial_causal_lineage(jsonb),
  public.merge_commercial_causal_lineage(jsonb,jsonb),
  public.guard_order_causal_lineage() FROM PUBLIC, empiredb_app;
GRANT EXECUTE ON FUNCTION public.validate_commercial_causal_lineage(jsonb),
  public.merge_commercial_causal_lineage(jsonb,jsonb)
  TO empire_closer_planner, empire_outcome_recorder, empire_revenue_recognizer;
COMMIT;
