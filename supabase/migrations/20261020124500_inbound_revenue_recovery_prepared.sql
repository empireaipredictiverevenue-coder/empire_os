-- Empire AI inbound revenue recovery evidence storage (prepared, NOT applied).
-- Isolated from existing outbound calls, buyer/pay-per-call routing and CRM.
-- Does not create triggers, outbound jobs, callable RPCs, or public policies.
BEGIN;

CREATE TABLE IF NOT EXISTS public.inbound_recovery_tenants (
    tenant_id text PRIMARY KEY,
    business_name text NOT NULL,
    vertical text NOT NULL DEFAULT 'general',
    lifecycle_state text NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_state IN ('draft', 'testing', 'approved', 'suspended')),
    inbound_route_enabled boolean NOT NULL DEFAULT false,
    booking_integration_verified boolean NOT NULL DEFAULT false,
    callback_capture_allowed boolean NOT NULL DEFAULT false,
    retention_days integer NOT NULL DEFAULT 90 CHECK (retention_days BETWEEN 1 AND 365),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT recovery_tenant_key_nonblank CHECK (length(trim(tenant_id)) > 0)
);

CREATE TABLE IF NOT EXISTS public.inbound_recovery_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    event_id text NOT NULL,
    call_id text NOT NULL,
    occurred_at timestamptz NOT NULL,
    kind text NOT NULL CHECK (kind IN (
        'ringing','answered','unanswered','busy','rejected','failed','completed',
        'callback_requested','callback_connected','booking_requested','booking_confirmed',
        'invoice_paid','human_transfer','followup_opt_out'
    )),
    origin text NOT NULL CHECK (origin IN ('provider','operator','calendar','payments')),
    evidence_ref text NOT NULL DEFAULT '',
    evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    amount_minor bigint,
    currency char(3),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, event_id),
    CHECK (length(trim(event_id)) > 0 AND length(trim(call_id)) > 0),
    CHECK (
        (kind = 'invoice_paid' AND evidence_verified = true
            AND origin = 'payments' AND length(trim(evidence_ref)) > 0
            AND amount_minor IS NOT NULL AND amount_minor > 0
            AND currency IS NOT NULL AND currency ~ '^[A-Z]{3}$')
        OR (kind <> 'invoice_paid' AND amount_minor IS NULL AND currency IS NULL)
    ),
    CHECK (
        kind NOT IN ('callback_connected','booking_confirmed')
        OR (evidence_verified = true AND length(trim(evidence_ref)) > 0
            AND ((kind = 'callback_connected' AND origin = 'provider')
                OR (kind = 'booking_confirmed' AND origin = 'calendar')))
    ),
    CHECK (kind NOT IN ('ringing','answered','unanswered','busy','rejected','failed','completed')
           OR origin = 'provider')
);

CREATE INDEX IF NOT EXISTS inbound_recovery_events_tenant_call_time_idx
    ON public.inbound_recovery_events (tenant_id, call_id, occurred_at);

-- Prepared signed-Voice callback replay/audit evidence.
-- Do not ingest direct client payloads as verified callbacks.
CREATE TABLE IF NOT EXISTS public.inbound_recovery_signed_callbacks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    event_id text NOT NULL,
    provider text NOT NULL CHECK (provider = 'vonage'),
    api_key text NOT NULL,
    jwt_id text NOT NULL,
    payload_sha256 char(64) NOT NULL CHECK (payload_sha256 ~ '^[a-f0-9]{64}$'),
    verified_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (api_key, jwt_id),
    UNIQUE (tenant_id, event_id, jwt_id),
    FOREIGN KEY (tenant_id, event_id)
        REFERENCES public.inbound_recovery_events(tenant_id, event_id)
);

-- Default-deny. Future signed provider adapters use a dedicated internal role,
-- with verified tenant mapping; nothing is granted to client/browser roles.
ALTER TABLE public.inbound_recovery_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_signed_callbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_signed_callbacks FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.inbound_recovery_tenants FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_events FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.inbound_recovery_signed_callbacks FROM PUBLIC, anon, authenticated;

COMMIT;
