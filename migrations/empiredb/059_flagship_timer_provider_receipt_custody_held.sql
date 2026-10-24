-- EMPIRE AI / ORIGINAL EMPIREDB 059: HELD PROVIDER CALLBACK CUSTODY
-- FOR OWNER REVIEW / DISPOSABLE POSTGRESQL FIXTURE ONLY.
-- Depends on 057, 058. No live provider account, app grants, dispatch
-- worker, cron, callback endpoint, schema activation or source proof.
-- Signatures are NOT verified here; digests are untrusted metadata.
-- A signed receipt must be independently authenticated by the original
-- Notification/Security owner before any future permitted invocation.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $owner_preflight$
BEGIN
    IF current_database() NOT IN ('empiredb','empire_timer_fixture') THEN
        RAISE EXCEPTION 'TIMER059_WRONG_DATABASE';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname='empiredb_migrator'
          AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
          AND NOT rolcreatedb AND NOT rolcreaterole
    ) THEN
        RAISE EXCEPTION 'TIMER059_RESTRICTED_MIGRATOR_MISSING';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE roleid = (
            SELECT oid FROM pg_catalog.pg_roles
            WHERE rolname='empiredb_migrator'
        )
    ) THEN
        RAISE EXCEPTION 'TIMER059_MIGRATOR_ROLE_MEMBERSHIP_UNREVIEWED';
    END IF;
    IF pg_catalog.to_regclass('public.empire_prime_voice_timer_requests') IS NULL
       OR pg_catalog.to_regclass('public.empire_prime_voice_timer_events') IS NULL
       OR pg_catalog.to_regprocedure(
            'public.empire_prime_voice_timer_transition_held(uuid,text,text,text,text)'
       ) IS NULL
    THEN
        RAISE EXCEPTION 'TIMER059_REQUIRES_ORIGINAL_LEDGER_057_AND_GUARD_058';
    END IF;
    IF pg_catalog.to_regclass('public.empire_prime_timer_provider_receipts') IS NOT NULL
       OR pg_catalog.to_regprocedure(
            'public.empire_prime_timer_provider_receipt_guard_held()'
       ) IS NOT NULL
    THEN
        RAISE EXCEPTION 'TIMER059_ALREADY_PRESENT_REQUIRE_OWNER_REVIEW';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public'
          AND c.relname IN ('empire_prime_voice_timer_requests',
                            'empire_prime_voice_timer_events')
          AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    ) THEN
        RAISE EXCEPTION 'TIMER059_ORIGINAL_LEDGER_MUST_FORCE_RLS';
    END IF;
END;
$owner_preflight$;

SET LOCAL ROLE empiredb_migrator;

-- Metadata custody ONLY: no payload, name, email, device ID, audio, IP,
-- webhook body, token, provider key or human identifier. Provider reference,
-- receipt and nonce must be purpose-keyed digests in a real implementation.
CREATE TABLE public.empire_prime_timer_provider_receipts (
    tenant_id uuid NOT NULL,
    timer_digest text NOT NULL CHECK (timer_digest ~ '^[0-9a-f]{64}$'),
    provider_code text NOT NULL CHECK (
        provider_code ~ '^[a-z][a-z0-9_]{2,47}$'
    ),
    callback_nonce_digest text NOT NULL CHECK (
        callback_nonce_digest ~ '^[0-9a-f]{64}$'
    ),
    receipt_digest text NOT NULL CHECK (receipt_digest ~ '^[0-9a-f]{64}$'),
    claim_event_digest text NOT NULL CHECK (
        claim_event_digest ~ '^[0-9a-f]{64}$'
    ),
    delivery_reference_digest text NOT NULL CHECK (
        delivery_reference_digest ~ '^[0-9a-f]{64}$'
    ),
    source_attestation_digest text NOT NULL CHECK (
        source_attestation_digest ~ '^[0-9a-f]{64}$'
    ),
    callback_stage text NOT NULL CHECK (
        callback_stage IN ('ACCEPTED','DELIVERED','FAILED')
    ),
    callback_seq smallint NOT NULL CHECK (callback_seq BETWEEN 1 AND 2),
    provider_reported_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
    PRIMARY KEY (tenant_id,timer_digest,callback_seq),
    -- Replay protection across processes, timers and TENANTS for each provider.
    UNIQUE (provider_code,callback_nonce_digest),
    UNIQUE (provider_code,receipt_digest),
    FOREIGN KEY (tenant_id,timer_digest)
      REFERENCES public.empire_prime_voice_timer_requests(tenant_id,timer_digest)
      ON DELETE RESTRICT
);
COMMENT ON TABLE public.empire_prime_timer_provider_receipts IS
    'HELD: metadata-only synthetic callback custody, not independently authenticated provider source or device delivery. No runtime grants, webhook or sending authority.';

