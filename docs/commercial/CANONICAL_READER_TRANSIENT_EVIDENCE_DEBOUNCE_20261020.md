# Empire AI — Canonical Reader Source-Check Noise Control

Date: 20 October 2026
Worktree: `/home/ubuntu/empire_worktrees/adaptive_reader_transient_noise_control_20261020`
Branch: `feature/adaptive-reader-transient-noise-control-20261020`

## Why this is needed

The live original owner `execution_bus_data_repository.py` was being edited while the existing observe-only Ops Control timer was executing. This is a valid reason for a Git/source-integrity check to temporarily fail. A source check that cannot finish does not mean a reader has been approved, released, withdrawn or newly verified.

## Behaviour change

`empire_os/canonical_order_reader_release_integrity.py` now outputs a separate *transition* state `ORIGINAL_OWNER_SOURCE_TEMPORARILY_UNAVAILABLE_HOLD_NO_REVIEW` when the original file-to-Git integrity proof cannot be completed. It preserves only the **last confirmed allowlisted original-owner release status** inside the existing Ops snapshot memory for comparison.

When the original source becomes readable again, a status identical to the last confirmed status produces `UNCHANGED_ORIGINAL_OWNER_RELEASE_HOLD`, rather than duplicate owner attention. A genuinely new committed/loaded state produces `ORIGINAL_OWNER_RELEASE_INTEGRITY_CHANGED_REVIEW_REQUIRED` for the **existing** owner lane. No job is created.

The currently inspected integrity packet remains unknown and blocked on any failed check. Retained memory **is not reused as current proof or authority**. Injected or malformed previous transition state is ignored. No contact, original order or tenant IDs are stored in this release-transition memory.

Existing `commercial_adaptive_ops_bridge.py` passes its previous safe transition packet to the pure reviewer inside the **same** Ops Control service; no timer, database table or new scheduler.

## Operational boundary

The canonical reader remains part of the original owner's dirty file. Before its owner publishes a clean commit, the exact-order operator remains blocked and no real financial totals or buyer outcomes can be claimed.

Original owner clean-checkout tests dependent on the unpublished methods previously failed (66 failures), while 178 owner tests passed against the live dirty tree. This increment does **not** modify or publish those owner methods.

The Git observer's status may remain `ORIGINAL_OWNER_SOURCE_INTEGRITY_NOT_PROVEN` temporarily under systemd. That is a safe unknown, not a verified release. No payouts, outreach or other commercial execution authority is granted.

## Verification

Synthetic Git checkout tests cover current method committed/uncommitted, transient Git check failures, repeated unavailable states, recovery to the last confirmed state, and real source publication after a gap. End-to-end sandbox Ops Control tests confirm fail-closed source handling. After controlled promotion, inspect the two fields `adaptive_commercial_summary.original_order_reader_release_integrity` and `adaptive_commercial_summary.original_order_reader_release_transition` in the existing Founder Ops snapshot.

No revenue or buyer claims are derived from TEST fixtures. No production financial or contact records are modified.
