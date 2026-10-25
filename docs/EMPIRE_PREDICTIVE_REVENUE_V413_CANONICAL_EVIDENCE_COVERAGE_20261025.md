# Empire AI Predictive Revenue V4.13 — canonical evidence coverage audit

Date: 25 October 2026. **One original EmpireOS, EmpireDB PostgreSQL, Smart CRM, Predictive Cloud.** Trading is out of scope.

## What this release does

V4.13 is a **read-only, bounded, non-promoting evidence diagnostic**. It composes the original `SignedCrmTenantVerifier`, which checks real-time active signed CRM membership, with the original `read_recognized_revenue_event` from the existing `predictive_revenue_canonical_reader.py` and canonical EmpireDB REV051/052 role/function. It accepts at most **8 explicit, unique canonical event UUIDs**; no database event discovery or arbitrary source-table SELECT. No new database, root service, credentials, AI agents, routes or financial operations.

It validates that a **single** revenue-recognised event has order-bound tenant/product/price/causal lineage under the existing restricted reader, and returns only bounded diagnostics and event UUID fingerprints. It sanitises query errors and never prints DSNs.

V4.13 deliberately refuses to mistake the evidence for a *cohort* or cash forecast. Original REV051 exposes `amount_cents` for one `revenue_recognized` event but does not prove its currency, funds received, the complete cohort/event census, or the 30/60/90-day cash-lag metric used by the V4.12 twin. A recognised revenue event is not automatically collected cash.

## Explicit non-promotion

- A missing/unavailable event yields **coverage unknown**, not zero realised revenue.
- An injected/mock reader may exercise fixtures but its results never count as independently verified production evidence.
- Even the authentic restricted reader verifies **single events only**; it does not produce a daily, tenant or campaign-level aggregate. The auditor exposes `complete_30_60_90_cohort_census_verified=false`, `event_currency_verified=false`, `recognition_vs_cash_metric_mismatch=true`, and `revenue_forecast_calibration_eligible=false`.
- No automatic model retraining, economic-memory write, source ingestion, outbound, lead delivery, ad spend or capital movement.
- A caller cannot override signed CRM membership or the original V4.12 `SIMULATION`/no-execution contract.
- The existing V4.10 restricted source-rights reader's prepared EmpireDB migration 066 remains **NOT APPLIED**. This release does not change REV051/052 roles or grants.

## Actual release evidence

- New code: `empire_os/predictive_revenue_v413_canonical_coverage.py`
- New tests: `tests/test_predictive_revenue_v413_canonical_coverage_20261025.py`
- **120 tests passed** across V4.9–V4.13 including the isolated PostgreSQL 18 HELD source reader, native signed CRM membership, simulation, forged positive event reader, duplicate/malformed event UUIDs, revoked membership, missing events, false tenant, and expected governance holds. One inherited Starlette/AnyIO warning.

## What is required next for calibrated revenue predictions

1. Original owner-approved canonical **opportunity/cohort membership** with timestamps for the full denominator, not only successful orders.
2. Verified, tenant-scoped commercial event lifecycle and **collected cash receipts**, including refund/chargeback/loss reversals where relevant. Currency and exact units from the authoritative ledger must match the twin.
3. Cohort creation/observation timestamps, source rights, consent where applicable, dedupe, terminal labels, and complete 30/60/90 exposure windows (avoid censoring false negatives).
4. Locked historical train/validation/test time splits, calibration and reliability/bias checks by sector, geography and buyer. Test against simple no-signal baselines and withheld outcomes; monitor drift.
5. ONLY after quality proofs and separate owner approvals should the Founder/Smart CRM dashboard show a calibrated predictive confidence range. Do not present synthetic P10/P50/P90 as a confirmed financial promise.

**Current production reality:** V4.9 read-only readiness endpoint live, V4.10–V4.13 add-only code under governance. This V4.13 diagnostic is not mounted to live API or executing commercial actions.
