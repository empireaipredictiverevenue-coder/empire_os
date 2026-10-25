# Empire AI Predictive Revenue V4.16 — original operational reversal investigation

**25 October 2026 | Predictive Revenue only | Additive HELD release**

## Purpose

Use the existing EmpireDB `commercial_outcomes` ledger as an **operational warning signal**, not as verified evidence that a payment was refunded, reversed, charged back, financially settled or earned. Our V4.15 reader can identify an explicitly selected direct USDT/BSC settlement evidence **candidate**, but cannot close refund finality. V4.16 adds the missing distinction between a refund-like *delivery outcome* and an authoritative financial reversal.

## Deliverables in one EmpireOS

- `migrations/empiredb/068_predictive_revenue_operational_reversal_signals_held.sql` — **PREPARED, NOT APPLIED to production**. Requires the pre-existing 067 read-only function, original `empiredb_migrator`, existing `empire_predictive_cash_candidate_reader` NOLOGIN capability, owner SELECT on existing `commercial_outcomes`, and original tenant resolver. Adds only one `STABLE SECURITY DEFINER` bounded read function; no new DB/table/LOGIN/role or payment authority.
- `empire_os/predictive_revenue_v416_operational_reversals.py` — validates the original Ed25519 signed CRM membership, V4.12 research-only twin, exact 1–8 distinct order IDs, and original V4.15 SCRAM login/capability. Opens a read-only query with a 4-second statement timeout. Source data is scoped by the *original* order buyer's `buyers.org_id` and the login-bound `empire_current_tenant_id()`.
- `scripts/rehearse_predictive_revenue_v416_reversals_20261025.sh` + paired Python fixture — actual disposable PostgreSQL 18 with original schema-shaped buyer/order/direct-payment and operational outcome records; applies 067 and 068 **to disposable DB only**, verifies exact SQL statuses, foreign tenant non-disclosure, duplicate selection rejection, restricted direct table denial, and original signed CRM through the real psycopg path. Automatically drops temporary PG18 cluster.
- `tests/test_predictive_revenue_v416_operational_reversals_20261025.py` — positive observation fixture, rejection of forged financial-refund flags and overprivileged responses, tampered CRM, mismatched tenant, unknown order, non-ephemeral protection and actual PG18 integration.

## Four possible read outcomes

| Operational delivery review | Meaning |
| --- | --- |
| `REFUND_LIKE_DELIVERY_SIGNAL_HELD` | At least one same-tenant order outcome has `delivery_outcome='refunded'`. **This is not monetary reversal evidence.** |
| `FAILED_OR_REJECTED_DELIVERY_SIGNAL_HELD` | At least one operational `failed` or `rejected` delivery result is recorded. |
| `NO_REFUND_LIKE_DELIVERY_RECORD_OBSERVED_HELD` | The selected order had no matching refund-like/failure rows in the reader's bounded query. **Does not prove that no refund or chargeback occurred.** |
| `ORDER_NOT_VISIBLE_OR_UNKNOWN_HELD` | Missing or foreign-tenant order. No existence or financial-status details leaked. |

Statuses are mutually exclusive summary categories; when both refunded and failed records exist the refunded category takes precedence, but both bounded counts are returned. Counts are capped at 100,000 per explicitly selected order. The record itself does not verify its own source authenticity, provider rights or payment completeness.

## What it cannot claim

Every result stays `OBSERVE`, `execution_authority=none`. All independent financial attestation flags remain false; `net_cash_earned_minor_units=null`, no model retraining or economic-memory writes, no additional buyer communication, no paid media, no trade, no live finance action, and no API runtime activation.

The connector enforces the dedicated login and session-scoped NOLOGIN role, but the caller-supplied DB endpoint is not independently attested. Mock connectors never count operational signals as independently sourced. Original V4.10 rights migration 066, V4.15 SQL 067 and new 068 are all **held pending individual DB owner approval**, not production-applied.

## Next evidence gates

1. **Provider-backed financial reversal and transfer proof:** reconcile original BSC transaction evidence with later chain events, treasury balances, refunds, disputes and off-chain bank rails under independent custody.
2. **Complete tenant-bound cohort denominator:** introduce an audited original-DB reader for *all* eligible opportunities over a specified historical cut-off. V4.15/16 only reads up to 8 pre-selected orders, so cannot assert complete revenue or a conversion rate.
3. **Time-locked forecasts and actual cash outcomes:** join settled receipts, recognised commercial events, operational delivery outcomes, and final reversals to each cohort with timestamp and currency. Keep USD/USDT separate from GBP/EUR unless an independently verified FX record exists.
4. **Historical holdout validation:** only real, independently finalised outcomes may promote V4.14 MAE/WAPE, skill and calibrated 30/60/90 P10/P50/P90; no synthetic cash promotion.

**One EmpireOS, one original EmpireDB, one Smart CRM. No root daemon or duplicate trading architecture.**
