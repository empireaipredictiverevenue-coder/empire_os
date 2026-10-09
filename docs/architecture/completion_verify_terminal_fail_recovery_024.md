# Completion 024 — Terminal VERIFY FAIL Recovery

## Incident
The completion reconciliation on 2026-10-09 classified three engineering
rows as NEEDS_WIRING_OR_TEST_FIX, all bound to one VERIFY job
`coder_job_b97cb7b6fec14db8886e070011878361`.
That job was in `runtime/coder/jobs/completed/`, with
`status: COMPLETED` but deterministic
`result.verification.verdict: FAIL`. The old recovery implementation
scanned only `runtime/coder/jobs/failed/`, so it never queued a retry.

The current full Astra / Agent Execution Plane regression was separately
rerun on main: 113 tests passed on 2026-10-09. This is not itself a
new completed VERIFY job and not a proof of live functionality.

## Narrow change
The existing `completion_verify_recovery.py` now admits two sources:
1. existing terminal FAIL bucket VERIFY records as before;
2. **only** completed VERIFY jobs with exact `verdict: FAIL` AND an ID
   referenced by the current completion reconciliation for unresolved
   NEEDS_WIRING_OR_TEST_FIX items.

No stale completed failures without current association, no completed PASS
jobs, and no other job types are eligible. The existing SHA-256 fingerprint
of the required files/tests, source job ID, unresolved item IDs and
`completion_verify_recovery_key` enforce once-per-source-content idempotence.
It does not loop on an unchanged failure or infer outcome from a queued job.

The existing `scripts/run_coder_verify_drain.py` can process the resulting
single read-only VERIFY. The new verdict is independent from the old job.
The three checklist items move from test repair to NEEDS_LIVE_PROOF only on
a new successful verifier receipt; they are NOT automatically marked DONE.
Later current operational proof is still required.

## Safety
No new timer, agent model, production code implementation, outbound, funds,
database migration, revenue recognition or founder gate is modified.
The test fixture uses real temporary Git repositories to comply with the
existing safe-workspace policy. It does not touch an unrelated in-progress
edit to `tests/test_completion_verify_recovery.py`.
