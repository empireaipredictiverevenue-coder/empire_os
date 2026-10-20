# Empire AI — Canonical Order Reader Release Integrity

Date: 20 October 2026
Branch: `feature/verified-order-reader-release-gate-20261020`
Isolated worktree: `/home/ubuntu/empire_worktrees/verified_order_reader_release_gate_20261020`

## Objective

Get the existing authenticated-order operator into maintainable production readiness **without** promoting the other original owner's unfinished code or making up financial proof.

This release makes the current Ops Control read the original ExecutionBusDataRepository release state accurately, and prevents the manual order proof CLI from attempting an uncommitted implementation.

## Implemented

- `empire_os/canonical_order_reader_release_integrity.py`: allowlisted original-owner source integrity monitor. Requires the exact Git worktree, reads the original owner file, compares SHA256 of its bytes with `HEAD:empire_os/execution_bus_data_repository.py`, parses the checked-in Python AST to find the expected `verified_outcome_feedback` method signature, and checks whether the method is callable in the actual running process.
- This probe explicitly distinguishes: invalid source, dirty/uncommitted source, no committed reader, committed reader not loaded, and committed/loaded reader whose owner deployment approval is **still outstanding**.
- No database/API access or real order query happens during this probe. Source hashes are change receipts only, not authenticity, buyer activity or payment proof.
- `commercial_adaptive_ops_bridge.py` surfaces the integrity report and its first/unchanged/changed transition through the **existing** Ops Control latest snapshot and existing Founder Ops API status. The existing Ops timer holds memory from the prior snapshot.
- `scripts/review_verified_commercial_order_20261020.py` checks source Git integrity **before** reading the DSN and before starting any database transaction. It will not use an uncommitted method even if it is callable at runtime.
- `tests/test_canonical_order_reader_release_integrity.py` uses disposable TEST-only git repositories with both checked-in and dirty versions of a mock owner method. Includes tampered source, forged authority and no extra dispatch. Existing operator and sandboxed entire Ops-cycle tests are extended.

## Observed original-owner deployment reality

On 20 October 2026, the live canonical repo `/srv/empire_os` had **193 unrelated dirty entries**, among them an approximately 367-line uncommitted change in `empire_os/execution_bus_data_repository.py`. The live Python method existed, but the committed source did not yet carry the implementation. The probe correctly found `ORIGINAL_OWNER_SOURCE_DIRTY_RELEASE_HOLD`. Existing original verified outcome and causal lineage tests were also run on the live code (178 passed), which is useful technical evidence but not a commit or an owner approval.

**Do not** cherry-pick or overwrite that owner's dirty `execution_bus_data_repository.py`. The existing owner must finish their own integration, permissions and release review. This adaptive change simply follows that source once it becomes committed.

## Next actual commercial progression

1. Existing canonical repository owner commits and reviews `verified_outcome_feedback`, including tenant row authority, exact original payment/settlement evidence and approved cost lineage.
2. The next Ops Control cycle updates `adaptive_commercial_summary.original_order_reader_release_integrity`. It reports the changed release state without claiming an order.
3. An existing authenticated owner with an approved **read-only** EmpireDB login can invoke the exact-order CLI for one explicitly known tenant and order; no global search, credential echo or synthetic production records.
4. The canonical owner verifies the selected actual order's provider evidence, payment settlement, revenue recognition and observed cost. Incomplete evidence is UNKNOWN, not $0.
5. The existing predictive decision owner supplies its authentic **pre-outcome** prediction if one exists. An in-memory Brier calculation can only become calibration-ready after the original prediction custody is independently checked. Model weights, spending and pricing remain unchanged until existing finance/model-review owners approve.

## Safety / ownership boundaries

- This is a Git/source release-integrity observer, not a signing service. **No method presence or source commit is proof of tenant rights, order existence or owner release approval**. The output keeps `original_owner_release_attested=False`.
- No new tasks, timers, agents, buyer activation, CRM/database writes, emails, payments, or price/spend changes.
- No raw buyer names, tenant IDs, contact details, order IDs, original receipt records, source contents, errors or DSNs are emitted to Founder Ops.
- No synthetic commercial evidence enters production; offline tests use synthetic mock repositories only.
- Global Ops Control never reads all orders or enumerates tenants.

## Verification / deployment

Run new integrity tests, exact-order operator tests, original owner verified outcome tests, full sandbox Ops-cycle tests, existing commercial/Sales Director/Buyer Scout/Revenue OS/Founder Ops regressions. Check latest committed canonical HEAD and avoid all 193 dirty paths in the concurrent live tree. Controlled promotion to existing Ops Control only; preserve the timer's observe-only mode and do not attempt an original DB read without an authenticated tenant/order.


## Clean-checkout owner test dependency (explicit release blocker)

A broad combined test run including `tests/test_outreach_verified_outcome_runtime_bridge.py` and `tests/test_runtime_causal_lineage_continuity.py` produced **438 passed, 66 failed** in the clean committed checkout. The failures are missing original-owner repository methods such as `outreach_verified_outcome_record()` and `verified_outcome_feedback()`, which are present in the live checkout's **uncommitted** owner implementation. They are not regressions introduced by the integrity observer. Those original owner suites were separately run against the live dirty checkout (178 passed).

After scoping the test run to code actually present in the clean committed baseline plus this integration, **369 tests passed**. Do not report the entire original-owner outcome feature as clean/releasable or interpret the 369 passing tests as fixing the 66 dependent owner tests.

The release of the canonical reader and all original-owner tests is **blocked until that owning agent publishes its implementation into a clean commit and passes its own full regression tests**. This branch intentionally does not modify that owner's repository file.
