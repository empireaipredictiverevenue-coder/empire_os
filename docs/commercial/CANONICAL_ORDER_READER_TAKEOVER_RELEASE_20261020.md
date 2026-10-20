# Canonical Order Reader — founder-directed engineering takeover

Date: 20 October 2026
Integration branch: `feature/canonical-order-reader-takeover-20261020`
Clean worktree: `/home/ubuntu/empire_worktrees/canonical_order_reader_takeover_20261020`

## What is included

- `empire_os/execution_bus_data_repository.py`: the original owner's 367-line uncommitted canonical order/verified outcome reader and outreach/causal-lineage reader. The **exact source bytes** were copied from the live owner's dirty file to the clean worktree and SHA256 compared before any edits. No unrelated runtime/database/CRM files copied.
- `empire_os/commercial_terms_materializer.py`: its 98-line uncommitted dependency, including validated persisted approved/accepted terms. The source was copied and hash checked.
- Four existing tests were made resilient to the verified order-reader method becoming committed and importable: `test_canonical_order_reader_release_integrity.py`, `test_verified_commercial_order_operator.py`, `test_commercial_buyer_ops_integration.py`. The missing method is now simulated explicitly rather than assumed absent from the installed code.
- No migration, service, timer, background worker, write action, prospect promotion, buyer outreach, payout, model retraining or automatic transaction intake.

## Actual verification

On the **clean worktree** with those two original owner source files and updated compatibility tests, the broad commercial, financial, original-owner, Ops Control and Founder Console suite reported **508 passed, one pre-existing Starlette/anyio deprecation warning**.

The previously failing original-owner suites `tests/test_outreach_verified_outcome_runtime_bridge.py`, `tests/test_runtime_causal_lineage_continuity.py` and `tests/test_verified_outcome_learning_continuity.py` now report **178 passed** together in the clean worktree.

## Security and authority boundary

The source reader uses existing `CanonicalDataGateway` and `DataFilter` / `OrderSpec` read paths. It does not create a new DB credential or grant tenant authority. A clean source commit and a passing synthetic test do **not** validate real provider payments, RLS, production tenant access, read-only login, actual order existence or production financial correctness.

The existing `canonical_order_reader_release_integrity` guard detects if the source at the live Git HEAD matches what the process can run. That only establishes code integrity; it deliberately continues to report `original_owner_release_attested=False`. A legitimate original canonical tenant+order identity and approved read-only DB access are still necessary before invoking the manual exact-order CLI. No global order or customer sweep.

Caution: `outreach_performance_records` is a separate owner-wide research/analysis read path. Do **not** use it for unauthorised tenant discovery or assume a capacity/lead count is buyer proof. Its use is subject to the original owner's authenticated database permissions and row policies.

## Safe canonical promotion

The production checkout contains ~193 unrelated uncommitted entries belonging to other agents. A normal fast-forward cannot safely overwrite the two already-dirty source files; their contents were copied **byte-identically** into the isolated commit instead.

Promotion should use only the six reviewed paths and this handoff, with hash / clean-test / live HEAD preflight, without staging or committing any other file. Preserve the existing Ops timer and verify the next observe-only Ops cycle.

Do not count real revenue or start financial training as a result of this code commit.
