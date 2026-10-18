-- EmpireDB 052: isolated historical Workspace SENT evidence (NOT outbound intents).
-- STAGED ONLY. Requires separate founder-approved privileged DBA schema action.
-- Never run on application boot, cron, or ordinary agents.
-- No email send, retrospective approval, CRM contact, payment or customer row.
-- The existing canonical outbound_intents lifecycle remains entirely unchanged.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';

DO $scope$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'HIST052_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empiredb_migrator' AND NOT rolcanlogin
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_roles
    WHERE rolname='empire_closer_observer' AND NOT rolsuper AND NOT rolbypassrls
  ) THEN
    RAISE EXCEPTION 'HIST052_EXISTING_ROLE_BOUNDARY_UNVERIFIED';
  END IF;
  IF pg_catalog.to_regclass('public.workspace_historical_sent_receipts') IS NOT NULL
     OR pg_catalog.to_regprocedure(
       'public.guard_workspace_historical_receipt_immutable()'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'HIST052_EXISTING_OBJECT_REVIEW_REQUIRED';
  END IF;
END;
$scope$;

SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.workspace_historical_sent_receipts (
    original_provider_message_id text PRIMARY KEY,
    gmail_thread_id text NOT NULL UNIQUE,
    provider_mailbox_class text NOT NULL
      DEFAULT 'EMPIRE_WORKSPACE_NOT_PERSONAL_GMAIL',
    original_recipient_sha256 text NOT NULL,
    original_sent_at timestamptz NOT NULL,
    source_scanned_at timestamptz NOT NULL,
    evidence_sha256 text NOT NULL UNIQUE,
    source_kind text NOT NULL
      DEFAULT 'AUTHENTICATED_GMAIL_ORIGINAL_SENT_METADATA',
    linkage_state text NOT NULL DEFAULT 'UNBOUND_EXTERNAL_SENT_OBSERVED',
    historical_approval_attested boolean NOT NULL DEFAULT false,
    crm_contact_bound boolean NOT NULL DEFAULT false,
    customer_revenue_verified boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT workspace_historical_provider_message_check
      CHECK (original_provider_message_id ~ '^[a-f0-9]{16,32}$'),
    CONSTRAINT workspace_historical_thread_check
      CHECK (gmail_thread_id ~ '^[a-f0-9]{16,32}$'),
    CONSTRAINT workspace_historical_mailbox_check
      CHECK (provider_mailbox_class='EMPIRE_WORKSPACE_NOT_PERSONAL_GMAIL'),
    CONSTRAINT workspace_historical_recipient_hash_check
      CHECK (original_recipient_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT workspace_historical_evidence_hash_check
      CHECK (evidence_sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT workspace_historical_source_kind_check
      CHECK (source_kind='AUTHENTICATED_GMAIL_ORIGINAL_SENT_METADATA'),
    CONSTRAINT workspace_historical_linkage_state_check
      CHECK (linkage_state='UNBOUND_EXTERNAL_SENT_OBSERVED'),
    CONSTRAINT workspace_historical_no_retrospective_approval
      CHECK (historical_approval_attested IS FALSE),
    CONSTRAINT workspace_historical_no_unproven_crm
      CHECK (crm_contact_bound IS FALSE),
    CONSTRAINT workspace_historical_no_fake_revenue
      CHECK (customer_revenue_verified IS FALSE),
    CONSTRAINT workspace_historical_time_order_check
      CHECK (original_sent_at <= source_scanned_at),
    CONSTRAINT workspace_historical_time_not_future
      CHECK (original_sent_at < created_at)
);

-- No UPDATE or DELETE can rewrite what the original provider observed.
CREATE FUNCTION public.guard_workspace_historical_receipt_immutable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path=''
AS $guard$
BEGIN
  RAISE EXCEPTION 'HIST052_APPEND_ONLY_RECEIPT_NO_MUTATION';
END;
$guard$;

CREATE TRIGGER workspace_historical_receipts_append_only
BEFORE UPDATE OR DELETE ON public.workspace_historical_sent_receipts
FOR EACH ROW EXECUTE FUNCTION
  public.guard_workspace_historical_receipt_immutable();

REVOKE ALL ON TABLE public.workspace_historical_sent_receipts FROM PUBLIC;
ALTER TABLE public.workspace_historical_sent_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_historical_sent_receipts FORCE ROW LEVEL SECURITY;

-- SELECT-only from the existing private Founder read API observer role.
-- No INSERT/UPDATE/DELETE for the app or CRM identities.
CREATE POLICY workspace_historical_closer_readonly
ON public.workspace_historical_sent_receipts
FOR SELECT TO empire_closer_observer USING (true);
GRANT SELECT ON TABLE public.workspace_historical_sent_receipts
TO empire_closer_observer;

DO $final_guard$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_catalog.pg_class c
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND c.relname='workspace_historical_sent_receipts'
   AND c.relrowsecurity AND c.relforcerowsecurity
 ) THEN RAISE EXCEPTION 'HIST052_RLS_NOT_FORCED'; END IF;
 IF pg_catalog.has_table_privilege(
     'empire_closer_observer','public.workspace_historical_sent_receipts','INSERT'
   ) OR pg_catalog.has_table_privilege(
     'empire_closer_observer','public.workspace_historical_sent_receipts','UPDATE'
   ) OR pg_catalog.has_table_privilege(
     'empire_closer_observer','public.workspace_historical_sent_receipts','DELETE'
   ) THEN
   RAISE EXCEPTION 'HIST052_NO_CLOSER_MUTATION_PERMITTED';
 END IF;
END;
$final_guard$;
COMMIT;
