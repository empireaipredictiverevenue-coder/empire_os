-- EmpireDB Mautic inbox unnumbered draft: PREPARED-ONLY (DO NOT APPLY).
-- Scope: append-only tenant-bound, PII-free signed Mautic event review inbox.
-- No runtime registration, customer contact import, sending, payment or campaign execution.
-- Founder/DBA approval REQUIRED before migration, role/user provisioning or activation.
-- Provision separately:
--   empire_mautic_crm_inbox_writer NOLOGIN NOINHERIT
--   per-tenant LOGIN, NOINHERIT, member ONLY of the above role and mapped
--   through existing trusted public.empire_current_tenant_id() session_user.
BEGIN;
SET LOCAL ROLE empiredb_migrator;

DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','mautic_crm_inbox_fixture') THEN
   RAISE EXCEPTION 'wrong EmpireDB Mautic inbox migration database';
 END IF;
 IF pg_catalog.to_regclass('public.empire_crm_mautic_event_inbox') IS NOT NULL THEN
   RAISE EXCEPTION 'canonical Mautic inbox already exists; reconcile, do not overwrite';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empire_mautic_crm_inbox_writer'
   AND NOT rolcanlogin AND NOT rolinherit AND NOT rolsuper
   AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN
   RAISE EXCEPTION 'dedicated nonlogin Mautic CRM inbox writer role required';
 END IF;
 IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
      WHERE p.oid='public.empire_current_tenant_id()'::pg_catalog.regprocedure
        AND p.prosecdef AND p.provolatile='s'
        AND r.rolname='empiredb_migrator'
    ) THEN
   RAISE EXCEPTION 'existing authenticated session_user tenant resolver required';
 END IF;
END;
$guard$;

CREATE TABLE public.empire_crm_mautic_event_inbox (
  tenant_id uuid NOT NULL,
  source_id text NOT NULL CHECK (
    source_id ~ '^[a-z0-9][a-z0-9_-]{2,63}$'
  ),
  event_evidence_hmac text NOT NULL CHECK (
    event_evidence_hmac ~ '^[0-9a-f]{64}$'
  ),
  prospect_id uuid NOT NULL,
  source_event text NOT NULL CHECK (
    source_event IN (
      'mautic.form_on_submit',
      'mautic.email_on_open',
      'mautic.lead_channel_subscription_changed'
    )
  ),
  review_signal text NOT NULL CHECK (
    review_signal IN (
      'SUPPRESSION_REVIEW_REQUIRED',
      'CONTACTABILITY_REVIEW_NOT_CONSENT',
      'FORM_SUBMISSION_REVIEW_NOT_CONSENT',
      'LOW_CONFIDENCE_EMAIL_OPEN_REVIEW',
      'STALE_OR_UNVERIFIED_EVENT_REVIEW'
    )
  ),
  timestamp_state text NOT NULL CHECK (
    timestamp_state IN (
      'RECENT_OBSERVED','UNVERIFIED',
      'FUTURE_UNVERIFIED','STALE_OVER_30_DAYS'
    )
  ),
  journey_segment text NOT NULL CHECK (
    journey_segment IN (
      'contact_hold','fulfilment_review','awaiting_payment_review',
      'proposal_review','engaged_conversation_review',
      'unqualified_evidence_review'
    )
  ),
  review_state text NOT NULL DEFAULT 'REVIEW_ONLY'
    CHECK (review_state='REVIEW_ONLY'),
  execution_authority text NOT NULL DEFAULT 'none'
    CHECK (execution_authority='none'),
  send_authorized boolean NOT NULL DEFAULT false
    CHECK (send_authorized=false),
  received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY (tenant_id,source_id,event_evidence_hmac)
);

ALTER TABLE public.empire_crm_mautic_event_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_crm_mautic_event_inbox FORCE ROW LEVEL SECURITY;

REVOKE ALL ON public.empire_crm_mautic_event_inbox FROM PUBLIC;
REVOKE ALL ON public.empire_crm_mautic_event_inbox FROM
  empiredb_app, empiredb_readonly, empiredb_tenant_reader,
  empire_revenue_crm_reader, empire_revenue_crm_journey_writer;

CREATE POLICY mautic_inbox_tenant_select
 ON public.empire_crm_mautic_event_inbox FOR SELECT
 TO empire_mautic_crm_inbox_writer
 USING (
   tenant_id=public.empire_current_tenant_id()
   AND public.empire_current_tenant_id() IS NOT NULL
 );

CREATE POLICY mautic_inbox_tenant_insert
 ON public.empire_crm_mautic_event_inbox FOR INSERT
 TO empire_mautic_crm_inbox_writer
 WITH CHECK (
   tenant_id=public.empire_current_tenant_id()
   AND public.empire_current_tenant_id() IS NOT NULL
   AND review_state='REVIEW_ONLY'
   AND execution_authority='none'
   AND send_authorized=false
 );

GRANT USAGE ON SCHEMA public TO empire_mautic_crm_inbox_writer;
GRANT EXECUTE ON FUNCTION public.empire_current_tenant_id()
 TO empire_mautic_crm_inbox_writer;
GRANT SELECT,INSERT ON public.empire_crm_mautic_event_inbox
 TO empire_mautic_crm_inbox_writer;

COMMENT ON TABLE public.empire_crm_mautic_event_inbox IS
 'Tenant-bound, PII-free verified Mautic signals. Append-only REVIEW_ONLY '
 'inbox; cannot imply consent or execute workflow, payment or sending. '
 'Tenant comes from trusted session_user, never HTTP headers.';
COMMIT;
