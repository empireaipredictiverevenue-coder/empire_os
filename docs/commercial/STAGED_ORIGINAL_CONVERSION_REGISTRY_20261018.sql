-- STAGED ONLY: EmpireDB original conversion-probability register.
-- DO NOT auto-apply or put into migration runner. Dedicated DBA review,
-- tenant resolver authority check and explicit founder DDL approval required.
-- This is NOT the existing directional predictive_forecasts registry.
-- No LOGIN, credentials, tenant membership, web endpoint, sender or job.
BEGIN;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '3s';

DO $$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'CONV_REG_WRONG_DATABASE';
  END IF;
  IF NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles
      WHERE rolname = current_user AND rolsuper
  ) THEN
    RAISE EXCEPTION 'CONV_REG_PRIVILEGED_BOOTSTRAP_REQUIRED';
  END IF;
  IF pg_catalog.to_regclass('public.original_conversion_predictions') IS NOT NULL
     OR pg_catalog.to_regprocedure(
       'public.record_original_conversion_prediction_v1(text,text,jsonb,text)'
     ) IS NOT NULL
     OR pg_catalog.to_regprocedure(
       'public.read_original_conversion_prediction_v1(text,text)'
     ) IS NOT NULL THEN
    RAISE EXCEPTION 'CONV_REG_REVIEW_EXISTING_OBJECTS';
  END IF;
  IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_roles WHERE rolname IN (
        'empire_original_conversion_prediction_writer',
        'empire_original_conversion_prediction_reader'
      )
  ) THEN
    RAISE EXCEPTION 'CONV_REG_ROLE_NAME_COLLISION';
  END IF;
  IF pg_catalog.to_regprocedure('public.empire_current_tenant_id()') IS NULL THEN
    RAISE EXCEPTION 'CONV_REG_CANONICAL_TENANT_BINDING_MISSING';
  END IF;

  CREATE ROLE empire_original_conversion_prediction_writer
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
  CREATE ROLE empire_original_conversion_prediction_reader
    NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS;
END
$$;

GRANT USAGE ON SCHEMA public TO
  empire_original_conversion_prediction_writer,
  empire_original_conversion_prediction_reader;

SET LOCAL ROLE empiredb_migrator;

CREATE TABLE public.original_conversion_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  prediction_ref text NOT NULL
    CHECK(length(prediction_ref) BETWEEN 36 AND 160),
  opportunity_key text NOT NULL CHECK(length(opportunity_key) BETWEEN 1 AND 128),
  prediction_type text NOT NULL DEFAULT 'conversion_probability'
    CHECK(prediction_type = 'conversion_probability'),
  predicted_probability numeric(12,10) NOT NULL
    CHECK(predicted_probability >= 0 AND predicted_probability <= 1),
  model_name text NOT NULL CHECK(length(model_name) BETWEEN 1 AND 128),
  model_version text NOT NULL CHECK(length(model_version) BETWEEN 1 AND 128),
  proposed_at timestamptz NOT NULL,
  horizon_until timestamptz NOT NULL,
  source_evidence jsonb NOT NULL,
  prediction_json jsonb NOT NULL,
  client_payload_sha256 text NOT NULL
    CHECK(client_payload_sha256 ~ '^[0-9a-f]{64}$'),
  -- Hash of PostgreSQL's canonical JSONB representation, independently
  -- computed in the DB. NOT a signature or proof of original issuer.
  server_payload_sha256 text NOT NULL
    CHECK(server_payload_sha256 ~ '^[0-9a-f]{64}$'),
  recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (tenant_id,prediction_ref),
  CHECK(jsonb_typeof(source_evidence) = 'array'
    AND jsonb_array_length(source_evidence) BETWEEN 1 AND 20),
  CHECK(jsonb_typeof(prediction_json) = 'object'),
  CHECK(horizon_until > proposed_at)
);

ALTER TABLE public.original_conversion_predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.original_conversion_predictions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.original_conversion_predictions FROM PUBLIC;
REVOKE ALL ON public.original_conversion_predictions FROM
  empire_original_conversion_prediction_writer,
  empire_original_conversion_prediction_reader;
REVOKE ALL ON public.original_conversion_predictions FROM service_role;
-- FORCE RLS applies even to the table owner/SECURITY DEFINER. Only the
-- dedicated migrator owner sees rows bound to the authenticated session.
-- No table permissions are granted to either runtime capability role.
CREATE POLICY original_conversion_migrator_tenant_read
ON public.original_conversion_predictions
FOR SELECT TO empiredb_migrator
USING (tenant_id = public.empire_current_tenant_id());
CREATE POLICY original_conversion_migrator_tenant_insert
ON public.original_conversion_predictions
FOR INSERT TO empiredb_migrator
WITH CHECK (tenant_id = public.empire_current_tenant_id());

