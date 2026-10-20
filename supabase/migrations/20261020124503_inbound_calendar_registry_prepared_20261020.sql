-- PREPARED ONLY: independent Google Calendar read-back provenance and status.
-- Ordered after 20261020124500/01/02; never apply without real RLS tests.
-- Owner-authorised server-side integration only; NO OAuth tokens stored here.
BEGIN;

CREATE TABLE IF NOT EXISTS public.inbound_recovery_calendar_bindings (
    calendar_id text PRIMARY KEY CHECK (length(trim(calendar_id)) > 0),
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    provider_account_ref text NOT NULL CHECK (length(trim(provider_account_ref)) > 0),
    owner_approved boolean NOT NULL DEFAULT false,
    account_access_verified boolean NOT NULL DEFAULT false,
    owner_approval_evidence_ref text NOT NULL
        CHECK (length(trim(owner_approval_evidence_ref)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (calendar_id, tenant_id)
);

CREATE TABLE IF NOT EXISTS public.inbound_recovery_calendar_links (
    calendar_id text NOT NULL,
    tenant_id text NOT NULL,
    appointment_id text NOT NULL CHECK (length(trim(appointment_id)) > 0),
    call_id text NOT NULL CHECK (length(trim(call_id)) > 0),
    contact_key char(64) NOT NULL CHECK (contact_key ~ '^[a-f0-9]{64}$'),
    tracked_source_ref text NOT NULL CHECK (length(trim(tracked_source_ref)) > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(calendar_id, appointment_id),
    UNIQUE (calendar_id, appointment_id, tenant_id),
    FOREIGN KEY(calendar_id, tenant_id)
        REFERENCES public.inbound_recovery_calendar_bindings(calendar_id, tenant_id)
);

CREATE TABLE IF NOT EXISTS public.inbound_recovery_calendar_status_evidence (
    calendar_id text NOT NULL,
    appointment_id text NOT NULL,
    tenant_id text NOT NULL,
    provider_revision_ref text NOT NULL CHECK (length(trim(provider_revision_ref)) > 0),
    booking_status text NOT NULL
        CHECK (booking_status IN ('confirmed', 'cancelled')),
    observed_at timestamptz NOT NULL,
    provider_updated_at timestamptz,
    source_receipt_sha256 char(64) NOT NULL
        CHECK (source_receipt_sha256 ~ '^[a-f0-9]{64}$'),
    adapter_evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    PRIMARY KEY (calendar_id, appointment_id, provider_revision_ref),
    UNIQUE (calendar_id, appointment_id, provider_revision_ref, tenant_id),
    FOREIGN KEY (calendar_id, appointment_id, tenant_id)
        REFERENCES public.inbound_recovery_calendar_links(
            calendar_id, appointment_id, tenant_id
        )
);

-- Separate durable projection acknowledgements. Creation of a provider
-- readback and creation of its PENDING delivery entry must be atomic in the
-- eventual trusted database adapter. No automatic worker is installed here.
CREATE TABLE IF NOT EXISTS public.inbound_recovery_calendar_projection_delivery (
    calendar_id text NOT NULL,
    appointment_id text NOT NULL,
    provider_revision_ref text NOT NULL,
    tenant_id text NOT NULL,
    delivery_status text NOT NULL DEFAULT 'pending'
        CHECK (delivery_status IN ('pending', 'complete')),
    projected_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (calendar_id, appointment_id, provider_revision_ref),
    FOREIGN KEY (calendar_id, appointment_id, provider_revision_ref, tenant_id)
        REFERENCES public.inbound_recovery_calendar_status_evidence
            (calendar_id, appointment_id, provider_revision_ref, tenant_id),
    CHECK (
        (delivery_status = 'pending' AND projected_at IS NULL)
        OR (delivery_status = 'complete' AND projected_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS inbound_calendar_projection_pending_by_tenant
    ON public.inbound_recovery_calendar_projection_delivery
        (tenant_id, delivery_status, created_at);

CREATE INDEX IF NOT EXISTS inbound_recovery_calendar_status_tenant_time_idx
    ON public.inbound_recovery_calendar_status_evidence
       (tenant_id, calendar_id, observed_at DESC);

-- Backend-only evidence, no customer direct reads or writes.
ALTER TABLE public.inbound_recovery_calendar_projection_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_projection_delivery FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_links FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_status_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_status_evidence FORCE ROW LEVEL SECURITY;

REVOKE ALL ON public.inbound_recovery_calendar_projection_delivery FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_calendar_bindings FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_calendar_links FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_calendar_status_evidence FROM PUBLIC, anon, authenticated;

-- No stored OAuth access or refresh tokens and no automatic provider writes.
-- Production adapter provisioning and RLS/security tests need separate approval.
COMMIT;
