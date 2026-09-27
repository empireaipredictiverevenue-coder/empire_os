-- Temporary Phase 3E runtime bridge for environments where dedicated
-- Postgres LOGIN passwords cannot be provisioned through the deployment plane.
-- The server-side worker still enforces the existing RPC allowlist and no table
-- write helper or arbitrary SQL surface is added.
BEGIN;

GRANT EXECUTE ON FUNCTION public.get_outbound_intent_review(uuid)
TO service_role;
GRANT EXECUTE ON FUNCTION public.get_outbound_governor_context(uuid)
TO service_role;
GRANT EXECUTE ON FUNCTION public.list_outbound_governor_work(integer)
TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_outbound_send(uuid,text)
TO service_role;
GRANT EXECUTE ON FUNCTION public.record_outbound_delivery(
    uuid,text,text,text,jsonb
) TO service_role;

GRANT EXECUTE ON FUNCTION public.ingest_outbound_reply(
    uuid,text,text,text,text,timestamptz,jsonb
) TO service_role;
GRANT EXECUTE ON FUNCTION public.classify_outbound_reply(
    uuid,text,numeric,text
) TO service_role;
GRANT EXECUTE ON FUNCTION public.record_outbound_provider_event(
    uuid,text,text,text,boolean,jsonb
) TO service_role;

COMMIT;
