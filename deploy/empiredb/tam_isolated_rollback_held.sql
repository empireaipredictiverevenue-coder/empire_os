-- HELD / approval required: isolated TAM rollback ONLY.
-- Requires a separate DBA release window; never touches Market GPS grants.
BEGIN;
SET LOCAL statement_timeout='15s';
DO $rollback_guard$
BEGIN
  IF current_database() <> 'empiredb' THEN
    RAISE EXCEPTION 'TAM rollback requires empiredb';
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_tam_market_reader' AND NOT rolcanlogin
  ) OR NOT EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname='empire_tam_market_login' AND rolcanlogin
  ) THEN
    RAISE EXCEPTION 'isolated TAM roles missing; manual recovery required';
  END IF;
  IF NOT EXISTS (
    SELECT FROM pg_catalog.pg_proc p
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations(integer)'
    ) AND p.proowner=(
      SELECT oid FROM pg_catalog.pg_roles
      WHERE rolname='empiredb_migrator'
    )
    AND p.prosecdef
  ) THEN
    RAISE EXCEPTION 'isolated TAM function ownership does not match';
  END IF;
END $rollback_guard$;
SET LOCAL ROLE empiredb_migrator;
REVOKE ALL ON FUNCTION public.get_tam_market_observations(integer)
  FROM empire_tam_market_reader, empire_tam_market_login;
DROP FUNCTION public.get_tam_market_observations(integer);
RESET ROLE;
REVOKE empire_tam_market_reader FROM empire_tam_market_login;
REVOKE CONNECT ON DATABASE empiredb FROM empire_tam_market_login;
REVOKE USAGE ON SCHEMA public FROM empire_tam_market_reader;
DROP ROLE empire_tam_market_login;
DROP ROLE empire_tam_market_reader;
COMMIT;
