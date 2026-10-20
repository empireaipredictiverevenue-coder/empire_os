# Empire AI — Existing Ops Control Adaptive Commercial Memory

Date: 20 October 2026
Isolated worktree: `/home/ubuntu/empire_worktrees/video_commercial_framework_20261019`
Branch: `feature/video-commercial-framework-20261019`
Status: IMPLEMENTED + TESTED IN ISOLATED BRANCH; NOT MERGED/DEPLOYED.

## Implementation

This increment connects the existing Adaptive Commercial Intelligence v1 work directly to the existing EmpireOS **Ops Control** cycle. No additional scheduler, agent, task queue, CRM writer or daemon.

New:
- `empire_os/commercial_adaptive_ops_bridge.py`
  - Pure read-only bridge to the existing Sales Director, Conversation OS, offer-book and Revenue Distribution owner modules
  - Original-source SHA256 change receipts for ten allowlisted sources, not message authenticity proof
  - Consume pre-existing Conversation OS aggregate control report (avoid duplicate observer execution)
  - Reuse prior Sales Director and commercial control records already stored by Ops Control
  - Distinguish meaningful evidence change, original source-only change and no change
  - Privacy-safe summary and change-only event, never private prospect details or actual outbound permissions
  - Fail-closed, no exception values/PII in Founder-visible output
- `scripts/run_ops_control_cycle.py` (existing ONLY)
  - Pass previous `ops_control/latest.json` decision records to the pure bridge
  - Include `adaptive_sales_review`, `adaptive_commercial_review` and `adaptive_commercial_summary` in the **existing** Ops Control latest snapshot
  - Add `health_domains.adaptive_commercial_intelligence`
  - Append **change-only** privacy-safe records to `runtime/ops_control/adaptive_commercial_transitions.jsonl` after the existing latest snapshot write
- `scripts/review_sales_director_original_proof_20261020.py` and `scripts/review_commercial_adaptive_intelligence_20261020.py`
  - Expose reuse points so the Ops cycle does not need a duplicate source loader or a second Conversation OS observer
- `tests/test_commercial_adaptive_ops_bridge.py`
  - Synthetic end-to-end initial, repeat, source-only delta, invalid original proof, transient unavailability, private fields and existing-owner wiring

Existing systemd service: `empire-ops-control.service`. It runs `scripts/run_ops_control_cycle.py`, already has its own cadence and writes only beneath `/srv/empire_os/runtime`. This worktree **does not** add systemd units, enable timers, restart services or modify live deployment.

## Behaviour

### First completed review

Ops Control stores the current two privacy-safe checkpoints and emits `COMMERCIAL_EVIDENCE_STATE_CHANGED` once. Separate source files are read; none is modified.

### Identical evidence next cycle

Existing commercial gate memory is retrieved from prior Ops snapshot, the new `UNCHANGED_COMMERCIAL_HOLD` transition is calculated and repeated owner attention is suppressed. No new commercial change-history event is appended.

### Original source bytes change with no verified outcome change

The ten allowlisted owner snapshots produce different SHA256 receipts (content change detection only). The Sales Director adapts to `OWNER_SOURCE_CHANGED_NO_PROOF_UPGRADE` and the commercial dependency graph stays on hold. The system can emit a quiet `ORIGINAL_SOURCE_RECEIPT_CHANGED_ONLY` change-history event. **No reply authenticity, buyer proof or outbound authority is inferred from a digest change.**

### Meaningful verified source-level evidence changes

Source-validated counters, readiness blockers or gate status change. The graph records material status delta, newly blocked/cleared gates, persistent holds and recurrences, and outputs owner review suggestions. No jobs are dispatched.

### Missing source, schema drift or suspect previous memory

Bridge returns `ADAPTIVE_COMMERCIAL_EVIDENCE_UNAVAILABLE` with **zero action authority** and no private exception details. It can carry forward previous checkpoint values **only as historical replay inputs**; the current summary clearly says unavailable. The Ops cycle can continue.

## Hard boundaries and honesty

- No per-thread authenticated reply proof has been established by this integration.
- Existing Sales Director and Buyer Development own buyer contact, original thread authentication, suppression, capacity, payment terms, onboarding and outreach.
- Existing Revenue OS learning owns original post-decision financial outcome proof; **no synthetic revenue learning**.
- Research counts of historical targets/threads and unverified buyer-capacity records never become pipeline or settlement counts.
- No auto-send, no spend, no CRM writes, no database migrations, no permission/owner changes, no model training.
- No user identifier, email, company, thread ID or message body is emitted in the adaptive event record.
- Byte change is not instant: it is observed when the **pre-existing Ops Control cycle next runs**, not by a new file-watching daemon.
- The Ops snapshot is persistent on disk and has its own existing access controls; deployment owner must verify row/tenant isolation and retention.

## Release/review requirements

1. Ops Control owner reviews new imports, runtime read budget and change-only event retention.
2. Existing Sales Director, Conversation OS and commercial data producers review their source contracts.
3. Dry-run the pure bridge again on a current source sample and run all commercial, Ops, Conversation OS, founder API and Revenue OS tests.
4. Check Git conflict and revision drift before merging the isolated branch; do **not** overwrite the live canonical tree.
5. Only after an explicit merge/deploy approval, the next normal Ops Control cycle will start retaining the new fields. No independent job should be enabled.

## How to verify in isolated worktree

```bash
cd /home/ubuntu/empire_worktrees/video_commercial_framework_20261019
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
    tests/test_commercial_adaptive_ops_bridge.py \
    tests/test_commercial_adaptive_intelligence_cli.py \
    tests/test_commercial_adaptive_intelligence_control.py \
    tests/test_ops_control_runtime_doctor.py \
    tests/test_ops_control_health_summary.py \
    tests/test_founder_ops_api.py
```

The bridge itself can be manually invoked with `observe_ops_adaptive_commercial(root=..., previous_ops_snapshot=..., conversation_proof=..., now=...)` without disk writes. **Do not directly run the full production Ops Control CLI for a read-only test**: the existing core CLI normally persists Ops Control and incident snapshots, and may execute other permitted repairs in guarded mode.

### Next commercial build milestones

Real original per-case provider receipt and tenant authority proof; buyer capacity/contract proof; event-time lineage rather than re-written output timestamps; source SLAs; safe archival and retention of previous decision snapshots; and metrics of actual qualified buyer-to-order progress from verifiable real payment and fulfilment evidence.
