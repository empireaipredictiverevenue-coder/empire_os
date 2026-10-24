-- EmpireOS Predictive Cloud 065: HELD advisory stream replay audit, not a consumer.
-- PREPARED ONLY: do not run on production EmpireDB until independent approval.
-- Requires held 064 revision/outbox; owner-only synthetic receipt research.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v4_outbox_fixture') THEN
  RAISE EXCEPTION 'V4_065_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
   AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
   AND NOT rolcreatedb AND NOT rolcreaterole
 ) OR EXISTS(
  SELECT 1 FROM pg_catalog.pg_auth_members
  WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
 ) THEN
  RAISE EXCEPTION 'V4_065_RESTRICTED_OWNER_REQUIRED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_v4_watermarks_held') IS NULL
  OR pg_catalog.to_regclass('public.empire_predictive_v4_outbox_held') IS NULL THEN
  RAISE EXCEPTION 'V4_065_ORIGINAL_HELD_OUTBOX_REQUIRED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_v4_advisory_receipts_held') IS NOT NULL
 OR pg_catalog.to_regprocedure(
  'public.audit_empire_predictive_v4_stream_observation_held(uuid,text,text)'
 ) IS NOT NULL THEN
  RAISE EXCEPTION 'V4_065_EXISTING_RECEIPTS_REQUIRES_REVIEW';
 END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;

-- Composite tenant/event identity remains enforced even for privileged direct inserts.
CREATE UNIQUE INDEX empire_predictive_v4_outbox_tenant_event_065
 ON public.empire_predictive_v4_outbox_held(tenant_id,event_digest);

CREATE TABLE public.empire_predictive_v4_advisory_receipts_held (
 tenant_id uuid NOT NULL,
 event_digest text NOT NULL CHECK (event_digest ~ '^[a-f0-9]{64}$'),
 first_stream_id text NOT NULL CHECK (first_stream_id ~ '^[0-9]{1,20}-[0-9]{1,20}$'),
 decision text NOT NULL CHECK (decision IN (
  'WITHDRAWN_BLOCKED','SUPERSEDED_BLOCKED','UNVERIFIED_BLOCKED')),
 receipt_state text NOT NULL DEFAULT 'HELD' CHECK (receipt_state='HELD'),
 redis_acknowledged boolean NOT NULL DEFAULT false CHECK (NOT redis_acknowledged),
 action_executed boolean NOT NULL DEFAULT false CHECK (NOT action_executed),
 source_authorized boolean NOT NULL DEFAULT false CHECK (NOT source_authorized),
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY(tenant_id,event_digest),
 UNIQUE(tenant_id,first_stream_id),
 FOREIGN KEY(tenant_id,event_digest)
  REFERENCES public.empire_predictive_v4_outbox_held(tenant_id,event_digest)
  ON DELETE RESTRICT
);
ALTER TABLE public.empire_predictive_v4_advisory_receipts_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_v4_advisory_receipts_held FORCE ROW LEVEL SECURITY;
CREATE POLICY empire_predictive_v4_receipts_owner_held
 ON public.empire_predictive_v4_advisory_receipts_held FOR ALL TO empiredb_migrator
 USING (true) WITH CHECK (true);

