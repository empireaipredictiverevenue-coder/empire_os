-- Restore the protected service-role bridge used by the bounded
-- Supabase outbound transport. The dedicated sender role remains allowed too.

GRANT EXECUTE ON FUNCTION public.get_outbound_governor_context(uuid)
TO service_role;

COMMENT ON FUNCTION public.get_outbound_governor_context(uuid) IS
'Read-only evidence projection for the Phase 3E Outbound Governor. EXECUTE is granted to the dedicated sender role and protected service_role bridge; application RPC allowlists remain the runtime boundary.';
