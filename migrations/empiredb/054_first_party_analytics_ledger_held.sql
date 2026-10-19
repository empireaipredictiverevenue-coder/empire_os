-- EmpireDB ANALYTICS054: STAGED ONLY; NEVER apply on ordinary deploy/boot.
-- REQUIRES separate, explicit founder-approved privileged migration.
-- Builds isolated first-party analytics storage with ZERO runtime grants,
-- ZERO route activation, ZERO website tags/cookies, ZERO tracked visitors.
-- Real consent legal authority, erasure and retention MUST be approved
-- independently before any collection; fixture target only for isolated QA.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_analytics_fixture') THEN
   RAISE EXCEPTION 'ANALYTICS054_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator'
     AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
 ) THEN
   RAISE EXCEPTION 'ANALYTICS054_MIGRATOR_OWNER_UNVERIFIED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_analytics_sessions') IS NOT NULL
   OR pg_catalog.to_regclass('public.empire_analytics_consent_decisions') IS NOT NULL
   OR pg_catalog.to_regclass('public.empire_analytics_event_receipts') IS NOT NULL
   OR pg_catalog.to_regprocedure('public.empire_analytics_immutable()') IS NOT NULL
   OR pg_catalog.to_regprocedure('public.empire_analytics_consent_before_insert()') IS NOT NULL
   OR pg_catalog.to_regprocedure('public.empire_analytics_event_before_insert()') IS NOT NULL
 THEN
   RAISE EXCEPTION 'ANALYTICS054_EXISTING_OBJECT_OWNER_REVIEW_REQUIRED';
 END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- SESSION REFERENCE ONLY: digest must be calculated by an approved
-- keyed HMAC authority later. It is not a public token/visitor login.
CREATE TABLE public.empire_analytics_sessions (
 tenant_id uuid NOT NULL,
 property_key text NOT NULL DEFAULT 'empire-ai.co.uk'
   CHECK (property_key='empire-ai.co.uk'),
 session_digest text NOT NULL CHECK (session_digest ~ '^[a-f0-9]{64}$'),
 acquisition_channel text NOT NULL CHECK (
   acquisition_channel IN (
    'direct','organic_search','organic_social','referral','email','unknown'
   )
 ),
 source_evidence_kind text NOT NULL CHECK (
   (acquisition_channel='direct' AND source_evidence_kind='server_observed_direct')
   OR (acquisition_channel IN ('organic_search','organic_social','referral')
       AND source_evidence_kind='server_verified_referral')
   OR (acquisition_channel='email' AND source_evidence_kind='signed_campaign_binding')
   OR (acquisition_channel='unknown' AND source_evidence_kind='server_unknown')
 ),
 policy_revision text NOT NULL CHECK (
   policy_revision ~ '^[a-z][a-z0-9._-]{3,47}$'
 ),
 opened_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id,property_key,session_digest),
 CHECK (expires_at > opened_at),
 CHECK (expires_at <= opened_at + interval '30 minutes'),
 CHECK (opened_at <= created_at + interval '1 minute')
);
COMMENT ON TABLE public.empire_analytics_sessions IS
 'NOT ACTIVATED. Property/tenant scoped HMAC session references only; no IP/cookie/email/user agent and no customer revenue proof.';

-- Append-only proof references: evidence_sha256 is a reference fingerprint,
-- NOT legal consent by itself. Decisions need future trusted server/CMP.
CREATE TABLE public.empire_analytics_consent_decisions (
 tenant_id uuid NOT NULL,
 property_key text NOT NULL DEFAULT 'empire-ai.co.uk'
   CHECK (property_key='empire-ai.co.uk'),
 session_digest text NOT NULL CHECK (session_digest ~ '^[a-f0-9]{64}$'),
 revision integer NOT NULL CHECK (revision BETWEEN 1 AND 1000000),
 purpose text NOT NULL DEFAULT 'website_analytics_measurement'
   CHECK (purpose='website_analytics_measurement'),
 decision text NOT NULL CHECK (decision IN ('granted','denied','revoked')),
 policy_revision text NOT NULL CHECK (
   policy_revision ~ '^[a-z][a-z0-9._-]{3,47}$'
 ),
 evidence_sha256 text NOT NULL CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
 evidence_class text NOT NULL CHECK (
   evidence_class='SERVER_VERIFIED_CMP_DECISION'
 ),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id,property_key,session_digest,revision),
 FOREIGN KEY (tenant_id,property_key,session_digest)
   REFERENCES public.empire_analytics_sessions
   (tenant_id,property_key,session_digest)
);
COMMENT ON TABLE public.empire_analytics_consent_decisions IS
 'APPEND ONLY, no production writer. Revoke terminal per session; consent evidence digest alone does not establish statutory compliance.';

