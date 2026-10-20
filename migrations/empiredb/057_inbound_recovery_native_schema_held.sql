-- EmpireDB 057: native inbound recovery evidence foundation.
-- PREPARED / HELD. DO NOT APPLY TO PRODUCTION without DBA approval,
-- trusted backup, rollback plan and isolated PostgreSQL RLS tests.
--
-- Native EmpireDB PostgreSQL only. No Supabase auth.users, anon,
-- authenticated, external JWT or duplicate tenant-membership table.
-- Existing public.empire_crm_tenant_memberships is the account authority.
-- This release creates no writers, logins, memberships, HTTP routes, jobs,
-- public grants, trigger, outbound, booking writes or payment activation.

BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $preflight$
DECLARE t text;
BEGIN
  IF current_database() NOT IN ('empiredb', 'inbound_recovery_057_fixture') THEN
    RAISE EXCEPTION 'INBOUND057_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname = 'empiredb_migrator'
      AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
  ) THEN
    RAISE EXCEPTION 'INBOUND057_MIGRATOR_ROLE_MISSING_OR_UNSAFE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    WHERE c.oid = pg_catalog.to_regclass('public.empire_crm_tenant_memberships')
      AND c.relkind = 'r'
      AND c.relrowsecurity
  ) THEN
    RAISE EXCEPTION 'INBOUND057_CANONICAL_CRM_MEMBERSHIP_ABSENT';
  END IF;
  IF pg_catalog.to_regprocedure('public.empire_crm_read_member(text,uuid)') IS NULL
    OR pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
  THEN
    RAISE EXCEPTION 'INBOUND057_NATIVE_TENANT_AUTHORITY_ABSENT';
  END IF;
  FOREACH t IN ARRAY ARRAY[
    'inbound_recovery_tenants',
    'inbound_recovery_events',
    'inbound_recovery_signed_callbacks',
    'inbound_recovery_management_access_audit',
    'inbound_booking_workflow_events',
    'inbound_recovery_contact_suppression',
    'inbound_recovery_calendar_bindings',
    'inbound_recovery_calendar_links',
    'inbound_recovery_calendar_status_evidence',
    'inbound_recovery_calendar_projection_delivery'
  ] LOOP
    IF pg_catalog.to_regclass('public.' || t) IS NOT NULL THEN
      RAISE EXCEPTION 'INBOUND057_EXISTING_OBJECT_NEEDS_RECONCILIATION:%', t;
    END IF;
  END LOOP;
END;
$preflight$;

SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.inbound_recovery_tenants (
    tenant_id uuid PRIMARY KEY,
    business_name text NOT NULL CHECK (length(btrim(business_name)) BETWEEN 1 AND 240),
    vertical text NOT NULL DEFAULT 'general',
    lifecycle_state text NOT NULL DEFAULT 'draft'
        CHECK (lifecycle_state IN ('draft','testing','approved','suspended')),
    inbound_route_enabled boolean NOT NULL DEFAULT false,
    booking_integration_verified boolean NOT NULL DEFAULT false,
    callback_capture_allowed boolean NOT NULL DEFAULT false,
    retention_days integer NOT NULL DEFAULT 90 CHECK (retention_days BETWEEN 1 AND 365),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE public.inbound_recovery_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    event_id text NOT NULL CHECK (length(btrim(event_id)) BETWEEN 1 AND 240),
    call_id text NOT NULL CHECK (length(btrim(call_id)) BETWEEN 1 AND 240),
    occurred_at timestamptz NOT NULL,
    kind text NOT NULL CHECK (kind IN (
        'ringing','answered','unanswered','busy','rejected','failed','completed',
        'callback_requested','callback_connected','booking_requested',
        'booking_confirmed','booking_cancelled','invoice_paid',
        'human_transfer','followup_opt_out'
    )),
    origin text NOT NULL CHECK (origin IN ('provider','operator','calendar','payments')),
    evidence_ref text NOT NULL DEFAULT '',
    evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    amount_minor bigint,
    currency char(3),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (tenant_id,event_id),
    CHECK (
        (kind = 'invoice_paid' AND evidence_verified IS TRUE
          AND synthetic IS FALSE AND origin='payments'
          AND length(btrim(evidence_ref)) > 0
          AND amount_minor IS NOT NULL AND amount_minor > 0
          AND currency IS NOT NULL AND currency ~ '^[A-Z]{3}$')
        OR (kind <> 'invoice_paid' AND amount_minor IS NULL AND currency IS NULL)
    ),
    CHECK (
        kind NOT IN ('callback_connected','booking_confirmed','booking_cancelled')
        OR (evidence_verified IS TRUE AND length(btrim(evidence_ref)) > 0
          AND ((kind='callback_connected' AND origin='provider')
            OR (kind IN ('booking_confirmed','booking_cancelled') AND origin='calendar')))
    ),
    CHECK (kind NOT IN ('ringing','answered','unanswered','busy','rejected','failed','completed')
           OR origin='provider')
);
CREATE INDEX inbound_recovery_events_tenant_call_time_idx
  ON public.inbound_recovery_events(tenant_id,call_id,occurred_at);

