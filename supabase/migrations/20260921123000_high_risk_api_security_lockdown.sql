-- EmpireOS high-risk Data API security lockdown — STAGED, NOT APPLIED.
--
-- This migration changes production authorization semantics.
-- It must not be applied without explicit founder/security approval.
--
-- Scope:
--   1. Convert seven legacy public views to security-invoker.
--   2. Remove anon/authenticated access to those sensitive views.
--   3. Remove anon/authenticated access to pulse_rollup_hourly.
--   4. Remove anon/authenticated EXECUTE on two token-gated
--      SECURITY DEFINER RPCs and grant service_role explicitly.
--
-- The two RPCs already use SET search_path TO '' and fully-qualified
-- function calls; this migration preserves those safe definitions.

BEGIN;

ALTER VIEW public.affiliate_performance
  SET (security_invoker = true);
ALTER VIEW public.affiliate_stats
  SET (security_invoker = true);
ALTER VIEW public.predictive_revenue_view
  SET (security_invoker = true);
ALTER VIEW public.contractor_referral_view
  SET (security_invoker = true);
ALTER VIEW public.referral_click_funnel
  SET (security_invoker = true);
ALTER VIEW public.bounty_payout_summary
  SET (security_invoker = true);
ALTER VIEW public.referral_funnel_view
  SET (security_invoker = true);

REVOKE ALL ON TABLE public.affiliate_performance
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.affiliate_stats
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.predictive_revenue_view
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.contractor_referral_view
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.referral_click_funnel
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.bounty_payout_summary
  FROM anon, authenticated;
REVOKE ALL ON TABLE public.referral_funnel_view
  FROM anon, authenticated;

GRANT SELECT ON TABLE public.affiliate_performance TO service_role;
GRANT SELECT ON TABLE public.affiliate_stats TO service_role;
GRANT SELECT ON TABLE public.predictive_revenue_view TO service_role;
GRANT SELECT ON TABLE public.contractor_referral_view TO service_role;
GRANT SELECT ON TABLE public.referral_click_funnel TO service_role;
GRANT SELECT ON TABLE public.bounty_payout_summary TO service_role;
GRANT SELECT ON TABLE public.referral_funnel_view TO service_role;

REVOKE ALL ON TABLE public.pulse_rollup_hourly
  FROM anon, authenticated;
GRANT SELECT ON TABLE public.pulse_rollup_hourly TO service_role;

REVOKE EXECUTE ON FUNCTION
  public.get_astra_operational_evidence_token(text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION
  public.get_astra_operational_evidence_token(text)
  TO service_role;

REVOKE EXECUTE ON FUNCTION
  public.get_commercial_outcome_feedback_token(text, integer)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION
  public.get_commercial_outcome_feedback_token(text, integer)
  TO service_role;

COMMIT;
