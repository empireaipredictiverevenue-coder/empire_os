-- HELD for independently approved rollback of 044 only.
-- Does not touch existing 043, TAM login, Market GPS roles or credentials.
BEGIN;
SET LOCAL ROLE empiredb_migrator;
SET LOCAL statement_timeout='15s';
DO $guard$
BEGIN
  IF current_database()<>'empiredb' THEN
    RAISE EXCEPTION 'TAM044 rollback wrong database';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid=to_regprocedure(
      'public.get_tam_market_observations_scoped(text[],text[],integer)'
    ) AND p.proowner=(SELECT oid FROM pg_catalog.pg_roles
      WHERE rolname='empiredb_migrator')
      AND p.prosecdef
  ) THEN
    RAISE EXCEPTION 'TAM044 rollback function owner/security mismatch';
  END IF;
  IF to_regprocedure(
    'public.get_tam_market_observations(integer)'
  ) IS NULL THEN
    RAISE EXCEPTION 'existing 043 must remain intact';
  END IF;
END $guard$;
REVOKE EXECUTE ON FUNCTION
  public.get_tam_market_observations_scoped(text[],text[],integer)
  FROM empire_tam_market_reader;
DROP FUNCTION public.get_tam_market_observations_scoped(
  text[],text[],integer
);
COMMIT;
