# Empire AI Predictive Revenue V4.11 — CRM + Source Rights Gate

**25 October 2026. Scope: Predictive Revenue only. Not trading.**

## Change

Add `empire_os/predictive_revenue_v411_source_gate.py` to the **original** EmpireOS repo. The read-only function `review_revenue_source_candidate_held` ties together:

1. `SignedCrmTenantVerifier` from the existing canonical CRM. A signed, unexpired, pinned-issuer bearer must pass a fresh active tenant-membership check. Caller-supplied user/tenant/role claims cannot bypass this check.
2. `EmpireDbHeldSourceRightsReader` from Predictive Cloud V4.10. It queries an exact source-evidence digest and the authenticated tenant via the dedicated, read-only, restricted EmpireDB interface from prepared migration 066. Any missing database role/table, invalid source proof, expired/revoked candidate, mismatched tenant, or query failure remains HELD.
3. A fixed response with flags explicitly forbidding revenue opportunity admission, customer forecasts, commercial offers, buyer outreach, lead delivery, Redis publishing, recognised revenue, spending, and capital execution.

No new public endpoint, service, database, alternative CRM, credential, trading workflow, or payment path. No import-time network/DB I/O. The review function is **not production-connected by this release** and cannot approve commercial action.

## Verification

- 24 V4.11 negative/signed-CRM fixture tests: native Ed25519 bearer, active vs revoked membership, invalid role/reader, source digests, tenant mismatch, revoked and expired source, forged positive source rows, and all result authority gates false.
- 70 tests passed combined with V4.10 rights reader's real disposable PostgreSQL 18 rehearsal, V4.9 status, and existing status regressions; one inherited dependency warning.
- Previous V4.10 full Predictive Cloud suite: 267 tests passed. No production database migration executed.

## Precise production truth

- V4.9 Founder API readiness endpoint **LIVE** in OBSERVE on loopback `:8766`, operator's verified service override still pinned.
- V4.10 original EmpireDB migration 066 **PREPARED, NOT APPLIED**. Dedicated source-rights login has not been provisioned by this release.
- V4.11 CRM-bound source-rights review **CODE ONLY, HELD, not a production API**, so real licensed source custody and source admission remain unverified.
- No Monte Carlo customer forecast promotion, realised revenue, outreach, Redis promotion, paid traffic, mainnet trading, settlement or banking.

## Next verified work

Owner-approved canonical DB/roles/security preflight for migration 066, **only** after backup/rollback and independent real source-rights audit. Subsequent authenticated private API integration must reuse the original Smart CRM and must not treat `CANDIDATE_REVIEW_HELD` as a verified source. For revenue strategy twins, label synthetic backtests/forecast distributions as simulations until reconciled with real conversions and realised revenue.

**One EmpireOS — one Predictive Revenue / Predictive Cloud — one EmpireDB — one Smart CRM.**
