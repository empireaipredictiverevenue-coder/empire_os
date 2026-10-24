-- EmpireOS Predictive Cloud 064 — held, source-UNVERIFIED projection/outbox.
-- PREPARED ONLY; do not apply to production without DB/Security owner approval.
-- No real tenant membership, real source-rights attestation, Redis IO, routing or money.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v4_outbox_fixture') THEN
  RAISE EXCEPTION 'V4_064_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator'
    AND NOT rolcanlogin AND NOT rolsuper AND NOT rolbypassrls
    AND NOT rolcreatedb AND NOT rolcreaterole
 ) OR EXISTS (
  SELECT 1 FROM pg_catalog.pg_auth_members
  WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
 ) THEN
  RAISE EXCEPTION 'V4_064_RESTRICTED_OWNER_REQUIRED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_v4_watermarks_held') IS NOT NULL
 OR pg_catalog.to_regclass('public.empire_predictive_v4_outbox_held') IS NOT NULL
 OR pg_catalog.to_regprocedure(
  'public.stage_empire_predictive_v4_projection_held(uuid,text,text,text,bigint,text,text)'
 ) IS NOT NULL THEN
  RAISE EXCEPTION 'V4_064_EXISTING_CONTRACT_REQUIRES_REVIEW';
 END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.empire_predictive_v4_watermarks_held (
 tenant_id uuid NOT NULL CHECK (tenant_id <> '00000000-0000-0000-0000-000000000000'::uuid),
 sector text NOT NULL CHECK (sector IN (
  'roofing','hvac','solar','dental','legal','b2b_saas',
  'ecommerce','logistics','heat_pumps','storm')),
 entity_digest text NOT NULL CHECK (entity_digest ~ '^[a-f0-9]{64}$'),
 source_evidence_digest text NOT NULL CHECK (source_evidence_digest ~ '^[a-f0-9]{64}$'),
 latest_revision bigint NOT NULL CHECK (latest_revision BETWEEN 1 AND 1000000000),
 withdrawn boolean NOT NULL DEFAULT false,
 source_review_state text NOT NULL DEFAULT 'UNVERIFIED'
  CHECK (source_review_state='UNVERIFIED'),
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY (tenant_id,sector,entity_digest)
);

CREATE TABLE public.empire_predictive_v4_outbox_held (
 event_digest text PRIMARY KEY CHECK (event_digest ~ '^[a-f0-9]{64}$'),
 tenant_id uuid NOT NULL,
 sector text NOT NULL,
 entity_digest text NOT NULL,
 source_evidence_digest text NOT NULL CHECK (source_evidence_digest ~ '^[a-f0-9]{64}$'),
 revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 1000000000),
 event_kind text NOT NULL CHECK (event_kind IN ('OBSERVED','WITHDRAWN')),
 delivery_state text NOT NULL DEFAULT 'HELD' CHECK (delivery_state='HELD'),
 execution_authority text NOT NULL DEFAULT 'none' CHECK (execution_authority='none'),
 created_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 FOREIGN KEY (tenant_id,sector,entity_digest)
  REFERENCES public.empire_predictive_v4_watermarks_held (tenant_id,sector,entity_digest)
  ON DELETE RESTRICT,
 UNIQUE(tenant_id,sector,entity_digest,revision)
);

ALTER TABLE public.empire_predictive_v4_watermarks_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_v4_watermarks_held FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_v4_outbox_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_v4_outbox_held FORCE ROW LEVEL SECURITY;
CREATE POLICY empire_predictive_v4_watermark_owner_held
 ON public.empire_predictive_v4_watermarks_held FOR ALL TO empiredb_migrator
 USING (true) WITH CHECK (true);
CREATE POLICY empire_predictive_v4_outbox_owner_held
 ON public.empire_predictive_v4_outbox_held FOR ALL TO empiredb_migrator
 USING (true) WITH CHECK (true);

