# Empire AI Predictive Revenue V4.21 — two-way reconciliation & frozen forecast residual continuation

**25 October 2026 | Original EmpireOS, EmpireDB and Smart CRM only | HELD / OFFLINE**

## Same original V4.21 handoff — the previously missing second direction

V4.21's `073` bounded SQL view joins the original GTM opportunity, source/event claims, original accepted order, matching *claim*, and refund *claim*. It correctly refuses to certify bank cash. However that tenant-originating reader cannot enumerate **bank-originated payments with no matching EmpireDB order**. Nor can source/bank reference hashes by themselves prove that an independent bank issued an authoritative statement. This extension supplies a **pure offline two-way ledger analysis**, not an importer, parallel database or new production service.

### Additive release files

- `empire_os/predictive_revenue_v421_dual_entry.py`: existing V4.12 research-only twin and Ed25519 signed Smart CRM active-tenant membership, exact source/currency/tenant and UUID checks. Accepts a bounded caller-supplied snapshot of **original accepted orders**, **buyer remittance advice** and **external bank CREDIT/DEBIT event records**. Verifies cryptographic Ed25519 document signatures against explicitly pinned *caller-supplied* buyer and bank public keys; rejects invalid signatures, duplicate IDs, buyer-bank key reuse, future events and tenant/currency crossover. Supports multiple clearing tranches for one order and multiple later refunds or clawbacks. Checks original gross amount, buyer advice, cleared credit amount, chronology and refunds not exceeding paid credits. Counts both missing internal settlements and foreign-to-the-selection external credits/debits, including orphan order references. Does not silently discard foreign receipts or treat absence of a bank event as zero realised revenue.
- **Frozen forecast bridge** `review_v421_two_way_forecast_residuals_held` in the same module: re-verifies signed Smart CRM and research twin; requires a matching manifest digest and three exact 30/60/90 forecasts each frozen before the cohort's first accepted order. Compares to matured **claimed** net receipt timelines and returns signed residuals. Incomplete horizons return NULL, and even a fully matched signed claim batch never updates model weights or creates verified economic memory.
- `tests/test_predictive_revenue_v421_dual_entry_20261025.py`: deterministic Ed25519 fixture signatures for buyer and bank pseudo-documents, positive 1-to-many clearing, per-order mismatch, orphan bank entries, over-refund, invalid key/signature, duplicate records, replay/cross-tenant/currency, out-of-order refunds, future settlement, 30/60/90 maturity and frozen forecast residual anti-forgery. Test fixtures are fictional.

### Important trust boundary

Valid cryptographic signatures **prove only that a document was signed by a key whose bytes the test caller supplied**. The code cannot independently attest whether those keys belong to the bank or buyer, whether the bank cleared real money, whether the complete statement/ledger population was supplied, or whether another refund or chargeback occurred outside the submitted manifest. Caller-supplied original-order snapshots are also **not authenticated original EmpireDB financial extracts**.

Accordingly, `all_supplied_claims_reconciled=true` is **not** independently verified settlement; `actual_realised_net_cash_minor=null`; `training_examples_eligible=0`, `model_weights_updated=false`, `production_calibration_authorized=false`, `economic_memory_written=false`, `funds_moved=false`. Do **not** switch these gates on based on this release or on any 95%/100% coverage claim.

No migration added or applied in this continuation. All production DDL 066–073 remain HELD. No live V3.6 observer, original API, database schema, wallet, outbound or production model changed.

### Fictional acceptance example — USD integer minor units

Two original orders: one for **$150.00** with **$10.00** claimed acquisition cost; one for **$70.00** with **$3.00** claimed acquisition cost.

A signed buyer advice matches each, but external bank-like events show $100 + $50 credits and a later $20 debit for the first; only a $65 credit for the second; and an additional **orphan $9.99 external credit** that references no selected order.

**Matched order candidates: one. Discrepant selected orders: one. Orphan external credits: one.** Selected-order nominal receipts $215.00; debit $20.00; claimed acquisition cost $13.00; resulting illustrative net **$182.00**. The orphan external $9.99 is counted **separately**, not silently added to tenant's recognised revenue.

Per accepted-cohort 30/60/90-day claimed net: $202.00 / $182.00 / $182.00, reflecting that the $20.00 reversal appears after day 30. Separately supplied hypothetical frozen forecasts $200.00 / $195.00 / $180.00 produce research residuals +$2.00 / −$13.00 / +$2.00, **not bank-verified model feedback**.

### Exact remaining V4.21 production prerequisites

1. Approved original EmpireDB owner/scope for each original opportunity and order, with full eligible external and internal transaction inventory; allow for split remittances, rejected orders and refunds. A list of selected orders is not a whole-of-bank-statement census.
2. Trusted independent buyer/bank issuer enrollment: obtain and verify pinned public keys from a separately authorised organisation, not keys supplied in the same payload as alleged receipts. Resolve chain-specific treasury ownership, USDT BSC finality, fees and exchange conversions independently when relevant.
3. Match both unmatched original orders and unmatched *complete* externally issued statements; reconcile chargeback/dispute finality and fees, not just amounts and digests.
4. Only after independent authority proofs, complete cohorts and immutable historically frozen predictions are verified may the existing V4.14/V4.21 holdout evaluator consume **genuine 30/60/90 net cash actuals**, requiring model performance superiority before any separately approved live training promotion.

**Original V4.21 six-stage handoff continued. No drift, new trading subsystem, new database, live spend or financial action.**