CREATE FUNCTION public.audit_empire_predictive_v4_stream_observation_held(
 p_tenant uuid,p_event_digest text,p_stream_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public
AS $audit$
DECLARE
 observed RECORD;
 decision text;
 inserted text;
 existing_event text;
BEGIN
 IF p_tenant IS NULL OR p_tenant='00000000-0000-0000-0000-000000000000'::uuid
 OR p_event_digest IS NULL OR p_event_digest !~ '^[a-f0-9]{64}$'
 OR p_stream_id IS NULL OR p_stream_id !~ '^[0-9]{1,20}-[0-9]{1,20}$' THEN
  RAISE EXCEPTION 'V4_065_INVALID_HELD_OBSERVATION';
 END IF;
 SELECT o.event_kind,o.revision,o.delivery_state,o.execution_authority,
   w.latest_revision,w.withdrawn,w.source_review_state
 INTO observed
 FROM public.empire_predictive_v4_outbox_held AS o
 JOIN public.empire_predictive_v4_watermarks_held AS w
  USING(tenant_id,sector,entity_digest)
 WHERE o.tenant_id=p_tenant AND o.event_digest=p_event_digest
 FOR SHARE OF o,w;
 IF NOT FOUND THEN
  RAISE EXCEPTION 'V4_065_UNKNOWN_TENANT_EVENT';
 END IF;
 IF observed.delivery_state <> 'HELD'
  OR observed.execution_authority <> 'none'
  OR observed.source_review_state <> 'UNVERIFIED' THEN
  RAISE EXCEPTION 'V4_065_AUTHORITY_STATE_NOT_HELD';
 END IF;
 IF observed.withdrawn OR observed.event_kind='WITHDRAWN' THEN
  decision := 'WITHDRAWN_BLOCKED';
 ELSIF observed.revision < observed.latest_revision THEN
  decision := 'SUPERSEDED_BLOCKED';
 ELSIF observed.revision = observed.latest_revision THEN
  decision := 'UNVERIFIED_BLOCKED';
 ELSE
  RAISE EXCEPTION 'V4_065_FUTURE_REVISION_REFUSED';
 END IF;
 SELECT r.event_digest INTO existing_event
 FROM public.empire_predictive_v4_advisory_receipts_held r
 WHERE r.tenant_id=p_tenant AND r.first_stream_id=p_stream_id;
 IF FOUND AND existing_event <> p_event_digest THEN
  RAISE EXCEPTION 'V4_065_STREAM_ID_COLLISION';
 END IF;
 -- Unique (tenant,event_digest) is the durable replay fence:
 -- distinct Redis XADD message IDs for the same event do not create new effects.
 INSERT INTO public.empire_predictive_v4_advisory_receipts_held
 (tenant_id,event_digest,first_stream_id,decision)
 VALUES(p_tenant,p_event_digest,p_stream_id,decision)
 ON CONFLICT (tenant_id,event_digest) DO NOTHING
 RETURNING event_digest INTO inserted;
 IF inserted IS NULL THEN
  RETURN jsonb_build_object('status','DUPLICATE_HELD',
   'redis_acknowledged',false,'action_executed',false,
   'source_authorized',false,'execution_authority','none');
 END IF;
 RETURN jsonb_build_object('status','FIRST_OBSERVATION_HELD',
  'decision',decision,'redis_acknowledged',false,
  'action_executed',false,'source_authorized',false,
  'execution_authority','none');
END;
$audit$;

CREATE FUNCTION public.reject_empire_predictive_v4_advisory_receipt_mutation_held()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $immutable$
BEGIN
 RAISE EXCEPTION 'V4_065_APPEND_ONLY_RECEIPTS';
END;
$immutable$;
CREATE TRIGGER empire_predictive_v4_receipt_no_mutation_held
 BEFORE UPDATE OR DELETE ON public.empire_predictive_v4_advisory_receipts_held
 FOR EACH ROW EXECUTE FUNCTION public.reject_empire_predictive_v4_advisory_receipt_mutation_held();

REVOKE ALL ON TABLE public.empire_predictive_v4_advisory_receipts_held FROM PUBLIC;
REVOKE ALL ON FUNCTION public.audit_empire_predictive_v4_stream_observation_held(
 uuid,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reject_empire_predictive_v4_advisory_receipt_mutation_held()
 FROM PUBLIC;
COMMENT ON TABLE public.empire_predictive_v4_advisory_receipts_held IS
 'HELD fixture-only replay audit for proposed advisory events. NOT a live Redis ACK, publish receipt, sender, commercial or financial ledger.';
COMMIT;
