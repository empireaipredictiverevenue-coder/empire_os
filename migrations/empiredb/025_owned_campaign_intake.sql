-- HELD_FOR_FOUNDER_DB_APPROVAL. DO NOT APPLY as part of build preparation.
-- Required: no existing owner accepts anonymous web observations / minimal research
-- enquiries without inventing identity or implying commercial qualification.
-- No dependency on held migration 018. No generic empiredb_app grants.
BEGIN;
DO $$ BEGIN
 IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'empire_owned_campaign_ingest') THEN
  CREATE ROLE empire_owned_campaign_ingest NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
 END IF;
END $$;

CREATE TABLE public.owned_campaign_enquiries (
 receipt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 dedupe_key text NOT NULL UNIQUE CHECK (dedupe_key ~ '^[0-9a-f]{64}$'),
 campaign_id text NOT NULL CHECK (campaign_id ~ '^campaign_[0-9a-f]{24}$'),
 asset_id text NOT NULL CHECK (asset_id = campaign_id || ':landing'),
 reply_email text NOT NULL CHECK (length(reply_email) BETWEEN 3 AND 254 AND reply_email = lower(btrim(reply_email)) AND reply_email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
 research_question text NOT NULL CHECK (length(btrim(research_question)) BETWEEN 10 AND 4000),
 company text CHECK (length(company) <= 200),
 role text CHECK (length(role) <= 100),
 marketing_consent boolean NOT NULL DEFAULT false CHECK (NOT marketing_consent),
 outbound_authorized boolean NOT NULL DEFAULT false CHECK (NOT outbound_authorized),
 automatic_followup boolean NOT NULL DEFAULT false CHECK (NOT automatic_followup),
 evidence_class text NOT NULL DEFAULT 'first_party_inbound_enquiry' CHECK (evidence_class = 'first_party_inbound_enquiry'),
 received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE public.owned_campaign_events (
 event_id uuid PRIMARY KEY,
 campaign_id text NOT NULL CHECK (campaign_id ~ '^campaign_[0-9a-f]{24}$'),
 asset_id text NOT NULL CHECK (asset_id = campaign_id || ':landing'),
 event_type text NOT NULL CHECK (event_type IN ('campaign_page_view','campaign_cta_click','campaign_enquiry_started','campaign_enquiry_submitted')),
 source text NOT NULL CHECK (source = 'owned_site'),
 channel text NOT NULL CHECK (channel = 'organic'),
 occurred_at timestamptz NOT NULL,
 session_id uuid,
 enquiry_receipt uuid REFERENCES public.owned_campaign_enquiries(receipt_id),
 evidence_class text NOT NULL DEFAULT 'browser_observation' CHECK (evidence_class IN ('browser_observation','server_received_enquiry')),
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 CHECK ((enquiry_receipt IS NULL AND evidence_class = 'browser_observation') OR
        (enquiry_receipt IS NOT NULL AND evidence_class = 'server_received_enquiry' AND event_type = 'campaign_enquiry_submitted'))
);
CREATE INDEX owned_campaign_events_asset_time ON public.owned_campaign_events(campaign_id,asset_id,occurred_at);
CREATE INDEX owned_campaign_enquiries_asset_time ON public.owned_campaign_enquiries(campaign_id,asset_id,received_at);
ALTER TABLE public.owned_campaign_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.owned_campaign_enquiries ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.owned_campaign_events, public.owned_campaign_enquiries FROM PUBLIC, empiredb_app, empire_owned_campaign_ingest;

CREATE FUNCTION public.record_owned_campaign_event(p jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE r public.owned_campaign_events; existing public.owned_campaign_events;
BEGIN
 IF jsonb_typeof(p) <> 'object' OR NOT (p ?& ARRAY['event_id','event_type','campaign_id','asset_id','source','channel','occurred_at'])
 OR EXISTS (SELECT FROM jsonb_object_keys(p) k WHERE k <> ALL(ARRAY['event_id','event_type','campaign_id','asset_id','source','channel','occurred_at','session_id'])) THEN
  RAISE EXCEPTION 'invalid event contract';
 END IF;
 r.event_id := (p->>'event_id')::uuid; r.campaign_id := p->>'campaign_id'; r.asset_id := p->>'asset_id';
 r.event_type := p->>'event_type'; r.source := p->>'source'; r.channel := p->>'channel';
 r.occurred_at := (p->>'occurred_at')::timestamptz; r.session_id := (p->>'session_id')::uuid;
 INSERT INTO public.owned_campaign_events(event_id,campaign_id,asset_id,event_type,source,channel,occurred_at,session_id)
 VALUES(r.event_id,r.campaign_id,r.asset_id,r.event_type,r.source,r.channel,r.occurred_at,r.session_id)
 ON CONFLICT (event_id) DO NOTHING;
 SELECT * INTO STRICT existing FROM public.owned_campaign_events WHERE event_id = r.event_id;
 IF ROW(existing.campaign_id,existing.asset_id,existing.event_type,existing.source,existing.channel,existing.occurred_at,existing.session_id,existing.enquiry_receipt)
 IS DISTINCT FROM ROW(r.campaign_id,r.asset_id,r.event_type,r.source,r.channel,r.occurred_at,r.session_id,NULL::uuid) THEN
  RAISE EXCEPTION 'conflicting event replay';
 END IF;
 RETURN existing.event_id;
END $$;

CREATE FUNCTION public.record_owned_campaign_enquiry(p jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE result uuid; key text;
BEGIN
 IF jsonb_typeof(p) <> 'object' OR NOT (p ?& ARRAY['campaign_id','asset_id','reply_email','research_question'])
 OR EXISTS (SELECT FROM jsonb_object_keys(p) k WHERE k <> ALL(ARRAY['campaign_id','asset_id','reply_email','research_question','company','role'])) THEN
  RAISE EXCEPTION 'invalid enquiry contract';
 END IF;
 key := encode(sha256(convert_to(p::text,'UTF8')),'hex');
 INSERT INTO public.owned_campaign_enquiries(dedupe_key,campaign_id,asset_id,reply_email,research_question,company,role)
 VALUES(key,p->>'campaign_id',p->>'asset_id',p->>'reply_email',p->>'research_question',p->>'company',p->>'role')
 ON CONFLICT (dedupe_key) DO NOTHING RETURNING receipt_id INTO result;
 IF result IS NULL THEN
  SELECT receipt_id INTO STRICT result FROM public.owned_campaign_enquiries WHERE dedupe_key=key;
 ELSE
  INSERT INTO public.owned_campaign_events(event_id,campaign_id,asset_id,event_type,source,channel,occurred_at,enquiry_receipt,evidence_class)
  VALUES(gen_random_uuid(),p->>'campaign_id',p->>'asset_id','campaign_enquiry_submitted','owned_site','organic',clock_timestamp(),result,'server_received_enquiry');
 END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION public.record_owned_campaign_event(jsonb), public.record_owned_campaign_enquiry(jsonb) FROM PUBLIC, empiredb_app;
GRANT USAGE ON SCHEMA public TO empire_owned_campaign_ingest;
GRANT EXECUTE ON FUNCTION public.record_owned_campaign_event(jsonb), public.record_owned_campaign_enquiry(jsonb) TO empire_owned_campaign_ingest;
COMMENT ON TABLE public.owned_campaign_enquiries IS 'First-party research enquiries only. No buyer/demand/consent/outbound/revenue inference. Restricted operator access and retention review required before activation.';
COMMIT;
