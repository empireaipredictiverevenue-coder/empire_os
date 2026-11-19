# Empire AI Productivity Driver — scoped completion handoff (19 November 2026)

## Authority and source of truth
- Branch: `feature/completion-productivity-driver-20261119`, isolated worktree.
- No deployment, remote push, live checklist modification, database change, financial action, outbound action, service restart or new timer.
- Existing department cycle owns the completion monitor and existing department dispatch. The Productivity Driver is a pure, read-only section of the existing completion-monitor snapshot; it does not own a new queue.

## Root cause corrected
- Canonical checklist includes a pending oversized identity row (line 1292, Social Search Console).
- Existing business completion dispatcher correctly holds that invalid identity, so its 287 eligible tasks differ from the 288 pending checklist rows.
- The completion monitor had incorrectly required 287 reconciled entries to equal all 288 pending rows, leaving the monitor HELD.
- The reconciler now carries the exact rejected line-count and line-identity evidence; the monitor independently checks those rows really fail shared task-key validation, then tracks valid tasks without dropping or marking the held row done.

## Implemented
- `empire_os/completion_reconciliation.py`: preserve invalid stable-identity hold count and line evidence.
- `empire_os/completion_task_monitor.py`: strict identity-hold accounting, fail-closed mismatches, no forged task identity; attach deterministic productivity review.
- `empire_os/productivity_driver.py`: existing-owner priority review, revenue-evidence weighting, per-task required proof/gate, no automatic dispatch/approval.
- `tests/test_completion_task_monitor.py`: regression and end-to-end tests for held-identity propagation, gate preservation, prioritisation, and hostile authority values.

## Verification
- Focused integration suite: 75 tests passed before final priority adjustment.
- Affected tests: **103 passed, 1 deselected**, 1 third-party deprecation warning; final priority change included in this run.
- Deselected test `tests/test_completion_task_memory.py::test_genuine_new_implementation_request_still_allowed_after_plan_only`: independently fails identically in unchanged canonical checkout with `HELD_STALE_REMOTE_BASE` rather than expected `QUEUED`. The remote `agent/data-cloud-wave4` ref differs from live local HEAD. Do not bypass the remote-base gate; reconcile branch authority separately.
- Live data, read-only in-memory replay (not deployed): canonical SHA-256 matched dispatch source ref; checklist 887, marked DONE 599 (not production proof), pending 288, trackable 287, explicitly held invalid-identity row 1 (line 1292). 287 ranked review candidates. Zero actions dispatched, zero financial/outbound authority, zero claimed commercial outcomes.

## Release gate
- **Implemented and tested in isolated branch; not live**. Founder-approved main checkout integration and guarded cycle verification remain outstanding.
- Release readback must confirm the existing `runtime/execution_plane/completion_task_monitor_latest.json` timestamp advances, `task_monitor.status` becomes AVAILABLE, identity hold remains count 1, genuine owner tasks have correct state and proof gates, and no external actions occur.
- Existing provider-capacity holds and stale remote-base authority remain separately observable; this work does not remove them by weakening governance.