CREATE FUNCTION public.reject_original_conversion_prediction_change_v1()
RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  RAISE EXCEPTION 'CONV_REG_APPEND_ONLY';
END
$$;

CREATE TRIGGER original_conversion_prediction_immutable
BEFORE UPDATE OR DELETE ON public.original_conversion_predictions
FOR EACH ROW EXECUTE FUNCTION public.reject_original_conversion_prediction_change_v1();
-- Row triggers do NOT fire on TRUNCATE. Guard against the table owner's
-- accidental or routine truncate too; a superuser still cannot be
-- cryptographically prevented from overriding a database-local audit.
CREATE TRIGGER original_conversion_prediction_truncate_guard
BEFORE TRUNCATE ON public.original_conversion_predictions
FOR EACH STATEMENT EXECUTE FUNCTION public.reject_original_conversion_prediction_change_v1();

CREATE FUNCTION public.record_original_conversion_prediction_v1(
  p_tenant text,
  p_prediction_ref text,
  p_payload jsonb,
  p_client_hash text
)
RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  current_tenant uuid := public.empire_current_tenant_id();
  existing_row public.original_conversion_predictions%ROWTYPE;
  now_at timestamptz := clock_timestamp();
  proposed timestamptz;
  horizon timestamptz;
  probability numeric;
  evidence_total bigint;
  evidence_unique bigint;
  server_hash text;
