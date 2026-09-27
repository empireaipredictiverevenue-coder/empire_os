# Supabase Security / RLS Audit — 2026-09-21

Canonical project: owbeinlfcfdtwcwrttjy

Mode: read-only audit. No policy, grant, schema, function or view mutation was
performed.

## Security Advisor findings

- 115 public tables reported with RLS disabled.
- 75 public tables reported with RLS enabled but no policies.
- 7 public security-definer views.
- 16 public functions reported with mutable/unpinned search path.
- 1 materialized view exposed through the Data API.
- 2 SECURITY DEFINER functions executable by anon.

Security-definer views:
- affiliate_performance
- affiliate_stats
- predictive_revenue_view
- contractor_referral_view
- referral_click_funnel
- bounty_payout_summary
- referral_funnel_view

Anon-executable SECURITY DEFINER functions:
- get_astra_operational_evidence_token(p_token text)
- get_commercial_outcome_feedback_token(p_token text, p_limit integer)

Materialized view exposed:
- pulse_rollup_hourly

## Remediation order

1. Classify every public relation as:
   - server-only;
   - authenticated tenant;
   - public read;
   - privileged operator.
2. Revoke anon/authenticated grants from server-only relations.
3. Enable RLS on every client-accessible table.
4. Add table-specific ownership/tenant policies; do not use blanket
   authenticated access.
5. Move or recreate security-definer views with safe invoker semantics where
   possible.
6. Review the two anon-executable SECURITY DEFINER functions and retain public
   execution only if their token boundary is explicitly verified.
7. Pin safe search_path values for mutable-path functions.
8. Remove public Data-API exposure for pulse_rollup_hourly unless explicitly
   required.
9. Re-run Security Advisor and role-based tests.

## Gate

Applying these policies changes live production authorization semantics.
The audit and remediation inventory are complete; migration activation remains
a founder/security gate.
