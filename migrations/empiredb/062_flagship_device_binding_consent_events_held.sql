-- ORIGINAL EmpireOS / EmpireDB 062: HELD device-binding + consent event contract.
-- No true Identity registration, user/device attestation, consent authentication,
-- notification sender, writer LOGIN, runtime grant, provider or production DDL.
-- The 061 callback write gate stays DENY-ALL: this migration DOES NOT alter it.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $preflight$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
    RAISE EXCEPTION 'TIMER062_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
     AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
    OR EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members
      WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles
                    WHERE rolname='empiredb_migrator'))
 THEN RAISE EXCEPTION 'TIMER062_OWNER_ROLE_UNVERIFIED'; END IF;
 IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NULL
    OR pg_catalog.to_regclass('public.empire_prime_timer_provider_receipts') IS NULL
    OR pg_catalog.to_regprocedure(
      'public.empire_prime_timer_consent_authority_held(uuid,text,text)'
    ) IS NULL
 THEN RAISE EXCEPTION 'TIMER062_ORIGINAL_057_TO_061_REQUIRED'; END IF;
 IF pg_catalog.to_regclass('public.empire_prime_reminder_devices_held') IS NOT NULL
    OR pg_catalog.to_regclass('public.empire_prime_reminder_timer_devices_held') IS NOT NULL
    OR pg_catalog.to_regclass('public.empire_prime_reminder_consent_events_held') IS NOT NULL
 THEN RAISE EXCEPTION 'TIMER062_ALREADY_PRESENT_OWNER_REVIEW_REQUIRED'; END IF;
 IF EXISTS (SELECT 1 FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname IN (
      'empire_prime_voice_timer_requests','empire_prime_timer_provider_receipts'
    ) AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity))
 THEN RAISE EXCEPTION 'TIMER062_EXISTING_RLS_NOT_FORCED'; END IF;
END;
$preflight$;

SET LOCAL ROLE empiredb_migrator;

-- These digests do NOT attest real device ownership. Only the actual
-- Identity/Security owner may subsequently define authorised enrolment.
CREATE TABLE public.empire_prime_reminder_devices_held (
 tenant_id uuid NOT NULL,
 actor_digest text NOT NULL CHECK(actor_digest ~ '^[a-f0-9]{64}$'),
 device_digest text NOT NULL CHECK(device_digest ~ '^[a-f0-9]{64}$'),
 device_attestation_digest text NOT NULL
   CHECK(device_attestation_digest ~ '^[a-f0-9]{64}$'),
 enrolled_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,actor_digest,device_digest),
 UNIQUE(tenant_id,device_attestation_digest)
);

CREATE TABLE public.empire_prime_reminder_timer_devices_held (
 tenant_id uuid NOT NULL,
 timer_digest text NOT NULL CHECK(timer_digest ~ '^[a-f0-9]{64}$'),
 actor_digest text NOT NULL CHECK(actor_digest ~ '^[a-f0-9]{64}$'),
 device_digest text NOT NULL CHECK(device_digest ~ '^[a-f0-9]{64}$'),
 source_attestation_digest text NOT NULL
   CHECK(source_attestation_digest ~ '^[a-f0-9]{64}$'),
 consent_evidence_digest text NOT NULL
   CHECK(consent_evidence_digest ~ '^[a-f0-9]{64}$'),
 bound_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,timer_digest),
 FOREIGN KEY(tenant_id,timer_digest)
   REFERENCES public.empire_prime_voice_timer_requests(tenant_id,timer_digest)
   ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,actor_digest,device_digest)
   REFERENCES public.empire_prime_reminder_devices_held(
      tenant_id,actor_digest,device_digest)
   ON DELETE RESTRICT
);

CREATE TABLE public.empire_prime_reminder_consent_events_held (
 tenant_id uuid NOT NULL,
 actor_digest text NOT NULL CHECK(actor_digest ~ '^[a-f0-9]{64}$'),
 device_digest text NOT NULL CHECK(device_digest ~ '^[a-f0-9]{64}$'),
 event_seq integer NOT NULL CHECK(event_seq BETWEEN 1 AND 1000000),
 event_digest text NOT NULL CHECK(event_digest ~ '^[a-f0-9]{64}$'),
 consent_evidence_digest text NOT NULL
   CHECK(consent_evidence_digest ~ '^[a-f0-9]{64}$'),
 identity_source_digest text NOT NULL
   CHECK(identity_source_digest ~ '^[a-f0-9]{64}$'),
 purpose text NOT NULL CHECK(purpose='TIMER_NOTIFICATION'),
 channel text NOT NULL CHECK(channel='PRIVATE_DEVICE'),
 decision text NOT NULL CHECK(decision IN ('GRANTED','REVOKED')),
 occurred_at timestamptz NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,actor_digest,device_digest,purpose,event_seq),
 UNIQUE(tenant_id,event_digest),
 FOREIGN KEY(tenant_id,actor_digest,device_digest)
   REFERENCES public.empire_prime_reminder_devices_held(
      tenant_id,actor_digest,device_digest)
   ON DELETE RESTRICT
);

