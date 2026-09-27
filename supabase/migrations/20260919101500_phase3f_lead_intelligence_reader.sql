-- Phase 3F canonical Lead Intelligence read-only runtime identity.
-- Password remains NULL and must be provisioned out of band.
BEGIN;

DO $$
DECLARE
  required_table text;
BEGIN
  FOREACH required_table IN ARRAY ARRAY[
    'public.prospects',
    'public.prospect_entity_links',
    'public.business_entities',
    'public.prospect_qualifications',
    'public.prospect_acquisitions',
    'public.intelligence_facts',
    'public.intelligence_signals',
    'public.intelligence_scores',
    'public.intelligence_contact_points',
    'public.intelligence_employment'
  ]
  LOOP
    IF to_regclass(required_table) IS NULL THEN
      RAISE EXCEPTION
        'Lead Intelligence dependency missing: %',
        required_table;
    END IF;
  END LOOP;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname='empire_lead_intelligence_reader'
  ) THEN
    CREATE ROLE empire_lead_intelligence_reader
      NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname='empire_lead_intelligence_reader_login'
  ) THEN
    CREATE ROLE empire_lead_intelligence_reader_login
      LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5;
  END IF;
END $$;

ALTER ROLE empire_lead_intelligence_reader_login PASSWORD NULL;
GRANT empire_lead_intelligence_reader
  TO empire_lead_intelligence_reader_login;
GRANT USAGE ON SCHEMA public
  TO empire_lead_intelligence_reader;
REVOKE empire_lead_intelligence_reader FROM service_role;

ALTER ROLE empire_lead_intelligence_reader_login
  SET statement_timeout='15s';
ALTER ROLE empire_lead_intelligence_reader_login
  SET idle_in_transaction_session_timeout='30s';

GRANT SELECT ON
  public.prospects,
  public.prospect_entity_links,
  public.business_entities,
  public.prospect_qualifications,
  public.prospect_acquisitions,
  public.intelligence_facts,
  public.intelligence_signals,
  public.intelligence_scores,
  public.intelligence_contact_points,
  public.intelligence_employment
TO empire_lead_intelligence_reader;

REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON
  public.prospects,
  public.prospect_entity_links,
  public.business_entities,
  public.prospect_qualifications,
  public.prospect_acquisitions,
  public.intelligence_facts,
  public.intelligence_signals,
  public.intelligence_scores,
  public.intelligence_contact_points,
  public.intelligence_employment
FROM empire_lead_intelligence_reader;

DO $$
DECLARE
  table_name text;
  policy_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'prospects',
    'prospect_entity_links',
    'business_entities',
    'prospect_qualifications',
    'prospect_acquisitions',
    'intelligence_facts',
    'intelligence_signals',
    'intelligence_scores',
    'intelligence_contact_points',
    'intelligence_employment'
  ]
  LOOP
    policy_name :=
      'lead_intelligence_reader_select_' || table_name;

    IF NOT EXISTS (
      SELECT 1
      FROM pg_policy p
      JOIN pg_class c
        ON c.oid=p.polrelid
      JOIN pg_namespace n
        ON n.oid=c.relnamespace
      WHERE n.nspname='public'
        AND c.relname=table_name
        AND p.polname=policy_name
    ) THEN
      EXECUTE format(
        'CREATE POLICY %I ON public.%I FOR SELECT TO empire_lead_intelligence_reader USING (true)',
        policy_name,
        table_name
      );
    END IF;
  END LOOP;
END $$;

COMMENT ON ROLE empire_lead_intelligence_reader IS
'Phase 3F SELECT-only canonical Lead Intelligence projection role.';
COMMENT ON ROLE empire_lead_intelligence_reader_login IS
'Phase 3F Lead Intelligence runtime login; password provisioned out of band.';

COMMIT;
