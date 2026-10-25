# Empire AI Predictive Revenue V4.21 — continuous bank statement chain (HELD)

**25 October 2026 | Same original EmpireOS, EmpireDB, signed Smart CRM. No trading.**

## Purpose: finish the six-stage reconciliation / 30–60–90 cash-maturity evidence path

The previous V4.21 modules reconcile original tenant-owned orders with *caller-supplied* buyer and bank-like evidence in both directions, then test one internally balanced signed bank-like statement. **One internally closed statement cannot establish a complete 90-day statement history**. A missing intermediate statement, change in account, reset of sequence, different opening balance, or orphan external transaction must be visible before historical cash can even be considered for calibration.

This continuation is a read-only, self-contained analysis of an explicitly supplied **chain of 1–16 signed statement windows**. No new or changed EmpireDB table, daemon, bank API, buyer message, job, payment or model.

### Added files

- `empire_os/predictive_revenue_v421_statement_chain.py` — `review_v421_statement_chain_held` re-authenticates the original signed CRM tenant and invokes existing V4.21 two-way reconciliation across the **full** original order set and **full** caller-supplied bank event set. It verifies each 31-day-or-shorter signed statement by calling the existing statement-closure checker on **only** events whose dates fall within that statement's half-open window.
- `tests/test_predictive_revenue_v421_statement_chain_20261025.py` — deterministically signed four-statement fixture and adversarial cases for missing middle window, overlapping windows and replay, mismatched previous closing/next opening balance, cross-statement sequence discontinuity, source account change, duplicate statement IDs, missing allocation of an external bank event, malformed signatures, wrong signed tenant, unrecognised issuer, duplicate global transaction identities and immature horizons.

### Mechanisms

The chain is restricted to one declared bank issuer, one declared account digest, exactly one authenticated Smart CRM tenant and one currency. Statement windows are sorted, checked for calendar **gaps and overlaps**, and matched across statements using consecutive transaction sequence numbers and equality of the previous declared closing and next declared opening balance. It detects a bank event repeated between two overlapping windows, and an externally supplied event falling in **none** of the supplied windows. Each constituent statement must independently pass content signatures against the **caller-pinned** key, row-count and hash checks, bounded sequence and debit/credit/balance arithmetic.

The chain reports separately whether its declared half-open windows continuously cover from the **earliest selected accepted order** to beyond the **latest** selected order's 30-, 60- and 90-day maturity point. An immature horizon or a missing statement window does not become a false zero, and no standalone bank statement is assumed to cover later refunds.

### Fixture, not finance performance

Four fictional 31-day statements cover 124 days from just before the selected orders' acceptance date. The first contains five signed test transactions (four credits and one debit); later fixture statements contain **zero declared transactions** but are signed, contiguous and linked by unchanged balances/sequence anchors. This proves the **consistency** of the supplied transcript, not that a real bank supplied those empty periods.

The original-order analysis **still finds one short-paid order and one orphan external credit**. Even an internally closed, 90-day-spanning statement chain cannot excuse those commercial discrepancies or prove a full external bank transaction population.

When the middle statement is withheld, the chain flags `STATEMENT_DATE_GAP`; when an overlapping statement repeats an event, it flags `STATEMENT_DATE_OVERLAP` and `REPLAYED_EXTERNAL_EVENT`; when account, sequence or balances change, it reports exact breaks. A new external credit after the last statement is counted as unassigned, not silently dropped.

### What is provable, and what remains held

**Can be tested:** signed manifest validity against *supplied* issuer key, exact records and sequence within the supplied set, stated account/balance continuity, declared calendar horizon coverage, cross-tenant protection and mismatch counts.

**Cannot yet be established:** that the public key is controlled by a real bank or authorised custodian; that all statements for the account were exported; that the supplied events are actual cleared funds; that the original EmpireDB selection covers all eligible opportunities/orders; that all fees, refunds and chargebacks reached finality; that historical forecasts were independently fixed before cash outcomes.

Every output deliberately returns `issuer_public_key_independently_attested=false`, `bank_statement_inventory_complete_verified=false`, `actual_realised_net_cash_minor=null`, `independent_cash_residuals_for_training=null`, `training_samples_eligible=0`, `production_model_weights_updated=false`, `funds_moved=false`, `execution_authority=none`. It cannot activate live CVR/eCAC or cash forecasts.

### What it would take to activate V4.21 with real observations

1. Obtain permitted **bank/treasury origin evidence** from the actual financial institution, and verify issuer identity and account owner through an independently controlled enrolment process. For BSC USDT, independently prove payment transaction ownership, token contract, confirmation finality, BSC chain logs and subsequent reversals before accepting value.
2. Ingest a **complete, owner-authorised account-period statement inventory**, not self-selected events, with unalterable delivery receipts, unique references, contiguous date windows and every unmatched external transaction. Obtain official chargeback/refund and fee histories for each cohort's maturation horizon.
3. Reconcile with canonical original EmpireDB accepted orders, GTM opportunity denominator, source rights and acquisition costs. Keep unknown amounts NULL rather than zero until verified.
4. Compare independently timestamped **pre-outcome frozen forecasts** to final net cash on chronological holdouts using the existing V4.14/V4.21 performance gates. Model training and financial activation require separate explicit approvals.

**Production migrations 066–073 remain HELD. Original V3.6 and V4.9 observers unchanged. No new SQL migrations, money, outbound, paid traffic, trading or model promotion.**