-- Browser attempts remain observations, not leads or purchases.
-- Event replay digest keyed to the tenant AND property, not a buyer ID.
CREATE TABLE public.empire_analytics_event_receipts (
 tenant_id uuid NOT NULL,
 property_key text NOT NULL DEFAULT 'empire-ai.co.uk'
   CHECK (property_key='empire-ai.co.uk'),
 event_digest text NOT NULL CHECK (event_digest ~ '^[a-f0-9]{64}$'),
 session_digest text NOT NULL CHECK (session_digest ~ '^[a-f0-9]{64}$'),
 event_kind text NOT NULL CHECK (
   event_kind IN ('page_view','engagement','cta_click',
                  'form_start','form_submit_attempt')
 ),
 page_key text NOT NULL CHECK (page_key ~ '^[a-z][a-z0-9_]{0,47}$'),
 occurred_at timestamptz NOT NULL,
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY (tenant_id,property_key,event_digest),
 FOREIGN KEY (tenant_id,property_key,session_digest)
   REFERENCES public.empire_analytics_sessions
   (tenant_id,property_key,session_digest),
 CHECK (occurred_at <= received_at + interval '1 minute'),
 CHECK (occurred_at >= received_at - interval '48 hours')
);
COMMENT ON TABLE public.empire_analytics_event_receipts IS
 'NO LIVE INTAKE. Only allowlisted pseudonymous event references, no raw URL, IP, PII, lead or payment data.';

CREATE INDEX empire_analytics_receipts_by_session
 ON public.empire_analytics_event_receipts
 (tenant_id,property_key,session_digest,received_at);

CREATE FUNCTION public.empire_analytics_immutable()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $fn$
BEGIN
 RAISE EXCEPTION 'ANALYTICS054_APPEND_ONLY_MUTATION_DENIED';
END;
$fn$;

CREATE TRIGGER empire_analytics_sessions_immutable
 BEFORE UPDATE OR DELETE ON public.empire_analytics_sessions
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_immutable();
CREATE TRIGGER empire_analytics_decisions_immutable
 BEFORE UPDATE OR DELETE ON public.empire_analytics_consent_decisions
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_immutable();
CREATE TRIGGER empire_analytics_events_immutable
 BEFORE UPDATE OR DELETE ON public.empire_analytics_event_receipts
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_immutable();

-- Serialize consent decision transitions per session to prevent concurrent
-- revision forks and post-revocation re-grants. No raw client consent flag.
CREATE FUNCTION public.empire_analytics_consent_before_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $fn$
DECLARE s public.empire_analytics_sessions%ROWTYPE;
        last_revision integer;
        last_decision text;
BEGIN
 SELECT * INTO s FROM public.empire_analytics_sessions
 WHERE tenant_id=NEW.tenant_id
   AND property_key=NEW.property_key
   AND session_digest=NEW.session_digest
 FOR UPDATE;
 IF NOT FOUND OR s.policy_revision<>NEW.policy_revision
   OR clock_timestamp()<s.opened_at
   OR clock_timestamp()>=s.expires_at
 THEN
   RAISE EXCEPTION 'ANALYTICS054_SESSION_OR_POLICY_UNVERIFIED';
 END IF;
 SELECT revision,decision INTO last_revision,last_decision
 FROM public.empire_analytics_consent_decisions
 WHERE tenant_id=NEW.tenant_id
   AND property_key=NEW.property_key
   AND session_digest=NEW.session_digest
 ORDER BY revision DESC LIMIT 1;
 IF NEW.revision<>coalesce(last_revision,0)+1
   OR last_decision='revoked'
   OR (last_decision='granted' AND NEW.decision='granted')
 THEN
   RAISE EXCEPTION 'ANALYTICS054_INVALID_CONSENT_TRANSITION';
 END IF;
 -- Client-supplied timestamps cannot backdate an apparent grant.
 NEW.recorded_at := clock_timestamp();
 RETURN NEW;
