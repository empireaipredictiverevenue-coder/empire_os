# High-Risk Supabase API Lockdown — Staged 2026-09-21

This is a **staged remediation only**. No production database authorization
change has been applied.

## Verified current risks

The Supabase Security Advisor reported:
- 115 public tables with RLS disabled;
- 75 public tables with RLS enabled but no policies;
- 7 public security-definer views;
- 1 exposed materialized view;
- 2 anon-executable SECURITY DEFINER token RPCs.

The seven flagged views expose commercial, referral, payout, email, phone,
wallet or projected-revenue data:
- affiliate_performance
- affiliate_stats
- predictive_revenue_view
- contractor_referral_view
- referral_click_funnel
- bounty_payout_summary
- referral_funnel_view

The exposed materialized view is:
- pulse_rollup_hourly

The two token RPCs currently grant EXECUTE to anon:
- get_astra_operational_evidence_token(text)
- get_commercial_outcome_feedback_token(text, integer)

Both token RPCs were inspected directly and already use
`SET search_path TO ''` with fully-qualified calls, so the staged migration
does not rewrite their bodies.

## Staged migration

`supabase/migrations/20260921123000_high_risk_api_security_lockdown.sql`

It:
1. sets all seven views to security-invoker;
2. revokes anon/authenticated access to those views;
3. preserves service-role SELECT;
4. revokes anon/authenticated access to pulse_rollup_hourly;
5. grants pulse_rollup_hourly SELECT only to service_role;
6. revokes PUBLIC/anon/authenticated EXECUTE on the two token RPCs;
7. grants EXECUTE to service_role.

## Not included yet

The migration deliberately does **not** attempt blanket policies across the
115 RLS-disabled and 75 policy-less tables. Those require table-by-table
ownership/tenant semantics. Applying generic authenticated policies would be
unsafe.

## Production gate

Applying this migration changes who can read commercial data and invoke RPCs.
It therefore remains a founder/security gate. Validation may continue; apply
must be explicit.
