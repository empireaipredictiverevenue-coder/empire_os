BEGIN;

ALTER FUNCTION public.claim_next_task(text,text[])
  SET search_path = '';
ALTER FUNCTION public.complete_task(uuid,jsonb,text)
  SET search_path = '';

REVOKE ALL ON FUNCTION public.claim_next_task(text,text[])
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.complete_task(uuid,jsonb,text)
  FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.claim_next_task(text,text[])
  TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_task(uuid,jsonb,text)
  TO service_role;

COMMENT ON FUNCTION public.claim_next_task(text,text[]) IS
  'Internal task-claim RPC. SECURITY DEFINER; callable only by service_role.';
COMMENT ON FUNCTION public.complete_task(uuid,jsonb,text) IS
  'Internal task-completion RPC. SECURITY DEFINER; callable only by service_role.';

COMMIT;
