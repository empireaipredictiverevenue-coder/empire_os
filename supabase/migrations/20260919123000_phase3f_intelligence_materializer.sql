-- Phase 3F least-privilege Intelligence Fabric materializer.
-- Staged only until production activation is explicitly approved.
BEGIN;

DO $$
DECLARE
  required_table text;
BEGIN
  FOREACH required_table IN ARRAY ARRAY[
    'public.prospects',
    'public.prospect_entity_links',
    'public.prospect_qualifications',
    'public.intelligence_sources',
    'public.intelligence_facts',
    'public.intelligence_scores'
  ]
  LOOP
    IF to_regclass(required_table) IS NULL THEN
      RAISE EXCEPTION
        'Intelligence materializer dependency missing: %',
        required_table;
    END IF;
  END LOOP;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS
  uq_intelligence_facts_evidence_hash
ON public.intelligence_facts(evidence_hash)
WHERE evidence_hash IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
  uq_intelligence_scores_materialized
ON public.intelligence_scores(
  entity_type,
  entity_id,
  score_type,
  model_key,
  scored_at
);

INSERT INTO public.intelligence_sources(
  source_key,
  source_type,
  display_name,
  authority_score,
  metadata
)
VALUES
(
  'empire.prospect.canonical.v1',
  'first_party',
  'Empire canonical prospect observation',
  1.0000,
  '{"authority_semantics":"authoritative_record_source; fact confidence remains separate"}'::jsonb
),
(
  'empire.qualification.lead_scoring.v1',
  'first_party',
  'Empire lead qualification v1',
  1.0000,
  '{"authority_semantics":"authoritative_internal_score_record; predictive confidence is separate"}'::jsonb
)
ON CONFLICT (source_key) DO NOTHING;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_intelligence_materializer'
  ) THEN
    CREATE ROLE empire_intelligence_materializer
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_roles
    WHERE rolname='empire_intelligence_materializer_login'
  ) THEN
    CREATE ROLE empire_intelligence_materializer_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 3;
  END IF;
END $$;

ALTER ROLE empire_intelligence_materializer_login PASSWORD NULL;
GRANT empire_intelligence_materializer
  TO empire_intelligence_materializer_login;
REVOKE empire_intelligence_materializer FROM service_role;

GRANT USAGE ON SCHEMA public
  TO empire_intelligence_materializer;

GRANT SELECT ON
  public.prospects,
  public.prospect_entity_links,
  public.prospect_qualifications,
  public.intelligence_sources,
  public.intelligence_facts,
  public.intelligence_scores
TO empire_intelligence_materializer;

GRANT INSERT ON
  public.intelligence_facts,
  public.intelligence_scores
TO empire_intelligence_materializer;

REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON
  public.prospects,
  public.prospect_entity_links,
  public.prospect_qualifications,
  public.intelligence_sources,
  public.intelligence_facts,
  public.intelligence_scores
FROM empire_intelligence_materializer;

ALTER ROLE empire_intelligence_materializer_login
  SET statement_timeout='15s';
ALTER ROLE empire_intelligence_materializer_login
  SET idle_in_transaction_session_timeout='30s';

DO $$
DECLARE
  table_name text;
  policy_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'prospects',
    'prospect_entity_links',
    'prospect_qualifications',
    'intelligence_sources',
    'intelligence_facts',
    'intelligence_scores'
  ]
  LOOP
    policy_name :=
      'intelligence_materializer_select_' || table_name;

    IF NOT EXISTS (
      SELECT 1
      FROM pg_policy p
      JOIN pg_class c ON c.oid=p.polrelid
      JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public'
        AND c.relname=table_name
        AND p.polname=policy_name
    ) THEN
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR SELECT TO empire_intelligence_materializer USING (true)',
        policy_name,
        table_name
      );
    END IF;
  END LOOP;
END $$;

CREATE POLICY intelligence_materializer_insert_facts
ON public.intelligence_facts
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  entity_type='company'
  AND evidence_hash IS NOT NULL
  AND source_id = (
    SELECT id
    FROM public.intelligence_sources
    WHERE source_key='empire.prospect.canonical.v1'
  )
);

CREATE POLICY intelligence_materializer_insert_scores
ON public.intelligence_scores
FOR INSERT
TO empire_intelligence_materializer
WITH CHECK (
  entity_type='company'
  AND score_type='lead_qualification'
  AND model_key='empire_os.lead_scoring:v1'
);

COMMENT ON ROLE empire_intelligence_materializer IS
'Phase 3F append-only canonical prospect/qualification Intelligence Fabric materializer.';
COMMENT ON ROLE empire_intelligence_materializer_login IS
'Phase 3F materializer runtime login; password provisioned out of band.';

COMMIT;
