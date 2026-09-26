-- Allow the existing restricted materializer role to read the canonical
-- commercial catalog through its bounded SECURITY DEFINER RPC.
BEGIN;

GRANT EXECUTE ON FUNCTION public.get_commercial_product_catalog(
  text, integer
) TO empire_intelligence_materializer;

COMMENT ON FUNCTION public.get_commercial_product_catalog(text,integer)
IS 'Bounded canonical commercial catalog projection. Read-only; safe for restricted runtime materializers.';

COMMIT;