CREATE TABLE public.inbound_recovery_signed_callbacks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL,
    event_id text NOT NULL,
    provider text NOT NULL CHECK(provider = 'vonage'),
    api_key text NOT NULL,
    jwt_id text NOT NULL,
    payload_sha256 char(64) NOT NULL CHECK(payload_sha256 ~ '^[a-f0-9]{64}$'),
    verified_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(api_key,jwt_id),
    FOREIGN KEY(tenant_id,event_id)
      REFERENCES public.inbound_recovery_events(tenant_id,event_id)
);

CREATE TABLE public.inbound_recovery_management_access_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    actor_fingerprint char(64) NOT NULL CHECK(actor_fingerprint ~ '^[a-f0-9]{64}$'),
    operation text NOT NULL CHECK(operation IN (
        'profile_read','scorecard_read','queue_read','patterns_read',
        'knowledge_read','workflow_read','calendar_read'
    )),
    previous_hash text NOT NULL,
    record_hash char(64) NOT NULL CHECK(record_hash ~ '^[a-f0-9]{64}$'),
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX inbound_recovery_management_audit_tenant_time_idx
  ON public.inbound_recovery_management_access_audit(tenant_id,occurred_at DESC);

CREATE TABLE public.inbound_booking_workflow_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    event_id text NOT NULL CHECK(length(btrim(event_id)) > 0),
    call_id text NOT NULL CHECK(length(btrim(call_id)) > 0),
    contact_key char(64) NOT NULL CHECK(contact_key ~ '^[0-9a-f]{64}$'),
    kind text NOT NULL CHECK(kind IN (
        'appointment_requested','callback_requested','callback_consent_granted',
        'callback_consent_revoked','followup_opt_out',
        'calendar_booking_confirmed','calendar_booking_cancelled','callback_connected'
    )),
    occurred_at timestamptz NOT NULL,
    origin text NOT NULL CHECK(origin IN (
        'verified_inbound','operator_review','calendar_adapter','voice_provider'
    )),
    evidence_ref text NOT NULL CHECK(length(btrim(evidence_ref)) > 0),
    evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    consent_expires_at timestamptz,
    appointment_id text,
    calendar_ref text,
    appointment_starts_at timestamptz,
    appointment_ends_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(tenant_id,event_id),
    CHECK (
        (kind='callback_consent_granted'
          AND consent_expires_at > occurred_at
          AND consent_expires_at <= occurred_at + interval '30 days')
        OR (kind <> 'callback_consent_granted' AND consent_expires_at IS NULL)
    ),
    CHECK (
        (kind IN ('calendar_booking_confirmed','calendar_booking_cancelled')
          AND origin='calendar_adapter' AND evidence_verified IS TRUE
          AND nullif(btrim(appointment_id),'') IS NOT NULL
          AND nullif(btrim(calendar_ref),'') IS NOT NULL
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
        OR (kind='callback_connected' AND origin='voice_provider')
        OR (kind IN ('calendar_booking_confirmed','calendar_booking_cancelled')
          AND origin='calendar_adapter')
    )
);
CREATE INDEX inbound_booking_workflow_tenant_call_time_idx
  ON public.inbound_booking_workflow_events(tenant_id,call_id,occurred_at);
CREATE INDEX inbound_booking_workflow_tenant_contact_time_idx
  ON public.inbound_booking_workflow_events(tenant_id,contact_key,occurred_at);

CREATE TABLE public.inbound_recovery_contact_suppression (
    tenant_id uuid NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    contact_key char(64) NOT NULL CHECK(contact_key ~ '^[0-9a-f]{64}$'),
    suppression_reason text NOT NULL CHECK(suppression_reason IN (
        'followup_opt_out','compliance_hold'
    )),
    evidence_ref text NOT NULL CHECK(length(btrim(evidence_ref)) > 0),
    recorded_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,contact_key)
);