CREATE FUNCTION public.empire_prime_timer_provider_receipt_guard_held()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = '' SET row_security = on
AS $receipt_guard$
DECLARE
    v_source text;
    v_claim_seq smallint;
    v_prev_status text;
    v_prev_provider text;
    v_prev_reference text;
    v_prev_time timestamptz;
    v_count int;
    v_clock timestamptz;
BEGIN
    -- Serialize receipt status transitions against each other AND against
    -- the original 058 timer claim/cancel on the same parent request row.
    SELECT r.source_attestation_digest INTO v_source
    FROM public.empire_prime_voice_timer_requests r
    WHERE r.tenant_id=NEW.tenant_id AND r.timer_digest=NEW.timer_digest
    FOR UPDATE;
    IF NOT FOUND OR v_source IS DISTINCT FROM NEW.source_attestation_digest THEN
        RAISE EXCEPTION 'TIMER059_TENANT_OR_SOURCE_BINDING_REFUSED';
    END IF;
    SELECT e.seq INTO v_claim_seq
    FROM public.empire_prime_voice_timer_events e
    WHERE e.tenant_id=NEW.tenant_id AND e.timer_digest=NEW.timer_digest
      AND e.event_kind='DISPATCH_CLAIMED'
      AND e.event_digest=NEW.claim_event_digest;
    IF NOT FOUND OR v_claim_seq<>2 THEN
        RAISE EXCEPTION 'TIMER059_ATOMIC_CLAIM_BINDING_REQUIRED';
    END IF;
    v_clock:=pg_catalog.clock_timestamp();
    IF NEW.received_at>v_clock+interval '1 minute'
       OR NEW.received_at<v_clock-interval '5 minutes'
       OR NEW.provider_reported_at>v_clock+interval '1 minute'
       OR NEW.provider_reported_at<v_clock-interval '24 hours'
    THEN
        RAISE EXCEPTION 'TIMER059_RECEIPT_TIME_WINDOW_INVALID';
    END IF;
    SELECT count(*),max(received_at) INTO v_count,v_prev_time
    FROM public.empire_prime_timer_provider_receipts p
    WHERE p.tenant_id=NEW.tenant_id AND p.timer_digest=NEW.timer_digest;
    IF v_count=0 THEN
        IF NEW.callback_seq<>1 OR NEW.callback_stage NOT IN ('ACCEPTED','FAILED') THEN
            RAISE EXCEPTION 'TIMER059_FIRST_RECEIPT_MUST_ACCEPT_OR_FAIL';
        END IF;
    ELSIF v_count=1 THEN
        SELECT p.callback_stage,p.provider_code,p.delivery_reference_digest
          INTO v_prev_status,v_prev_provider,v_prev_reference
        FROM public.empire_prime_timer_provider_receipts p
        WHERE p.tenant_id=NEW.tenant_id AND p.timer_digest=NEW.timer_digest
          AND p.callback_seq=1;
        IF NEW.callback_seq<>2 OR v_prev_status<>'ACCEPTED'
           OR NEW.callback_stage NOT IN ('DELIVERED','FAILED')
           OR NEW.provider_code<>v_prev_provider
           OR NEW.delivery_reference_digest<>v_prev_reference
           OR NEW.received_at<v_prev_time
        THEN
            RAISE EXCEPTION 'TIMER059_ILLEGAL_OR_REPLAYED_RECEIPT_TRANSITION';
        END IF;
    ELSE
        RAISE EXCEPTION 'TIMER059_TERMINAL_RECEIPT_NO_RETRY';
    END IF;
    RETURN NEW;
END;
$receipt_guard$;

CREATE TRIGGER empire_prime_timer_receipt_insert_guard
    BEFORE INSERT ON public.empire_prime_timer_provider_receipts
    FOR EACH ROW
    EXECUTE FUNCTION public.empire_prime_timer_provider_receipt_guard_held();
CREATE TRIGGER empire_prime_timer_receipt_immutable
    BEFORE UPDATE OR DELETE ON public.empire_prime_timer_provider_receipts
    FOR EACH ROW
    EXECUTE FUNCTION public.empire_prime_voice_timer_immutable();

ALTER TABLE public.empire_prime_timer_provider_receipts
  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_prime_timer_provider_receipts
  FORCE ROW LEVEL SECURITY;

-- No runtime policy or application rights; this owner-only policy is not
-- permission to send or record an external notification.
CREATE POLICY empire_prime_timer_held_owner_receipts
    ON public.empire_prime_timer_provider_receipts
    FOR ALL TO empiredb_migrator USING (true) WITH CHECK (true);

REVOKE ALL ON TABLE public.empire_prime_timer_provider_receipts FROM PUBLIC;
REVOKE ALL ON FUNCTION public.empire_prime_timer_provider_receipt_guard_held()
    FROM PUBLIC;

COMMENT ON FUNCTION public.empire_prime_timer_provider_receipt_guard_held() IS
    'HELD only: validates metadata order, uniqueness, source binding and nonce replay. Does NOT authenticate provider signature, device, consent or real delivery.';

COMMIT;