CREATE FUNCTION public.empire_prime_reminder_binding_guard_held()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $binding_guard$
DECLARE v_actor text; v_source text; v_evidence text;
BEGIN
 SELECT actor_digest,source_attestation_digest,consent_evidence_digest
 INTO v_actor,v_source,v_evidence
 FROM public.empire_prime_voice_timer_requests
 WHERE tenant_id=NEW.tenant_id AND timer_digest=NEW.timer_digest
 FOR UPDATE;
 IF NOT FOUND OR v_actor IS DISTINCT FROM NEW.actor_digest
   OR v_source IS DISTINCT FROM NEW.source_attestation_digest
   OR v_evidence IS DISTINCT FROM NEW.consent_evidence_digest
 THEN RAISE EXCEPTION 'TIMER062_ORIGINAL_TIMER_ACTOR_SOURCE_CONSENT_MISMATCH'; END IF;
 RETURN NEW;
END;
$binding_guard$;

CREATE FUNCTION public.empire_prime_reminder_consent_event_guard_held()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path='' SET row_security=on
AS $event_guard$
DECLARE v_previous_seq integer; v_previous_decision text;
BEGIN
 -- This row is the cross-session serialization boundary. An eventual
 -- DB-side callback consent reader must take SHARE on the SAME row.
 PERFORM 1 FROM public.empire_prime_reminder_devices_held
 WHERE tenant_id=NEW.tenant_id AND actor_digest=NEW.actor_digest
   AND device_digest=NEW.device_digest
 FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'TIMER062_UNKNOWN_DEVICE'; END IF;
 SELECT event_seq,decision INTO v_previous_seq,v_previous_decision
 FROM public.empire_prime_reminder_consent_events_held
 WHERE tenant_id=NEW.tenant_id AND actor_digest=NEW.actor_digest
   AND device_digest=NEW.device_digest AND purpose=NEW.purpose
 ORDER BY event_seq DESC LIMIT 1;
 IF NOT FOUND THEN
   IF NEW.event_seq<>1 OR NEW.decision<>'GRANTED' THEN
     RAISE EXCEPTION 'TIMER062_FIRST_EVENT_MUST_GRANT';
   END IF;
 ELSE
   IF NEW.event_seq<>v_previous_seq+1
      OR NEW.decision=v_previous_decision THEN
     RAISE EXCEPTION 'TIMER062_CONSENT_EVENT_ORDER_OR_DUPLICATE';
   END IF;
 END IF;
 IF NEW.occurred_at>pg_catalog.clock_timestamp()+interval '1 minute'
    OR NEW.occurred_at<pg_catalog.clock_timestamp()-interval '1 hour'
 THEN RAISE EXCEPTION 'TIMER062_CONSENT_EVENT_TIME_UNTRUSTED'; END IF;
 RETURN NEW;
END;
$event_guard$;

CREATE TRIGGER empire_prime_reminder_binding_insert_062
 BEFORE INSERT ON public.empire_prime_reminder_timer_devices_held
 FOR EACH ROW EXECUTE FUNCTION public.empire_prime_reminder_binding_guard_held();
CREATE TRIGGER empire_prime_reminder_consent_insert_062
 BEFORE INSERT ON public.empire_prime_reminder_consent_events_held
 FOR EACH ROW EXECUTE FUNCTION public.empire_prime_reminder_consent_event_guard_held();

CREATE TRIGGER empire_prime_reminder_devices_immutable_062
 BEFORE UPDATE OR DELETE ON public.empire_prime_reminder_devices_held
 FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();
CREATE TRIGGER empire_prime_reminder_bindings_immutable_062
 BEFORE UPDATE OR DELETE ON public.empire_prime_reminder_timer_devices_held
 FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();
CREATE TRIGGER empire_prime_reminder_consent_immutable_062
 BEFORE UPDATE OR DELETE ON public.empire_prime_reminder_consent_events_held
 FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();

ALTER TABLE public.empire_prime_reminder_devices_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_reminder_devices_held FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_reminder_timer_devices_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_reminder_timer_devices_held FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_reminder_consent_events_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_reminder_consent_events_held FORCE ROW LEVEL SECURITY;

-- Owner-only NOLOGIN review authority: NO production app policy or GRANT.
CREATE POLICY empire_prime_held_owner_devices_062
 ON public.empire_prime_reminder_devices_held FOR ALL TO empiredb_migrator
 USING(true) WITH CHECK(true);
CREATE POLICY empire_prime_held_owner_bindings_062
 ON public.empire_prime_reminder_timer_devices_held FOR ALL TO empiredb_migrator
 USING(true) WITH CHECK(true);
CREATE POLICY empire_prime_held_owner_consents_062
 ON public.empire_prime_reminder_consent_events_held FOR ALL TO empiredb_migrator
 USING(true) WITH CHECK(true);

REVOKE ALL ON TABLE public.empire_prime_reminder_devices_held FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_prime_reminder_timer_devices_held FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_prime_reminder_consent_events_held FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_reminder_binding_guard_held() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_reminder_consent_event_guard_held() FROM PUBLIC;

COMMENT ON TABLE public.empire_prime_reminder_devices_held IS
 'HELD: opaque proposed actor/device enrolment metadata, not verified original Identity authority or permission.';
COMMENT ON TABLE public.empire_prime_reminder_consent_events_held IS
 'HELD: append-only prospective consent events, not authenticated original user permission. Zero runtime grants.';
COMMIT;
