-- EmpireDB 057 — FLAGSHIP PRIME TIMER LEDGER — DDL CANDIDATE ONLY.
-- NOT APPLIED; NEVER include in unattended deploy or bootstrap.
-- Original EmpireDB DBA + Security + Voice + Privacy + ASTRA approval required.
-- This candidate creates no runtime roles, LOGINs, RLS SELECT policy, RPC,
-- writer GRANT, scheduler, recurring worker, delivery transport, reminders,
-- payments, commands, trigger-driven sends or other side effects.
-- Consent/source digests are REFERENCES only, not cryptographic proof.
-- Fixture DB allowed for isolated DBA tests ONLY; never run production
-- without independent owner approval, backup, RLS and rollback rehearsal.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $guard$
BEGIN
    IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
        RAISE EXCEPTION 'TIMER057_WRONG_DATABASE';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname='empiredb_migrator'
          AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
          AND NOT rolcreatedb AND NOT rolcreaterole
    ) THEN
        RAISE EXCEPTION 'TIMER057_CANONICAL_MIGRATOR_UNVERIFIED';
    END IF;
    IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NOT NULL
       OR pg_catalog.to_regclass('public.empire_prime_voice_timer_events') IS NOT NULL
       OR pg_catalog.to_regprocedure('public.empire_prime_voice_timer_immutable()') IS NOT NULL
    THEN
        RAISE EXCEPTION 'TIMER057_EXISTING_OBJECTS_REQUIRE_OWNER_RECONCILIATION';
    END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

-- No raw speech, text, email, name, address, device ID, location or IP is
-- stored. Tenant and user binding, provenance and consent must be resolved
-- by the original authorised Security/Identity/EmpireDB owner *before*
-- proposing an event; this migration does NOT supply that authority.
CREATE TABLE public.empire_prime_voice_timer_requests (
    tenant_id uuid NOT NULL,
    timer_digest text NOT NULL CHECK (timer_digest ~ '^[a-f0-9]{64}$'),
    actor_digest text NOT NULL CHECK (actor_digest ~ '^[a-f0-9]{64}$'),
    source_attestation_digest text NOT NULL
        CHECK (source_attestation_digest ~ '^[a-f0-9]{64}$'),
    consent_evidence_digest text NOT NULL
        CHECK (consent_evidence_digest ~ '^[a-f0-9]{64}$'),
    policy_revision text NOT NULL CHECK (policy_revision ~ '^[a-z][a-z0-9._-]{3,47}$'),
    duration_seconds integer NOT NULL CHECK (duration_seconds BETWEEN 1 AND 3600),
    created_at timestamptz NOT NULL,
    due_at timestamptz NOT NULL,
    provisioned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,timer_digest),
    CHECK (due_at > created_at AND
           due_at <= created_at + interval '1 hour' AND
           due_at = created_at + (duration_seconds * interval '1 second'))
);
COMMENT ON TABLE public.empire_prime_voice_timer_requests IS
 'STAGED ONLY. Original EmpireDB candidate for tenant-bound, non-content timer metadata. No runtime writer, authenticated sender, scheduling engine or consent authority established.';

-- Append-only event ledger. Primary/unique keys are necessary but not
-- sufficient for safe processing. Original DBA must independently approve
-- transactionally atomic first-claim RPC, original-owner identity authority,
-- delivery reconciler and replay tests BEFORE any LIVE writer exists.
CREATE TABLE public.empire_prime_voice_timer_events (
    tenant_id uuid NOT NULL,
    timer_digest text NOT NULL CHECK (timer_digest ~ '^[a-f0-9]{64}$'),
    seq smallint NOT NULL CHECK (seq BETWEEN 1 AND 32),
    event_digest text NOT NULL CHECK (event_digest ~ '^[a-f0-9]{64}$'),
    event_kind text NOT NULL CHECK (event_kind IN (
        'TIMER_CREATED','TIMER_CANCELLED','DISPATCH_CLAIMED',
        'PROVIDER_ACCEPTED_REPORTED','PROVIDER_DELIVERED_REPORTED',
        'PROVIDER_FAILED_REPORTED'
    )),
    occurred_at timestamptz NOT NULL,
    provider_receipt_digest text CHECK (
        provider_receipt_digest IS NULL
        OR provider_receipt_digest ~ '^[a-f0-9]{64}$'
    ),
    source_attestation_digest text NOT NULL
        CHECK (source_attestation_digest ~ '^[a-f0-9]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id,timer_digest,seq),
    UNIQUE (tenant_id,event_digest),
    FOREIGN KEY (tenant_id,timer_digest)
        REFERENCES public.empire_prime_voice_timer_requests(tenant_id,timer_digest)
        ON DELETE RESTRICT,
    CHECK (
        (event_kind IN ('PROVIDER_ACCEPTED_REPORTED',
                        'PROVIDER_DELIVERED_REPORTED',
                        'PROVIDER_FAILED_REPORTED')
         AND provider_receipt_digest IS NOT NULL)
        OR (event_kind NOT IN ('PROVIDER_ACCEPTED_REPORTED',
                               'PROVIDER_DELIVERED_REPORTED',
                               'PROVIDER_FAILED_REPORTED')
            AND provider_receipt_digest IS NULL)
    )
);
COMMENT ON TABLE public.empire_prime_voice_timer_events IS
 'STAGED ONLY. Synthetic protocol aligned to PRIME recovery shadow. Provider report digests are assertions, not independently verified delivery. Zero runtime INSERT/EXECUTE grants.';

CREATE INDEX empire_prime_timer_due_observe_ix
    ON public.empire_prime_voice_timer_requests(tenant_id,due_at);

CREATE FUNCTION public.empire_prime_voice_timer_immutable()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = ''
AS $function$
BEGIN
    RAISE EXCEPTION 'TIMER057_APPEND_ONLY_NO_UPDATE_OR_DELETE';
END;
$function$;

CREATE TRIGGER empire_prime_timer_requests_immutable
    BEFORE UPDATE OR DELETE ON public.empire_prime_voice_timer_requests
    FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();
CREATE TRIGGER empire_prime_timer_events_immutable
    BEFORE UPDATE OR DELETE ON public.empire_prime_voice_timer_events
    FOR EACH ROW EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();

-- Forced RLS with no policies denies ordinary row access regardless of a
-- shared service account. No policy or runtime role is created in 057.
ALTER TABLE public.empire_prime_voice_timer_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_voice_timer_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_voice_timer_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_voice_timer_events FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.empire_prime_voice_timer_requests FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_prime_voice_timer_events FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_voice_timer_immutable() FROM PUBLIC;

COMMENT ON FUNCTION public.empire_prime_voice_timer_immutable() IS
 'Held timer ledger immutability safeguard, not an executable scheduling capability.';
COMMIT;
