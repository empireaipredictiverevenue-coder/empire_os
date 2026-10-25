# Empire AI Predictive Revenue V4.15 — tenant-bound BSC cash-evidence candidate

**25 October 2026 | Original EmpireOS · Original EmpireDB PostgreSQL · One Smart CRM · NO trading**

## Production-safe scope

A prepared owner-controlled cash evidence bridge, NOT a money activation, payment transfer or revenue recognition service.

- `migrations/empiredb/067_predictive_direct_bsc_cash_candidate_held.sql` — **PREPARED, NEVER APPLIED TO PRODUCTION**. It requires the pre-existing non-login `empiredb_migrator`, native `empire_current_tenant_id()` (trusted `session_user` tenant binding), and a **separately owner-created**, privilege-limited `empire_predictive_cash_candidate_reader` NOLOGIN capability with zero incoming grants. It creates one restricted read-only function only after preflight. It creates **NO login**, database, grant to app role, HBA rule, key, appointment, cron timer or payment movement.
- `empire_os/predictive_revenue_v415_direct_cash_reader.py` — reuses the original `SignedCrmTenantVerifier` and the V4.12 simulation-only twin identity, then checks the independently owner-provisioned `empire_predictive_cash_candidate_login` session and NOLOGIN capability. The session is `READ ONLY`, bounded to **1–8 distinct exact order UUIDv4/v7** and the signed CRM tenant, with a 4-second statement timeout. Query failures return HELD and never expose passwords or source raw records.
- `scripts/rehearse_predictive_revenue_v415_cash_reader_20261025.sh` and paired Python script — provision real disposable PostgreSQL 18 fixture source rows and isolated SCRAM login only under `pg_virtualenv` with strict ephemeral data-directory/port checks. Test actual migration, tenant-scoped SQL, dedicated login, direct source table denial, and the **actual signed-CRM → Python reader → PostgreSQL function** sequence. The disposable cluster is dropped.
- `tests/test_predictive_revenue_v415_direct_cash_reader_20261025.py` — checks membership, tenant, exact orders, malformed/overprivileged rows, invalid source amounts/flags, absence, SQL role constraints and real isolated PostgreSQL.

## What counts as a V4.15 positive candidate

A returned `DIRECT_USDT_BSC_TRANSFER_CANDIDATE_HELD` row is limited to:

- Original order has the same tenant-bound buyer, `settled/outcome_captured` state and a settlement timestamp.
- Approved **direct** BSC payment request belongs to the same order/buyer, with matching commercial terms and exact nominal request amount (`USDT * 100 = USD cents`).
- Existing BSC evidence row matches the request and order, has BSC chain ID 56, the pinned USDT contract, >= 12 confirmations, matching treasury address/terms, evidence before the bounded read and exact 18-decimal raw token amount.
- Exactly **one** qualifying proof row. Zero, multiple, foreign-tenant, escrow, low-confirmation or otherwise inconsistent evidence remains `NO_UNAMBIGUOUS_DIRECT_BSC_EVIDENCE_HELD`.

This is **not independent on-chain validation** of the provenance of an inserted evidence row, nor does it check refunds, chargebacks, reversals, cross-chain transfers, treasury balances, banking finality, contract release disputes or the complete population of opportunities. Source tables and dependent original verifier/issuer roles need an independent Security/Finance review.

A buyer pricing field named `price_cents` is aligned to the original USD/USDT settlement convention; it **must not** be treated as collected GBP/EUR cash. The V4.12 synthetic twin explicitly preserves GBP/USD/EUR as separate currencies.

## No hidden promotion

- Every response is `mode=OBSERVE`, `execution_authority=none`, `actual_cash_collected_minor_units=null`, `revenue_forecast_calibration_eligible=false`.
- An injected/mock `connect_factory` **cannot report positive candidate counts**. Tests are marked held. The default `psycopg.connect` and exact authenticated reader are required to report even the restricted candidate count. The DSN endpoint itself is **not independently attested** by this read: `database_endpoint_independently_attested=false` remains present even on a matching response.
- No source-rights promotion, forecast calibration, auto-learning, CRM mutation, buyer outreach, lead delivery, capital allocation, paid traffic, live trading, payment execution or economic-memory write.
- The read covers only an **explicit selection**, not an authenticated full-cohort census. Missing or incomplete results mean unknown, not zero.
- V4.10 migration 066 is separately prepared and unactivated. V4.15 does **not** grant new source ingestion rights by creating the function.

## Founder/DBA gate to real data

**Do not run 067 against original production EmpireDB in this release.** Before a subsequent owner-authorised step: reconcile role/RLS/parent schema and migration order, verify backup & rollback, inspect all actual BSC chain/contract evidence and settlement pipeline, independently approve source terms and privacy obligations, create a dedicated NOLOGIN reader capability with no other grants and a separately managed SCRAM login/active tenant role binding under Security policy, inspect HBA and rotation, prove direct parent-table privileges denied, then explicitly authorise migration and separately reviewed activation.

Even after a subsequent 067 activation, its status would remain HELD and could not activate finance. A later version must separately prove **complete time-bounded opportunity cohorts, refunds and all revenue/cash finality**, then compare immutable pre-event forecasts with true observed outcomes before claiming calibrated 30/60/90 cash predictions.

**No Stripe payouts, no paid traffic, no new database, no root daemon, no duplicate bots.**

## Verification

Disposable PG18 fixture proves direct BSC transfer candidate, buyer/org isolation, transfer with insufficient confirmations, escrow not inferred, duplicate list refusal, full native CRM/PG read, direct source table denial and zero production DB changes. The original V4.9 live API remains OBSERVE; no production migrations were applied by this release.
