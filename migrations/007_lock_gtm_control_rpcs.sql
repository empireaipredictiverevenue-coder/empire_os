-- Empire OS — lock GTM queue control RPCs to service_role
-- Migration: 007_lock_gtm_control_rpcs
--
-- Removes public/anon/authenticated execution from the autonomous GTM bus controls.
-- The execution bus already uses the Supabase service-role credential.

REVOKE ALL ON FUNCTION public.claim_next_gtm_job(TEXT, INTEGER)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.heartbeat_gtm_job(UUID, TEXT, UUID, INTEGER)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.complete_gtm_job(UUID, TEXT, UUID, JSONB)
    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fail_gtm_job(UUID, TEXT, UUID, TEXT, INTEGER, JSONB)
    FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.claim_next_gtm_job(TEXT, INTEGER)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.heartbeat_gtm_job(UUID, TEXT, UUID, INTEGER)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_gtm_job(UUID, TEXT, UUID, JSONB)
    TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_gtm_job(UUID, TEXT, UUID, TEXT, INTEGER, JSONB)
    TO service_role;
