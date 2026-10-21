# Predictive Cloud framework — 21 October 2026

Owner: this Predictive Revenue / Predictive Cloud development worktree and its existing Cloud service. Canonical source: EmpireDB PostgreSQL. No Supabase, separate new agent, payments, marketing send, QPU job or customer write.

## Live before this candidate

The original owner deployed immutable Cloud guard `f4fe409c56fa` under `/opt/empire/predictive_cloud_guard_f4fe409c56fa`. Systemd `empire-predictive-cloud-materializer.service` and its original two-minute timer were verified running successfully. Both trend and formula materializations explicitly reported `prediction_ready=false`; 28/28 status components had readable artifacts. Two were stale: `optimization_fabric` (2 October) and `founder_directives`. Two had unknown source freshness: `commercial_loop` and `astra`. A component artifact's existence was not proof of authentic customer forecasts.

## New work owned and tested

1. The Cloud status builder classifies materially future-dated source evidence as `future_untrusted`, not fresh, and reports fresh counts, stale and unknown sources, and separate framework/runtime health versus customer forecast approval. Unknown, old and future records remain visible as diagnostics without creating false claims.
2. The read-only Cloud status API validates a bounded v2 snapshot: schema, age, overall OBSERVE authority, no payment/outbound/customer forecasting flags, exact known component inventory and arithmetic, matching per-component observation timestamps and freshness labels. Symlinks and oversized/stale/forged JSON are refused. Unrecognized top-level JSON keys are not copied into its response.
3. The existing Cloud runner now invokes the **existing** local `optimization_status.refresh_optimization_status` before the Cloud status refresh, which refreshes the formerly stale solver inventory at the normal two-minute cadence. It only checks installed local solver runtime and source-readiness metadata. It does not solve a commercial action, run external QPUs, call paid providers, enable spend or authorize model mutation.
4. The root-only guarded successor upgrade pins an exact Git commit and SHA-verified release, verifies the installed prior guard, keeps an original drop-in and runtime rollback copy, switches only the Cloud materializer, checks live source admission and optimisation/source freshness, and restores its timer. It explicitly leaves the Founder API and other agents' services untouched.

## Important remaining distinctions

- Cloud **code/wiring** can be fully installed and tested even when genuine forecast science cannot be empirically calibrated; zero real terminal cohorts and missing pre-outcome immutable forecast receipts still prohibit customer prediction delivery. Source-reported numbers are never silently accepted.
- The `founder_directives` artifact is stale and `commercial_loop`/`astra` have no trustworthy source observation timestamp. Do **not** update these timestamps to today's date without actual source-owner observation or repair. Cloud health will remain appropriately partially held until those source contracts are improved.
- The Founder dashboard API is a *separate heavily overlaid running service* (`empire-founder-dashboard-api.service`). This branch updates the Cloud status API's source code and validates it against the actual Cloud snapshot, but does not hot-restart or replace that multi-owner service. That precise API module promotion requires its own guarded overlay/rollback integration, not a broad root code overwrite.
- No original customer records were created. No forecast registry, financial receipts, or revenue were manufactured. `framework_operational` is a source-freshness metric, not proof of product/commercial readiness.

## Safe operator follow-through

Apply only the reviewed immutable Cloud upgrade using `scripts/upgrade_guarded_predictive_cloud_framework_20261021.sh --apply-owner-approved-observe <full commit>` after it passes `--check`. This does not require updating original `/srv/empire_os` code and retains the prior root-owned Cloud release as rollback.