-- Calendar IDs may legitimately be shared provider IDs across tenants.
-- Tenant is part of every PK/FK: never authorize by calendar_id alone.
CREATE TABLE public.inbound_recovery_calendar_bindings (
    tenant_id uuid NOT NULL REFERENCES public.inbound_recovery_tenants(tenant_id),
    calendar_id text NOT NULL CHECK(length(btrim(calendar_id)) > 0),
    provider_account_ref text NOT NULL CHECK(length(btrim(provider_account_ref)) > 0),
    owner_approved boolean NOT NULL DEFAULT false,
    account_access_verified boolean NOT NULL DEFAULT false,
    owner_approval_evidence_ref text NOT NULL
       CHECK(length(btrim(owner_approval_evidence_ref)) > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,calendar_id)
);

CREATE TABLE public.inbound_recovery_calendar_links (
    tenant_id uuid NOT NULL,
    calendar_id text NOT NULL,
    appointment_id text NOT NULL CHECK(length(btrim(appointment_id)) > 0),
    call_id text NOT NULL CHECK(length(btrim(call_id)) > 0),
    contact_key char(64) NOT NULL CHECK(contact_key ~ '^[a-f0-9]{64}$'),
    tracked_source_ref text NOT NULL CHECK(length(btrim(tracked_source_ref)) > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,calendar_id,appointment_id),
    FOREIGN KEY(tenant_id,calendar_id)
       REFERENCES public.inbound_recovery_calendar_bindings(tenant_id,calendar_id)
);

CREATE TABLE public.inbound_recovery_calendar_status_evidence (
    tenant_id uuid NOT NULL,
    calendar_id text NOT NULL,
    appointment_id text NOT NULL,
    provider_revision_ref text NOT NULL CHECK(length(btrim(provider_revision_ref)) > 0),
    booking_status text NOT NULL CHECK(booking_status IN ('confirmed','cancelled')),
    observed_at timestamptz NOT NULL,
    provider_updated_at timestamptz,
    source_receipt_sha256 char(64) NOT NULL
       CHECK(source_receipt_sha256 ~ '^[a-f0-9]{64}$'),
    adapter_evidence_verified boolean NOT NULL DEFAULT false,
    synthetic boolean NOT NULL DEFAULT true,
    PRIMARY KEY(tenant_id,calendar_id,appointment_id,provider_revision_ref),
    FOREIGN KEY(tenant_id,calendar_id,appointment_id)
       REFERENCES public.inbound_recovery_calendar_links(tenant_id,calendar_id,appointment_id)
);

CREATE TABLE public.inbound_recovery_calendar_projection_delivery (
    tenant_id uuid NOT NULL,
    calendar_id text NOT NULL,
    appointment_id text NOT NULL,
    provider_revision_ref text NOT NULL,
    delivery_status text NOT NULL DEFAULT 'pending'
       CHECK(delivery_status IN ('pending','complete')),
    projected_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(tenant_id,calendar_id,appointment_id,provider_revision_ref),
    FOREIGN KEY(tenant_id,calendar_id,appointment_id,provider_revision_ref)
       REFERENCES public.inbound_recovery_calendar_status_evidence(
         tenant_id,calendar_id,appointment_id,provider_revision_ref),
    CHECK (
        (delivery_status='pending' AND projected_at IS NULL)
        OR (delivery_status='complete' AND projected_at IS NOT NULL)
    )
);
CREATE INDEX inbound_calendar_projection_pending_by_tenant
  ON public.inbound_recovery_calendar_projection_delivery(
    tenant_id,delivery_status,created_at);
CREATE INDEX inbound_recovery_calendar_status_tenant_time_idx
  ON public.inbound_recovery_calendar_status_evidence(
    tenant_id,calendar_id,observed_at DESC);

-- Mandatory FORCE RLS on every table; NO policies = default-deny even for
-- inherited application roles. No customer or application grants.
ALTER TABLE public.inbound_recovery_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_signed_callbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_signed_callbacks FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_management_access_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_management_access_audit FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_booking_workflow_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_booking_workflow_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_contact_suppression ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_contact_suppression FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_bindings FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_links FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_status_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_status_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_projection_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbound_recovery_calendar_projection_delivery FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE
  public.inbound_recovery_tenants,
  public.inbound_recovery_events,
  public.inbound_recovery_signed_callbacks,
  public.inbound_recovery_management_access_audit,
  public.inbound_booking_workflow_events,
  public.inbound_recovery_contact_suppression,
  public.inbound_recovery_calendar_bindings,
  public.inbound_recovery_calendar_links,
  public.inbound_recovery_calendar_status_evidence,
  public.inbound_recovery_calendar_projection_delivery
FROM PUBLIC;

-- Identity sequences are private too. No GRANT USAGE on schemas, roles,
-- identities or sequences; no SQL SECURITY DEFINER escape hatches.
COMMIT;