BEGIN
  IF current_tenant IS NULL OR p_tenant IS NULL
     OR p_tenant <> current_tenant::text THEN
    RAISE EXCEPTION 'CONV_REG_TENANT_NOT_AUTHENTICATED';
  END IF;
  IF jsonb_typeof(p_payload) <> 'object'
     OR (SELECT pg_catalog.count(*) FROM jsonb_object_keys(p_payload))
        <> 10
     OR p_payload->>'prediction_type' <> 'conversion_probability'
     OR p_prediction_ref IS DISTINCT FROM p_payload->>'prediction_ref'
     OR p_tenant IS DISTINCT FROM p_payload->>'tenant_id'
     OR p_prediction_ref NOT LIKE 'conversion_prediction_candidate:%'
     OR p_client_hash !~ '^[0-9a-f]{64}$'
     OR (p_payload->>'opportunity_key') IS NULL
     OR length(p_payload->>'opportunity_key') NOT BETWEEN 1 AND 128
     OR (p_payload->>'model_name') IS NULL
     OR length(p_payload->>'model_name') NOT BETWEEN 1 AND 128
     OR (p_payload->>'model_version') IS NULL
     OR length(p_payload->>'model_version') NOT BETWEEN 1 AND 128
     OR jsonb_typeof(p_payload->'predicted_probability') <> 'number'
     OR jsonb_typeof(p_payload->'evidence_refs') <> 'array'
     OR jsonb_array_length(p_payload->'evidence_refs') NOT BETWEEN 1 AND 20
     OR p_payload->>'predicted_at' IS NULL
     OR p_payload->>'horizon_until' IS NULL
     OR length(p_prediction_ref) NOT BETWEEN 36 AND 160
     OR pg_catalog.octet_length(p_payload::text) > 32768
     OR (p_payload->>'predicted_at') !~
           '^.{10,50}(Z|[+-][0-9]{2}:[0-9]{2})$'
     OR (p_payload->>'horizon_until') !~
           '^.{10,50}(Z|[+-][0-9]{2}:[0-9]{2})$'
  THEN
    RAISE EXCEPTION 'CONV_REG_PAYLOAD_INVALID';
  END IF;
  SELECT pg_catalog.count(*), pg_catalog.count(DISTINCT r.value)
    INTO evidence_total, evidence_unique
  FROM pg_catalog.jsonb_array_elements(p_payload->'evidence_refs') AS r(value)
  WHERE pg_catalog.jsonb_typeof(r.value)='string'
    AND pg_catalog.length(r.value #>> '{}') BETWEEN 1 AND 240;
  IF evidence_total <> pg_catalog.jsonb_array_length(p_payload->'evidence_refs')
     OR evidence_unique <> evidence_total THEN
    RAISE EXCEPTION 'CONV_REG_EVIDENCE_REFS_INVALID';
  END IF;
  probability := (p_payload->>'predicted_probability')::numeric;
  proposed := (p_payload->>'predicted_at')::timestamptz;
  horizon := (p_payload->>'horizon_until')::timestamptz;
  IF probability < 0 OR probability > 1
     OR proposed < now_at - interval '5 minutes'
     OR proposed > now_at + interval '2 minutes'
     OR horizon <= now_at
     OR horizon <= proposed THEN
    RAISE EXCEPTION 'CONV_REG_NOT_PROSPECTIVE';
  END IF;

  -- Independent DB-computed digest of the exact JSONB value that will be
  -- stored. Unlike the client SHA, this cannot be supplied by the caller.
  server_hash := pg_catalog.encode(
    pg_catalog.sha256(pg_catalog.convert_to(p_payload::text,'UTF8')),
    'hex'
  );
  -- Return pre-existing immutable evidence when exactly identical.
  -- A later ON CONFLICT handles concurrent submissions safely.
  SELECT * INTO existing_row
  FROM public.original_conversion_predictions
  WHERE tenant_id=current_tenant AND prediction_ref=p_prediction_ref;
  IF FOUND THEN
    IF existing_row.prediction_json IS DISTINCT FROM p_payload
       OR existing_row.client_payload_sha256 IS DISTINCT FROM p_client_hash
       OR existing_row.server_payload_sha256 IS DISTINCT FROM server_hash THEN
      RAISE EXCEPTION 'CONV_REG_IMMUTABLE_IDENTITY_COLLISION';
    END IF;
    RETURN pg_catalog.jsonb_build_object(
      'status','existing',
      'prediction_ref',existing_row.prediction_ref,
      'tenant_id',existing_row.tenant_id::text,
      'recorded_at',existing_row.recorded_at,
      'payload_sha256',existing_row.client_payload_sha256,
      'server_payload_sha256',existing_row.server_payload_sha256
    );
  END IF;

  INSERT INTO public.original_conversion_predictions (
    tenant_id, prediction_ref, opportunity_key,
    predicted_probability, model_name, model_version,
    proposed_at,horizon_until,source_evidence,prediction_json,
    client_payload_sha256,server_payload_sha256,recorded_at
  ) VALUES (
    current_tenant,p_prediction_ref,p_payload->>'opportunity_key',
    probability,p_payload->>'model_name',p_payload->>'model_version',
    proposed,horizon,p_payload->'evidence_refs',p_payload,p_client_hash,
    server_hash,now_at
  )
  ON CONFLICT (tenant_id,prediction_ref) DO NOTHING
  RETURNING * INTO existing_row;
  IF NOT FOUND THEN
    SELECT * INTO existing_row
    FROM public.original_conversion_predictions
    WHERE tenant_id=current_tenant AND prediction_ref=p_prediction_ref;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'CONV_REG_CONCURRENT_RECORD_UNAVAILABLE';
    END IF;
    IF existing_row.prediction_json IS DISTINCT FROM p_payload
       OR existing_row.client_payload_sha256 IS DISTINCT FROM p_client_hash
       OR existing_row.server_payload_sha256 IS DISTINCT FROM server_hash THEN
      RAISE EXCEPTION 'CONV_REG_IMMUTABLE_IDENTITY_COLLISION';
    END IF;
    RETURN pg_catalog.jsonb_build_object(
      'status','existing',
      'prediction_ref',existing_row.prediction_ref,
      'tenant_id',existing_row.tenant_id::text,
      'recorded_at',existing_row.recorded_at,
      'payload_sha256',existing_row.client_payload_sha256,
      'server_payload_sha256',existing_row.server_payload_sha256
    );
  END IF;
  RETURN pg_catalog.jsonb_build_object(
    'status','recorded',
    'prediction_ref',existing_row.prediction_ref,
    'tenant_id',existing_row.tenant_id::text,
    'recorded_at',existing_row.recorded_at,
    'payload_sha256',existing_row.client_payload_sha256,
      'server_payload_sha256',existing_row.server_payload_sha256
  );
END
$$;

CREATE FUNCTION public.read_original_conversion_prediction_v1(
  p_tenant text, p_prediction_ref text
)
RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
 SELECT pg_catalog.jsonb_build_object(
   'prediction_ref',v.prediction_ref,
   'tenant_id',v.tenant_id::text,
   'recorded_at',v.recorded_at,
   'payload_sha256',v.client_payload_sha256,
   'server_payload_sha256',v.server_payload_sha256,
   'server_payload_integrity_valid',
     (v.server_payload_sha256 = pg_catalog.encode(
       pg_catalog.sha256(pg_catalog.convert_to(v.prediction_json::text,'UTF8')),
       'hex')),
   'prediction',v.prediction_json
 )
 FROM public.original_conversion_predictions AS v
 WHERE v.tenant_id=public.empire_current_tenant_id()
   AND p_tenant=v.tenant_id::text
   AND v.prediction_ref=p_prediction_ref
 LIMIT 1
$$;

REVOKE ALL ON FUNCTION public.record_original_conversion_prediction_v1(
  text,text,jsonb,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.read_original_conversion_prediction_v1(
  text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_original_conversion_prediction_v1(
  text,text,jsonb,text) TO empire_original_conversion_prediction_writer;
GRANT EXECUTE ON FUNCTION public.read_original_conversion_prediction_v1(
  text,text) TO empire_original_conversion_prediction_reader;
-- NO grant of either NOLOGIN role to any runtime account; credentials remain
-- absent. The founder must separately approve an audited, tenant-bound login.
RESET ROLE;
COMMIT;
