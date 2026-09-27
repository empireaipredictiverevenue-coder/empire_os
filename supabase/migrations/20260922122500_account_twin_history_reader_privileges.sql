-- Tighten the Account Twin history function to the dedicated restricted role.
BEGIN;

DO $$
BEGIN
  IF to_regprocedure(
    'public.empire_account_twin_history(uuid[])'
  ) IS NULL THEN
    RAISE EXCEPTION 'empire_account_twin_history(uuid[]) missing';
  END IF;
END $$;

REVOKE EXECUTE ON FUNCTION public.empire_account_twin_history(uuid[])
FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.empire_account_twin_history(uuid[])
TO empire_intelligence_materializer;

COMMIT;
