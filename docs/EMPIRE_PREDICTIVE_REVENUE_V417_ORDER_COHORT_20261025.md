# Empire AI Predictive Revenue V4.17 — complete buyer-owned order window (HELD)

**25 October 2026 | One EmpireOS · One original EmpireDB PostgreSQL · One Smart CRM · Not trading**

## Problem fixed

V4.13 checked **selected recognised revenue events** and V4.15–16 checked **up to eight selected orders** for direct BSC transfer candidates and operational reversal signals. Those samples cannot form a complete commercial denominator. V4.17 therefore reads **every fulfilment order attached to a buyer owned by the authenticated tenant in a bounded created-at window**, including open, cancelled and rejected states. It never mistakes those orders for the universe of GTM opportunities.

## Delivered as separate add-only code

- `migrations/empiredb/069_predictive_revenue_tenant_order_cohort_held.sql` — **PREPARED, NOT APPLIED to original production EmpireDB**. Requires owner-reviewed original 067 and 068 functions, original `empiredb_migrator` and `empire_predictive_cash_candidate_reader` NOLOGIN capability, and trusted `empire_current_tenant_id()`. Owner's single SECURITY DEFINER read function verifies `session_user='empire_predictive_cash_candidate_login'` and buyer `buyers.org_id`, performs a 31-day-or-less read (within last 5 years), fails closed above 5,000 buyer-owned orders, returns one bounded aggregate without IDs, PII, prospect emails or monetary amounts. Never creates a second DB/table, role, login, new daemon, credential, broad table grant, send or payment capability.
- `empire_os/predictive_revenue_v417_order_cohort.py` — reuses original `SignedCrmTenantVerifier`, V4.12 no-execution research twin and original V4.15 dedicated `SET ROLE` reader. Reads with `SET TRANSACTION READ ONLY`, 4-second statement timeout, exact login/capability, one aggregate row, strict numeric checks, no network on import. Missing schema/owner DSN or malformed/overprivileged data returns HELD with **null counts rather than a false zero**. An injected/mock PostgreSQL connector cannot return live denominators, and endpoint attestation remains false.
- `scripts/rehearse_predictive_revenue_v417_order_cohort_20261025.sh` and `.py` — real SCRAM PostgreSQL18 ephemeral `pg_virtualenv` fixture; apply 067, 068, 069 **only in disposable fixture**, prove cross-tenant denial, 31-day window guard, original CRM signed tenant login, direct table SELECT denial (from earlier source fixture), and all state categories without extra fetch permissions.
- `tests/test_predictive_revenue_v417_order_cohort_20261025.py` — forged numeric/bool status, malformed/incomplete records, strict temporal windows, duplicate opportunity interpretation, fake membership and role, missing DB, and the actual PostgreSQL integration.

## What it counts and what it does not

Eligible denominator **is orders**, not prospects or lead opportunities:
`fulfilment_orders` joined to `buyers` with buyer `org_id` exactly equal to the original authenticated tenant. The interval is half-open `[created_at_start, created_at_end)`. Result counts the **current** state of orders that were created in that period.

Returns buyer-owned order count, current state counts (settled/outcome-captured; rejected; cancelled; everything else/open), orders missing an `opportunity_id`, unique opportunity IDs **already linked to those orders**, and whether multiple orders may correspond to one linked opportunity. No order IDs or CRM/customer PII leave the function.

**Source limitation:** `gtm_opportunities` has no direct tenant ownership field in the original migration 002. Unlinked GTM opportunities, unsold prospects, unowned/null-buyer orders, and all unrelated buyers therefore remain outside this denominator. Even with 100% bounded-order coverage, **complete opportunity conversion rate remains unverified**.

**Historical limitation:** `state` is today's currently stored state. This is not an immutable as-of historic status at the chosen window end, and cannot establish backtest calibration by itself. `settled` is not independently verified collected cash, refunds and chargebacks are not closed, and original revenue recognition remains distinct from funds.

Every response: `execution_authority=none`, `gtm_opportunity_denominator_complete=false`, `historical_status_as_of_window_end_verified=false`, `eligible_for_revenue_forecast_calibration=false`, `actual_cash_collected_minor_units=null`, economic-memory writes/outbound/paid traffic/funds OFF. Currency remains unproved for financial outcomes. No public/private runtime route added.

## Verified isolated example

In the PostgreSQL18 fixture: **seven** in-window tenant-owned orders (4 settled/outcome-captured, 1 rejected, 1 cancelled, 1 open), **one** without an opportunity link, **five** unique linked opportunity IDs because some orders share one opportunity. The fixture separately contained a foreign-tenant order and an out-of-window own order that the reader excluded. Tested exact PG and Ed25519 Smart CRM-bound read. These are **fabricated test rows, not production revenue or buyer statistics**.

## Genuine revenue calibration: next dependencies

1. Owner-reviewed and provisioned original DB migrations 066–069, role bindings, source rights, RLS/historical backups and rollback. This code release does **not** activate any migration.
2. A separately modelled tenant-owned, immutable **opportunity-event cohort** with full acquisition/qualified/closed timestamps and **all** eligible opportunities including those with no order or buyer. Verify rights and consent.
3. Independently verified **collected** cash/USDT token movement with exact amounts/currency/treasury ownership, later refunds, reversals, fees, settlement disputes and confirmed financial finality; train on time-locked forecasts only.
4. Only once (2) and (3) exist, evaluate V4.14 30/60/90 historical holdout and calibration, avoiding censored false negatives and historical leakage.

**One EmpireOS. One EmpireDB. One Smart CRM. Predictive Revenue, not trading.**
