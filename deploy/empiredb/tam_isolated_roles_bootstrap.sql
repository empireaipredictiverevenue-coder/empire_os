-- HELD: isolated TAM-only capability bootstrap (no live application approval).
-- Run only under independently approved DBA transaction; NEVER on generic materializer.
BEGIN;
SET LOCAL statement_timeout = '15s';
DO $guard$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'isolated TAM bootstrap requires empiredb';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles
     WHERE rolname='empiredb_migrator' AND NOT rolcanlogin AND NOT rolsuper) THEN
    RAISE EXCEPTION 'verified empiredb_migrator role required';
  END IF;
  IF EXISTS (SELECT FROM pg_catalog.pg_roles
     WHERE rolname IN ('empire_tam_market_reader','empire_tam_market_login')) THEN
    RAISE EXCEPTION 'TAM isolated role already exists; manual readback required';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles
     WHERE rolname='empire_intelligence_materializer' AND NOT rolcanlogin) THEN
    RAISE EXCEPTION 'existing materializer must remain in place';
  END IF;
END $guard$;
CREATE ROLE empire_tam_market_reader NOLOGIN NOINHERIT
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE empire_tam_market_login LOGIN NOINHERIT
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
  CONNECTION LIMIT 2 PASSWORD NULL;
GRANT empire_tam_market_reader TO empire_tam_market_login;
GRANT CONNECT ON DATABASE empiredb TO empire_tam_market_login;
GRANT USAGE ON SCHEMA public TO empire_tam_market_reader;
ALTER ROLE empire_tam_market_login SET statement_timeout='15s';
ALTER ROLE empire_tam_market_login
  SET idle_in_transaction_session_timeout='20s';
DO $final$
DECLARE
  name text;
  relation_name text;
  privilege_name text;
BEGIN
  IF NOT pg_catalog.pg_has_role(
    'empire_tam_market_login','empire_tam_market_reader','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empiredb_app','empire_tam_market_reader','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empire_intelligence_materializer','empire_tam_market_reader','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empire_tam_market_login','empire_intelligence_materializer','MEMBER'
  ) OR pg_catalog.pg_has_role(
    'empire_tam_market_login','empiredb_migrator','MEMBER'
  ) THEN
    RAISE EXCEPTION 'TAM isolated membership verification failed';
  END IF;
  FOREACH name IN ARRAY ARRAY[
      'empire_tam_market_reader','empire_tam_market_login'
  ] LOOP
    IF EXISTS (
      SELECT 1 FROM pg_catalog.pg_auth_members m
      JOIN pg_catalog.pg_roles r ON r.oid=m.member
      JOIN pg_catalog.pg_roles parent ON parent.oid=m.roleid
      WHERE r.rolname=name AND NOT (
        name='empire_tam_market_login'
        AND parent.rolname='empire_tam_market_reader'
      )
    ) THEN RAISE EXCEPTION 'TAM role has forbidden inherited membership'; END IF;
    FOREACH relation_name IN ARRAY ARRAY[
      'public.prospect_acquisitions',
      'public.prospect_entity_links',
      'public.business_entities'
    ] LOOP
      IF pg_catalog.to_regclass(relation_name) IS NULL THEN
        RAISE EXCEPTION 'TAM base relation missing: %',relation_name;
      END IF;
      FOREACH privilege_name IN ARRAY ARRAY[
        'SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'
      ] LOOP
        IF pg_catalog.has_table_privilege(name,relation_name,privilege_name)
        THEN
          RAISE EXCEPTION 'TAM role unexpected base-table privilege';
        END IF;
      END LOOP;
    END LOOP;
  END LOOP;
END $final$;
COMMIT;
