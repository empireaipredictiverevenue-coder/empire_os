-- Empire AI Revenue Recovery: PREPARED ONLY, NOT APPLIED.
-- Requires prior 20261020124500 and 20261020124501 core/membership migrations.
-- Tenant-scoped booking/callback evidence and durable global suppression.
-- No client write grants, public APIs, triggers, contacts, or provider jobs.
BEGIN;

CREATE TABLE IF NOT EXISTS public.inbound_booking_workflow_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    event_id text NOT NULL CHECK (length(trim(event_id)) > 0),
    call_id text NOT NULL CHECK (length(trim(call_id)) > 0),
    contact_key char(64) NOT NULL CHECK (contact_key ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CHECK (kind IN (
        'appointment_requested', 'callback_requested', 'callback_consent_granted',
        'callback_consent_revoked', 'followup_opt_out',
        'calendar_booking_confirmed', 'calendar_booking_cancelled',
        'callback_connected'
    )),
    occurred_at timestamptz NOT NULL,
    origin text NOT NULL CHECK (origin IN (
        'verified_inbound', 'operator_review', 'calendar_adapter', 'voice_provider'
    )),
    evidence_ref text NOT NULL CHECK (length(trim(evidence_ref)) > 0),
    evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    consent_expires_at timestamptz,
    appointment_id text,
    calendar_ref text,
    appointment_starts_at timestamptz,
    appointment_ends_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_id),
    CHECK (
        (kind = 'callback_consent_granted'
          AND consent_expires_at > occurred_at
          AND consent_expires_at <= occurred_at + interval '30 days')
        OR (kind <> 'callback_consent_granted' AND consent_expires_at IS NULL)
    ),
    CHECK (
        (kind IN ('calendar_booking_confirmed','calendar_booking_cancelled')
          AND origin = 'calendar_adapter'
          AND evidence_verified = true
          AND nullif(trim(appointment_id), '') IS NOT NULL
          AND nullif(trim(calendar_ref), '') IS NOT NULL
          AND appointment_starts_at IS NOT NULL
          AND appointment_ends_at > appointment_starts_at
          AND appointment_ends_at <= appointment_starts_at + interval '24 hours')
        OR (kind NOT IN ('calendar_booking_confirmed','calendar_booking_cancelled')
          AND appointment_id IS NULL AND calendar_ref IS NULL
          AND appointment_starts_at IS NULL AND appointment_ends_at IS NULL)
    ),
    CHECK (
        (kind IN ('appointment_requested','callback_requested',
                  'callback_consent_granted','callback_consent_revoked','followup_opt_out')
         AND origin IN ('verified_inbound','operator_review'))
        OR (kind = 'callback_connected' AND origin = 'voice_provider')
        OR (kind IN ('calendar_booking_confirmed','calendar_booking_cancelled')
            AND origin = 'calendar_adapter')
    )
);

CREATE INDEX IF NOT EXISTS inbound_booking_workflow_tenant_call_time_idx
    ON public.inbound_booking_workflow_events (tenant_id, call_id, occurred_at);
CREATE INDEX IF NOT EXISTS inbound_booking_workflow_tenant_contact_time_idx
    ON public.inbound_booking_workflow_events (tenant_id, contact_key, occurred_at);

-- Unlike operational event lookbacks, suppression state is indefinite until
-- a separately verified explicit opt-in/revocation authority is implemented.
-- No automatic resubscribe action exists in this migration.
CREATE TABLE IF NOT EXISTS public.inbound_recovery_contact_suppression (
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    contact_key char(64) NOT NULL CHECK (contact_key ~ '^[0-9a-f]{64}$'),
    suppression_reason text NOT NULL
        CHECK (suppression_reason IN ('followup_opt_out', 'compliance_hold')),
    evidence_ref text NOT NULL CHECK (length(trim(evidence_ref)) > 0),
    recorded_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, contact_key)
);

ALTER TABLE public.inbound_booking_workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_booking_workflow_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_contact_suppression ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_contact_suppression FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.inbound_booking_workflow_events FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_contact_suppression FROM PUBLIC, anon, authenticated;

-- Dedicated internal trusted adapters must authenticate provider evidence,
-- own the tenant/customer identity join, and receive the least privilege
-- necessary in a separately approved production release.
COMMIT;
