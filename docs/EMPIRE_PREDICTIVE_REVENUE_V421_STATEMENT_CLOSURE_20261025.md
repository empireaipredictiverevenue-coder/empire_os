# Empire AI Predictive Revenue V4.21 — original six-stage settlement statement closure (HELD)

**25 October 2026 | Same EmpireOS · Same EmpireDB · Same Smart CRM. No trading.**

## Why this V4.21 continuation matters

V4.21 already joins authorised-inbound **claims** → original tenant-owned GTM opportunities → accepted original orders → paired clearing **claims** → refund/clawback **claims** → illustrative net outcomes → frozen 30/60/90 residuals. A bilateral join alone cannot prove it was supplied an entire bank statement. In particular, absence of a claimed bank event is not proof of zero cash, and a 90-day mature order does not prove all of its bank account's later refund windows have been reconciled.

This add-only continuation implements **signed statement arithmetic, sequence and content completeness within one supplied statement window**. It does not change any original production schema, provider, service, payment, training or observer.

## Files

- `empire_os/predictive_revenue_v421_statement_closure.py`: reuses the existing V4.21 bilateral reconciler, signed original Smart CRM membership, simulation-only twin, two separate caller-pinned Ed25519 buyer and bank keys, and source/currency/tenant constraints. Accepts one bank-like, issuer-signed *statement manifest* with account digest, explicit UTC period <=31 days, record counts, transaction sequence range, credit/debit totals, opening and closing bank balances, and SHA256 of the exact signed external event rows in sequence order. It also reports whether that one supplied statement **declares** date coverage across each original-order 30/60/90-day maturation window, keeping all verified-cash eligibility flags false.
- A caller-supplied mapping of every signed external bank event UUID to one statement UUID and integer sequence number. Checks exact one-to-one binding, contiguous bounded sequence, event content hash, correct issuer, bank event time inside the period, event count and credit/debit totals, and `opening + credits - debits = closing` in explicit integer minor currency units. Gaps and discrepancies are emitted by class instead of silently disappearing. Large/forged sequence ranges cannot allocate unbounded memory.
- `tests/test_predictive_revenue_v421_statement_closure_20261025.py`: self-contained deterministic buyer and bank key fixture with fake signed statement and five bank events; tampering and omissions, repeated/gapped sequence, forged totals, wrong currency/tenant, wrong issuer, wrong statement, missing event content, malformed range and an **empty yet internally closed statement that still cannot prove real cash is zero**.

## Fidelity and precise audit limits

The statement closure classification is only:

- `V421_SUPPLIED_STATEMENT_INTERNALLY_CLOSED_HELD` — the **provided**, caller-signed event rows, counts, sequence, digest and balances agree.
- `V421_SUPPLIED_STATEMENT_GAPS_HELD` — there are mismatches in a provided event set, sequence, period, issuer, counts, totals, content digest or balance.

**Internal closure is not independently authenticated bank settlement.** The caller chose the public keys, account digest, claimed period and event population; the reader has no direct access to a bank, custodial clearing account, authentic institution key registry, source provider or payment finality. An attacker controlling a claimed statement and signing key could fabricate a fully consistent statement. The code cannot prove any missing **other** statements, an external statement covering a different time window, or a subsequent refund/clawback. It therefore always returns:

`issuer_public_key_proven_independently=false`, `account_ownership_verified=false`, `complete_bank_account_window_population_verified=false`, `all_bank_statement_windows_provided_verified=false`, `accepted_order_cash_baseline_verified_minor=null`, `training_samples_eligible=0`, `verified_30_60_90_cash_forecasts=null`, `model_weights_updated=false` and `execution_authority=none`.

The previous V4.21 test-style frozen-forecast bridge associates forecasts with an after-the-fact reconciliation manifest digest. That is **not independent proof of an immutable pre-outcome model forecast**; the eventual real calibration flow must instead verify historical forecast timestamps/digests from an independent or tamper-evident audit trail created *before* prediction outcomes, with chronological holdout and verified cash.

## Artificial end-to-end test

A fictional signed account statement covers 12 days. It contains five signed bank events: four CREDITs (total **$224.99**) and one DEBIT (**$20.00**), so an opening balance of **$50.00** reconciles to a stated closing balance of **$254.99**. The original two-order selection still contains one fully matching split-payment order, one short-paid order, and one orphan external credit. Both halves remain visible separately.

The tests demonstrate that dropping a bank event, altering the closing balance or credit amount, duplicating a sequence or changing the signing key breaks the closed-statement classification or is rejected. Even a cryptographically valid empty statement remains unverified cash and cannot become a training example. A 12-day statement cannot cover the original 30/60/90-day order horizons. Even a hypothetical 31-day statement covering a 30-day horizon is only declared calendar coverage, not cash ground truth.

## Exactly what remains for the original V4.21 prompt

1. Verify bank or payment-custodian public keys, account ownership and statement delivery *outside the caller-supplied manifest* through an independently authorised channel.
2. Obtain an authenticated, continuous statement inventory over the original 30/60/90-day opportunity cohorts and refund-finality horizons, not just one internally consistent 31-day segment. Reconcile all orphan external entries and original unpaid orders.
3. Reconcile original source licences, consent, full eligible inbound events, accepted buyer outcomes, bank or BSC USDT finality, unique receipts, fees, refunds and chargebacks. Admit net settled cash only after those checks.
4. Independently verify historic model prediction freezes, use chronological out-of-sample evaluation from the existing V4.14/V4.21 evaluator, and separately authorise future production calibration **only after** trust and performance gates succeed.

**Original migration holds 066–073 unchanged. V3.6 observer and V4.9 live Founder API unchanged. No production DB DDL, cash, outbound, retraining, other-agent changes or new service.**
