-- Empire Analytics source taxonomy v2 — HELD, NOT A PRODUCTION DEPLOYMENT.
-- Must be reviewed and signed by the original Privacy/Website/EmpireDB owners.
-- This is a first-party analytics channel constraint extension, NOT a tag,
-- lead/call collector, login/role grant, cookie, CRM link or payment change.
-- Apply ONLY via a separately approved DBA migration (never on boot).
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_analytics_fixture') THEN
   RAISE EXCEPTION 'ANALYTICS075_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
     AND NOT rolsuper AND NOT rolbypassrls
 ) THEN RAISE EXCEPTION 'ANALYTICS075_UNSAFE_MIGRATOR'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
   WHERE n.nspname='public' AND c.relname='empire_analytics_sessions'
     AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity
     AND r.rolname='empiredb_migrator'
 ) THEN RAISE EXCEPTION 'ANALYTICS075_EXISTING_SESSION_OWNER_OR_RLS_UNVERIFIED'; END IF;
 -- Erasure/retention capability must have been installed and examined BEFORE
 -- extending the scope of data potentially stored by this schema.
 IF to_regclass('public.empire_analytics_erasure_audit') IS NULL
    OR to_regprocedure('public.empire_analytics_erase_session(uuid,text,text,text,text)') IS NULL
 THEN RAISE EXCEPTION 'ANALYTICS075_ERASURE_OWNER_NOT_READY'; END IF;
 IF EXISTS (
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_analytics_maintenance_login' AND rolcanlogin
 ) THEN RAISE EXCEPTION 'ANALYTICS075_EXISTING_MAINTENANCE_LOGIN_REVIEW'; END IF;
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_constraint
   WHERE conrelid='public.empire_analytics_sessions'::regclass
     AND conname='empire_analytics_sessions_acquisition_channel_check'
     AND contype='c' AND convalidated
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%organic_search%'
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%organic_social%'
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%unknown%'
 ) OR NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_constraint
   WHERE conrelid='public.empire_analytics_sessions'::regclass
     -- PostgreSQL names a cross-column CHECK without a column suffix.
     AND conname='empire_analytics_sessions_check'
     AND contype='c' AND convalidated
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%source_evidence_kind%'
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%server_observed_direct%'
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%server_verified_referral%'
     AND pg_catalog.pg_get_constraintdef(oid) LIKE '%signed_campaign_binding%'
 ) THEN RAISE EXCEPTION 'ANALYTICS075_V1_BASE_CONSTRAINTS_CHANGED'; END IF;
 IF EXISTS (
   SELECT 1 FROM pg_catalog.pg_constraint
   WHERE conrelid='public.empire_analytics_sessions'::regclass
     AND conname IN ('empire_analytics_source_channel_v2_check',
                     'empire_analytics_source_evidence_v2_check')
 ) THEN RAISE EXCEPTION 'ANALYTICS075_V2_ALREADY_PRESENT'; END IF;
END;
$guard$;

SET LOCAL ROLE empiredb_migrator;

ALTER TABLE public.empire_analytics_sessions
 ADD CONSTRAINT empire_analytics_source_channel_v2_check CHECK (
  acquisition_channel IN (
    'direct','organic_search','organic_social','referral','email','unknown',
    'paid_search','paid_social','affiliate_partner','publisher_referral','organic_video'
  )
 ) NOT VALID;
ALTER TABLE public.empire_analytics_sessions
 ADD CONSTRAINT empire_analytics_source_evidence_v2_check CHECK (
  (acquisition_channel='direct' AND source_evidence_kind='server_observed_direct')
  OR (acquisition_channel IN (
      'organic_search','organic_social','referral','organic_video'
  ) AND source_evidence_kind='server_verified_referral')
  OR (acquisition_channel IN (
      'email','paid_search','paid_social'
  ) AND source_evidence_kind='signed_campaign_binding')
  OR (acquisition_channel IN (
      'affiliate_partner','publisher_referral'
  ) AND source_evidence_kind='signed_partner_binding')
  OR (acquisition_channel='unknown' AND source_evidence_kind='server_unknown')
 ) NOT VALID;

-- Explicit VALIDATE verifies existing row compatibility before any v1
-- constraints are dropped. The transaction is atomic on failure.
ALTER TABLE public.empire_analytics_sessions
 VALIDATE CONSTRAINT empire_analytics_source_channel_v2_check;
ALTER TABLE public.empire_analytics_sessions
 VALIDATE CONSTRAINT empire_analytics_source_evidence_v2_check;

ALTER TABLE public.empire_analytics_sessions
 DROP CONSTRAINT empire_analytics_sessions_acquisition_channel_check;
ALTER TABLE public.empire_analytics_sessions
 DROP CONSTRAINT empire_analytics_sessions_check;

-- No DML, writer role, runtime RLS policy, public execute, event endpoint,
-- collector, cookie, payout, conversion or migration runner installed here.
-- A separate original-owner release is required for authenticated source
-- binding, privacy/consent, erasure and a scoped runtime writer capability.
COMMIT;
