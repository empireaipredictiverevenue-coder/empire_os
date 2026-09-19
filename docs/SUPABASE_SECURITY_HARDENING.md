# Supabase Security Hardening

Status: staged/local-tested. No production lockdown migration applied by this slice.

## Production findings

Supabase security inspection on 2026-09-19 found a broad public-schema exposure surface.
The highest-risk pattern is public tables with RLS disabled while anon and authenticated
roles still hold direct table privileges.

Confirmed examples included:
- b2b_leads: 775 rows, internal idle-import source.
- empire_revenue_ledger: 28 rows, internal revenue data.
- crypto_payment_requests: legacy/replaced payment-request surface.
- product_pricing: 48 rows; likely public-read but not public-write.
- product_subscriptions: 27 rows; requires customer/tenant-scoped policy.
- contractor_subscriptions: 1 row; requires owner-scoped policy.
- payout, advertiser transaction, outreach and referral tables also require classification.

The advisor also reported SECURITY DEFINER views and numerous RLS-enabled tables with
no policies. Those are tracked separately because blanket changes could break live
services.

## First bounded remediation slice

Migration:
supabase/migrations/20260919124500_lock_internal_legacy_surfaces.sql

Targets only:
- public.b2b_leads
- public.empire_revenue_ledger
- public.crypto_payment_requests

Behavior:
- revoke all table privileges from anon and authenticated;
- enable RLS;
- create no client policies;
- preserve postgres/admin and service_role access;
- preserve all existing rows;
- do not touch current governed BSC payment tables.

Why these three:
- repo inspection shows no live client dependency;
- b2b_leads is used only as an internal migration/import source;
- empire_revenue_ledger has no current repo consumer;
- crypto_payment_requests is explicitly legacy and superseded by the governed BSC flow.

## Next classes

1. Internal-only: revoke client access and enable RLS.
2. Public-read: SELECT-only policy, no direct writes.
3. Tenant/customer data: owner-scoped RLS based on authenticated identity.
4. Server workflows: dedicated runtime roles, no service-role fallback where practical.
5. Views/materialized views: remove SECURITY DEFINER/public API exposure unless justified.

Production application remains a separate approval gate.