CREATE FUNCTION public.stage_empire_predictive_v4_projection_held(
 p_tenant uuid,p_sector text,p_entity_digest text,p_source_digest text,
 p_revision bigint,p_event_digest text,p_kind text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog,public
AS $body$
DECLARE
 prior public.empire_predictive_v4_outbox_held%ROWTYPE;
 accepted bigint;
BEGIN
 IF p_tenant IS NULL OR p_tenant='00000000-0000-0000-0000-000000000000'::uuid
  OR p_sector IS NULL OR p_sector NOT IN (
   'roofing','hvac','solar','dental','legal','b2b_saas',
   'ecommerce','logistics','heat_pumps','storm')
  OR p_entity_digest IS NULL OR p_entity_digest !~ '^[a-f0-9]{64}$'
  OR p_source_digest IS NULL OR p_source_digest !~ '^[a-f0-9]{64}$'
  OR p_event_digest IS NULL OR p_event_digest !~ '^[a-f0-9]{64}$'
  OR p_revision IS NULL OR p_revision NOT BETWEEN 1 AND 1000000000
  OR p_kind IS NULL OR p_kind NOT IN ('OBSERVED','WITHDRAWN') THEN
  RAISE EXCEPTION 'V4_064_INVALID_HELD_EVENT';
 END IF;
 SELECT * INTO prior FROM public.empire_predictive_v4_outbox_held
  WHERE event_digest=p_event_digest;
 IF FOUND THEN
  IF prior.tenant_id=p_tenant AND prior.sector=p_sector
   AND prior.entity_digest=p_entity_digest
   AND prior.source_evidence_digest=p_source_digest
   AND prior.revision=p_revision AND prior.event_kind=p_kind THEN
   RETURN jsonb_build_object('status','HELD_DUPLICATE',
    'execution_authority','none','redis_publish_authorized',false);
  END IF;
  RAISE EXCEPTION 'V4_064_EVENT_IDENTITY_COLLISION';
 END IF;
 -- Atomic compare-and-swap on canonical tenant+entity key, including absent-row race.
 -- A withdrawal is terminal for this research contract: no stale or future revival.
 INSERT INTO public.empire_predictive_v4_watermarks_held
  (tenant_id,sector,entity_digest,source_evidence_digest,latest_revision,withdrawn)
 VALUES(p_tenant,p_sector,p_entity_digest,p_source_digest,p_revision,p_kind='WITHDRAWN')
 ON CONFLICT (tenant_id,sector,entity_digest) DO UPDATE SET
  source_evidence_digest=EXCLUDED.source_evidence_digest,
  latest_revision=EXCLUDED.latest_revision,
  withdrawn=EXCLUDED.withdrawn,
  recorded_at=pg_catalog.clock_timestamp()
 WHERE NOT public.empire_predictive_v4_watermarks_held.withdrawn
  AND public.empire_predictive_v4_watermarks_held.latest_revision < EXCLUDED.latest_revision
 RETURNING latest_revision INTO accepted;
 IF accepted IS NULL THEN
  RAISE EXCEPTION 'V4_064_STALE_OR_WITHDRAWN';
 END IF;
 -- Failure to insert the event also rolls back the watermark: same transaction.
 INSERT INTO public.empire_predictive_v4_outbox_held(
  event_digest,tenant_id,sector,entity_digest,source_evidence_digest,revision,event_kind
 ) VALUES(
  p_event_digest,p_tenant,p_sector,p_entity_digest,p_source_digest,p_revision,p_kind
 );
 RETURN jsonb_build_object('status','HELD_STAGED',
  'revision',accepted,'withdrawn',p_kind='WITHDRAWN',
  'source_review_state','UNVERIFIED','outbox_delivery_state','HELD',
  'execution_authority','none','redis_publish_authorized',false);
END;
$body$;

-- Even the held owner should not silently rewrite/delete staged event history.
CREATE FUNCTION public.reject_empire_predictive_v4_outbox_mutation_held()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $immutable$
BEGIN
 RAISE EXCEPTION 'V4_064_APPEND_ONLY_OUTBOX';
END;
$immutable$;
CREATE TRIGGER empire_predictive_v4_outbox_no_mutation_held
 BEFORE UPDATE OR DELETE ON public.empire_predictive_v4_outbox_held
 FOR EACH ROW EXECUTE FUNCTION public.reject_empire_predictive_v4_outbox_mutation_held();
REVOKE ALL ON FUNCTION public.reject_empire_predictive_v4_outbox_mutation_held() FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_predictive_v4_watermarks_held FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_predictive_v4_outbox_held FROM PUBLIC;
REVOKE ALL ON FUNCTION public.stage_empire_predictive_v4_projection_held(
 uuid,text,text,text,bigint,text,text) FROM PUBLIC;
COMMENT ON TABLE public.empire_predictive_v4_watermarks_held IS
 'HELD owner-only synthetic projection watermark. Source authority/tenant binding NOT verified.';
COMMENT ON TABLE public.empire_predictive_v4_outbox_held IS
 'HELD owner-only unique OBSERVE/withdrawal proposals. No publication, delivery, payment or CRM authority.';
COMMIT;
