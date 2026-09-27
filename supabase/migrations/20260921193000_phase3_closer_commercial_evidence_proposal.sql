-- Phase 3: allow closer planner to record buyer-stated commercial evidence.
-- Proposal-only. Verification, terms approval, payment and revenue authority
-- remain separate and are not granted here.
BEGIN;

REVOKE ALL ON FUNCTION public.propose_commercial_evidence(
  text,uuid,uuid,uuid,text,text,bigint,text,text,text,jsonb,timestamptz,timestamptz
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.propose_commercial_evidence(
  text,uuid,uuid,uuid,text,text,bigint,text,text,text,jsonb,timestamptz,timestamptz
) TO empire_closer_planner;

REVOKE ALL ON FUNCTION public.verify_commercial_evidence(uuid,text)
FROM empire_closer_planner;

COMMIT;
