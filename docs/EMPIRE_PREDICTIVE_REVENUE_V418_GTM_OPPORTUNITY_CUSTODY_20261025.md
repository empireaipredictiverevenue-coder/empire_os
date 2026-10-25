# Empire AI Predictive Revenue V4.18 — complete GTM opportunity custody, HELD

**25 October 2026 | Original EmpireOS and EmpireDB PostgreSQL | One Smart CRM | No trading**

## Scope and provenance

User-provided `v4_18_opportunity_intelligence_handoff.txt` proposes separate `empire_tenants`, `empire_opportunities` and `empire_orders` tables. **Do not install these duplicates.** Existing original EmpireDB already owns `gtm_opportunities` (migration 002), `fulfilment_orders`, `buyers` and `commercial_outcomes`. V4.17 only counts **buyer-owned fulfilment orders**. Opportunities that never enter an order are omitted from that denominator.

V4.18 creates a **PREPARED, NEVER PRODUCTION-APPLIED** migration 070 containing:
1. `empire_predictive_opportunity_custody_v418`: one claimed tenant assignment per original GTM opportunity ID, first observed timestamp, source/ownership evidence digests, claimed acquisition cost in integer minor units and explicit GBP/USD/EUR currency. Does not duplicate source-of-truth GTM records, invoices or customer identities.
2. `empire_predictive_opportunity_states_v418`: append-only, ordered original-opportunity lifecycle events (`OPEN`, `DISQUALIFIED`, `DEAD`, `CONVERTED`). A trigger requires initial OPEN, then exactly one terminal state (and strictly later event time). A conversion requires an order linked to the original opportunity and a buyer belonging to the same tenant, in an accepted-or-later state; a raw, rejected, cancelled or foreign-tenant order cannot justify conversion. UPDATE/DELETE attempts on custody or state events fail.
3. `read_predictive_revenue_gtm_denominator_v418`: restricted SECURITY DEFINER aggregate read, original dedicated NOLOGIN reader role, trustworthy `session_user` tenant resolver, maximum 31-day half-open custody window, 5,000-row hard stop, original GTM and order joins, no unscoped UUIDs, customer records or email export. Original owner policies FORCE RLS. No general app SELECT/INSERT grants, no new login/DB or production service.
4. `empire_os/predictive_revenue_v418_opportunities.py`: strict Smart CRM Ed25519 membership + V4.12 research-twin contract, read-only psycopg and a 4s timeout, identity/currency/count validations. Fails closed when migration 070 isn't approved or source data is incomplete. A mocked connector cannot report real cohort counts.

**One-time DDL creation is held:** migrations 066, 067, 068, 069 and new 070 remain subject to independent DBA/Security review, backup/rollback, role grants, source rights and explicit owner authority. The SQL fixture applies only inside `pg_virtualenv` disposable PostgreSQL 18.

## Opportunity funnel arithmetic — experimental only

Every opportunity in the tenant's *claimed custody set*, including OPEN and those without lifecycle evidence, stays in the all-opportunity denominator. Read-only outputs include:
- `research_cvr_all_opportunities_pct = 100 × tenant-order-linked converted opportunities / all claimed-custody opportunities`.
- `research_cvr_closed_opportunities_pct = 100 × order-linked conversions / (DISQUALIFIED + DEAD + all CONVERTED claims)`. An unlinked conversion claim **remains in the closed denominator**, but not the verified-order numerator.
- `research_ecac_minor_per_buyer_order = total claimed acquisition costs across ALL opportunity statuses / order-linked conversions`, only if the claimed window has a single exact currency and a nonzero numerator. Zero conversions yield null, not infinity or zero costs.

**The words “true CVR” and “effective CAC” are not yet independently verified.** Custody coverage across all source channels, source rights, actual carrier/proxy/ad expenses, deduplication, order capture, historical status, conversion origin, cancellations, and settled finance outcomes need to be independently proven. No automatic paid acquisition is authorised.

The model's existing V4.12 30/60/90 *simulation* remains intact. User-supplied 45%/80%/100% payout factors are explicitly **illustrative assumptions**. No sample revenue or buyer payments were imported, no validated cash-maturation curve was generated, and no recognition/settlement occurred.

## Four-sector handoff coverage

The requested Pay-Per-Call, Storm Restoration, E-Commerce and SaaS sector labels require a verified mapping from the original `gtm_opportunities.niche`, `opportunity_type`, `source_channel` and commercial product taxonomy. V4.18 deliberately does NOT pretend these labels are already canonical, nor auto-convert `raw clicks` into a distinct qualified customer/opportunity without an explicit event boundary. Founder/Security must approve segmentation and source permissions before any per-sector production CVR claims.

## Provided 100,000-opportunity table: not an actual backtest

Its 100,000 records and financial figures were presented in the handoff **without verifiable input records, collection windows, dedupe, rights, transaction references or out-of-sample evaluation**. They remain synthetic/illustrative and cannot populate real finance or economic memory. Auditing its arithmetic: total nominal spend `$503,190.89` divided by 14,377 converted orders is about **$35.00 per converted order**, not the displayed `$34.99`. Multiplying illustrative net margin by 45% or 80% is not a cash receipt or a calibrated predictive distribution. Negative E-Commerce margin is a diagnostic sensitivity case, not independent commercial loss proof.

## Actual disposable acceptance fixture

One isolated PG18 tenant A has seven in-window custody claims: OPEN=2, DISQUALIFIED=1, DEAD=1, CONVERTED=2, missing lifecycle evidence=1. Both converted claims link to an accepted-or-later original tenant-owned order; one raw order was specifically rejected as a conversion. Total claimed costs 700 USD minor units, indicative all-opportunity CVR 28.57%, indicative closed CVR 50.00%, indicative eCAC 350 minor units. The fixture excludes a foreign-tenant opportunity and an old record. Tests prove foreign tenant rejection, raw table SELECT denial, missing order conversion rejection, append-only event transitions, zero live migration and no money movement.

**This is fabricated TEST data—not seven real EmpireAI opportunities or verified earnings.**

## Remaining required build steps to commercial truth

1. Independent ownership evidence for all inbound/call/web/CRM opportunity events—including never ordered, declined and abandoned cases; consent and rights review; one controlled canonical source ingestion boundary.
2. Define supported sector/source mappings from actual original data and assure idempotency across calls, visits, buyers, opportunities and orders.
3. Independently attest costs, currencies, buyer order acceptance/fulfilment, cash receipt and later refunds/reversals; reconcile full opportunity population and timestamped historical state to finance.
4. Calibrate cohort time-to-cash and conversion rates against the historical V4.14 holdout; compare naive baselines; then allow separate private dashboard review. Real outbound, paid spend, payment acceptance and economic-memory writes still require owner approval.

**V3.6 observers unchanged. V4.9 existing live readiness unchanged. One EmpireOS, one EmpireDB, one Smart CRM.**
