-- EmpireOS Predictive Cloud 066 — PREPARED HELD source-rights evidence.
-- NOT a licence validator, not a tenant auth source, not real data admission.
-- The only exposed decision is HELD. Never install without EmpireDB owner gate.
BEGIN;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='3s';
DO $guard$
BEGIN
 IF current_database() NOT IN ('empiredb','empire_v4_outbox_fixture') THEN
   RAISE EXCEPTION 'V4_066_WRONG_DATABASE';
 END IF;
 IF NOT EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper
    AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) OR EXISTS (
   SELECT 1 FROM pg_catalog.pg_auth_members
   WHERE roleid=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='empiredb_migrator')
 ) THEN RAISE EXCEPTION 'V4_066_RESTRICTED_OWNER_REQUIRED';
 END IF;
 IF NOT EXISTS(
   SELECT 1 FROM pg_catalog.pg_roles
   WHERE rolname='empire_predictive_rights_reader' AND NOT rolcanlogin
    AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN RAISE EXCEPTION 'V4_066_NOLOGIN_READER_CAPABILITY_REQUIRED';
 END IF;
 IF pg_catalog.to_regclass('public.empire_predictive_source_rights_candidate_held') IS NOT NULL
 OR pg_catalog.to_regclass('public.empire_predictive_source_revocations_held') IS NOT NULL
 OR pg_catalog.to_regprocedure('public.read_empire_predictive_source_rights_held(uuid,text,text)') IS NOT NULL
 THEN RAISE EXCEPTION 'V4_066_EXISTING_RIGHTS_CONTRACT_REQUIRES_RECONCILIATION';
 END IF;
END;
$guard$;
SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.empire_predictive_source_rights_candidate_held(
 tenant_id uuid NOT NULL CHECK (tenant_id <> '00000000-0000-0000-0000-000000000000'::uuid),
 source_evidence_digest text NOT NULL CHECK(source_evidence_digest ~ '^[a-f0-9]{64}$'),
 permitted_purpose text NOT NULL CHECK (permitted_purpose='PRIVATE_PREDICTIVE_RESEARCH_ONLY'),
 rights_document_digest text NOT NULL CHECK(rights_document_digest ~ '^[a-f0-9]{64}$'),
 evidence_observed_at timestamptz NOT NULL,
 valid_until timestamptz NOT NULL,
 source_review_state text NOT NULL DEFAULT 'PENDING'
  CHECK(source_review_state IN ('PENDING','CANDIDATE_REVIEWED')),
 execution_authority text NOT NULL DEFAULT 'none' CHECK(execution_authority='none'),
 recorded_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY (tenant_id,source_evidence_digest,permitted_purpose),
 CHECK(valid_until > evidence_observed_at)
);

CREATE TABLE public.empire_predictive_source_revocations_held(
 tenant_id uuid NOT NULL,
 source_evidence_digest text NOT NULL,
 permitted_purpose text NOT NULL,
 reason_digest text NOT NULL CHECK(reason_digest ~ '^[a-f0-9]{64}$'),
 revoked_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp(),
 PRIMARY KEY (tenant_id,source_evidence_digest,permitted_purpose),
 FOREIGN KEY (tenant_id,source_evidence_digest,permitted_purpose)
  REFERENCES public.empire_predictive_source_rights_candidate_held
  (tenant_id,source_evidence_digest,permitted_purpose) ON DELETE RESTRICT
);

ALTER TABLE public.empire_predictive_source_rights_candidate_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_rights_candidate_held FORCE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_revocations_held ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.empire_predictive_source_revocations_held FORCE ROW LEVEL SECURITY;
CREATE POLICY empire_predictive_source_rights_owner_held
 ON public.empire_predictive_source_rights_candidate_held FOR ALL
 TO empiredb_migrator USING (true) WITH CHECK (true);
CREATE POLICY empire_predictive_source_revocation_owner_held
 ON public.empire_predictive_source_revocations_held FOR ALL
 TO empiredb_migrator USING (true) WITH CHECK (true);

-- Even the owner may never silently rewrite old review or revocation history.
CREATE FUNCTION public.reject_empire_predictive_source_mutation_held()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public AS $immut$
BEGIN
 RAISE EXCEPTION 'V4_066_APPEND_ONLY_SOURCE_HISTORY';
END;
$immut$;
CREATE TRIGGER empire_predictive_source_candidate_immutable_066
 BEFORE UPDATE OR DELETE ON public.empire_predictive_source_rights_candidate_held
 FOR EACH ROW EXECUTE FUNCTION public.reject_empire_predictive_source_mutation_held();
CREATE TRIGGER empire_predictive_source_revocation_immutable_066
 BEFORE UPDATE OR DELETE ON public.empire_predictive_source_revocations_held
 FOR EACH ROW EXECUTE FUNCTION public.reject_empire_predictive_source_mutation_held();

-- Bound read-only function: NO table SELECT granted to any application login.
-- Only later separately provisioned login may execute via the NOLOGIN capability.
-- Both attested and authorised booleans stay false, even for REVIEWED candidate.
CREATE FUNCTION public.read_empire_predictive_source_rights_held(
 p_tenant uuid,p_source_digest text,p_purpose text
) RETURNS TABLE(
 decision text,
 tenant_id uuid,
 source_evidence_digest text,
 permitted_purpose text,
 revocation_present boolean,
 real_rights_independently_verified boolean,
 source_admission_authorized boolean,
 execution_authority text
) LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = ''
AS $rights$
DECLARE
 candidate public.empire_predictive_source_rights_candidate_held%ROWTYPE;
 revoked boolean;
 selected_decision text;
BEGIN
 IF session_user <> 'empire_predictive_rights_login' THEN
   RAISE EXCEPTION 'V4_066_UNTRUSTED_READER_LOGIN';
 END IF;
 IF p_tenant IS NULL OR p_tenant='00000000-0000-0000-0000-000000000000'::uuid
  OR p_source_digest IS NULL OR p_source_digest !~ '^[a-f0-9]{64}$'
  OR p_purpose IS NULL OR p_purpose <> 'PRIVATE_PREDICTIVE_RESEARCH_ONLY' THEN
  RAISE EXCEPTION 'V4_066_INVALID_SCOPED_RIGHTS_QUERY';
 END IF;
 SELECT * INTO candidate
 FROM public.empire_predictive_source_rights_candidate_held AS c
 WHERE c.tenant_id=p_tenant AND c.source_evidence_digest=p_source_digest
 AND c.permitted_purpose=p_purpose;
 IF NOT FOUND THEN
   selected_decision := 'NO_SOURCE_RIGHTS_HELD';
   revoked := false;
 ELSE
   SELECT EXISTS(
     SELECT 1 FROM public.empire_predictive_source_revocations_held AS r
     WHERE r.tenant_id=p_tenant AND r.source_evidence_digest=p_source_digest
     AND r.permitted_purpose=p_purpose
   ) INTO revoked;
   selected_decision := CASE
     WHEN revoked THEN 'REVOKED_HELD'
     WHEN candidate.valid_until <= pg_catalog.statement_timestamp()
       THEN 'EXPIRED_HELD'
     WHEN candidate.evidence_observed_at > pg_catalog.statement_timestamp()
       THEN 'FUTURE_EVIDENCE_HELD'
     WHEN candidate.source_review_state='CANDIDATE_REVIEWED'
       THEN 'CANDIDATE_REVIEW_HELD'
     ELSE 'PENDING_HELD'
   END;
 END IF;
 RETURN QUERY SELECT
  selected_decision,p_tenant,p_source_digest,p_purpose,revoked,
  false,false,'none'::text;
END;
$rights$;

REVOKE ALL ON TABLE public.empire_predictive_source_rights_candidate_held FROM PUBLIC;
REVOKE ALL ON TABLE public.empire_predictive_source_revocations_held FROM PUBLIC;
REVOKE ALL ON FUNCTION public.reject_empire_predictive_source_mutation_held() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.read_empire_predictive_source_rights_held(uuid,text,text)
 FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_empire_predictive_source_rights_held(uuid,text,text)
 TO empire_predictive_rights_reader;
COMMENT ON TABLE public.empire_predictive_source_rights_candidate_held IS
 'PREPARED HELD rights evidence only. A review row does not authenticate a licence or permit business action.';
COMMENT ON FUNCTION public.read_empire_predictive_source_rights_held(uuid,text,text) IS
 'Bounded dedicated session_user read. Every result HELD, never source or financial authority.';
COMMIT;