END;
$fn$;

CREATE TRIGGER empire_analytics_consent_sequencer
 BEFORE INSERT ON public.empire_analytics_consent_decisions
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_consent_before_insert();

-- Event acceptance depends on latest server-written consent and received
-- transaction order, not a stale approved browser flag. Parent row lock
-- serializes events against revocation across requests.
CREATE FUNCTION public.empire_analytics_event_before_insert()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=''
AS $fn$
DECLARE s public.empire_analytics_sessions%ROWTYPE;
        current_decision text;
        consent_received_at timestamptz;
BEGIN
 SELECT * INTO s FROM public.empire_analytics_sessions
 WHERE tenant_id=NEW.tenant_id AND property_key=NEW.property_key
   AND session_digest=NEW.session_digest
 FOR UPDATE;
 IF NOT FOUND OR clock_timestamp()<s.opened_at
   OR clock_timestamp()>=s.expires_at
   OR NEW.occurred_at<s.opened_at
   OR NEW.occurred_at>=s.expires_at
 THEN
   RAISE EXCEPTION 'ANALYTICS054_SESSION_EXPIRED_OR_INVALID';
 END IF;
 SELECT decision,recorded_at INTO current_decision,consent_received_at
 FROM public.empire_analytics_consent_decisions
 WHERE tenant_id=NEW.tenant_id
   AND property_key=NEW.property_key
   AND session_digest=NEW.session_digest
 ORDER BY revision DESC LIMIT 1;
 IF current_decision IS DISTINCT FROM 'granted' THEN
   RAISE EXCEPTION 'ANALYTICS054_WEBSITE_CONSENT_NOT_PROVEN';
 END IF;
 -- A pre-grant event cannot be laundered as a post-consent observation.
 IF NEW.occurred_at < consent_received_at THEN
   RAISE EXCEPTION 'ANALYTICS054_PRE_CONSENT_EVENT_DENIED';
 END IF;
 -- Event ingestion time is from the database, never client-controlled.
 NEW.received_at := clock_timestamp();
 RETURN NEW;
END;
$fn$;

CREATE TRIGGER empire_analytics_events_consent_gate
 BEFORE INSERT ON public.empire_analytics_event_receipts
 FOR EACH ROW EXECUTE FUNCTION public.empire_analytics_event_before_insert();

-- No runtime grants or RLS policies. Even table owners are subject to RLS,
-- except privileged offline fixture administrators. A future migration
-- must explicitly provision a dedicated tenant-bound writer and deletion
-- authority after approved consent and retention controls.
ALTER TABLE public.empire_analytics_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_consent_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_consent_decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_event_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_analytics_event_receipts FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.empire_analytics_sessions,
  public.empire_analytics_consent_decisions,
  public.empire_analytics_event_receipts
FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_analytics_immutable(),
  public.empire_analytics_consent_before_insert(),
  public.empire_analytics_event_before_insert()
FROM PUBLIC;

DO $verify$
DECLARE r record;
BEGIN
 FOR r IN
  SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
  FROM pg_catalog.pg_class c
  JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relname IN (
    'empire_analytics_sessions',
    'empire_analytics_consent_decisions',
    'empire_analytics_event_receipts'
  )
 LOOP
   IF NOT r.relrowsecurity OR NOT r.relforcerowsecurity THEN
     RAISE EXCEPTION 'ANALYTICS054_RLS_NOT_FORCED';
   END IF;
 END LOOP;
 IF (SELECT count(*) FROM pg_catalog.pg_class c
     JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='public' AND c.relname IN (
       'empire_analytics_sessions','empire_analytics_consent_decisions',
       'empire_analytics_event_receipts'
     ))<>3 THEN
     RAISE EXCEPTION 'ANALYTICS054_TABLE_COUNT_INVALID';
 END IF;
END;
$verify$;
COMMIT;
