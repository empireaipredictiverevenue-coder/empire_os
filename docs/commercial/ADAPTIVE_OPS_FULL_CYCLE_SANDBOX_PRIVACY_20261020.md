# Empire AI — Adaptive Ops Integration: Full-Cycle Sandbox and Privacy Hardening

**Date:** 20 October 2026
**Branch:** `feature/commercial-adaptive-ops-integration-20261020`
**Worktree:** `/home/ubuntu/empire_worktrees/commercial_adaptive_ops_integration_20261020`
**Deployment:** NOT LIVE / NOT MERGED.

## Added in this increment

- `tests/test_commercial_full_ops_cycle_sandbox.py` — imports and executes the **real existing** `scripts/run_ops_control_cycle.py.main()` with all `/srv/empire_os` file references redirected to a disposable synthetic test root. Unrelated systemd, healer, mail relay and service probes are stubbed. The commercial original-owner snapshot readers, adaptive decision engine, disk Ops snapshot writer and crash-safe JSONL journal are **real**.
- `empire_os/commercial_adaptive_checkpoint_guard.py` — strict prior-checkpoint type, schema, evidence signature, owner source, causal-gate and authority validator. On temporary source failures it preserves **only the necessary privacy-safe prior decision fields**; unexpected top-level, nested personal, unknown source or forged commercial-authority fields are discarded. It never copies raw snapshot objects into a Founder-visible fallback.
- `tests/test_commercial_adaptive_checkpoint_guard.py` — synthetic tests for valid resume, nested PII injection even with recomputed checksum, invalid owner source keys, forged send/payment authority and source immutability.
- `empire_os/commercial_adaptive_ops_bridge.py` — replaces unsafe blind copying of previous packet on source failure with validated minimal memory.
- `tests/test_commercial_adaptive_ops_bridge.py` — updated recovery test to verify schema-minimised memory and resumed unchanged prior decision.

## Actual original Ops cycle sandbox checks

1. **Initial real main() cycle**: persisted Ops snapshot contains new Sales Director and cross-team commercial decision memory and existing Founder Ops health domain; exactly one commercial event was appended.
2. **Identical second real main() cycle**: prior decision is loaded from the persisted snapshot; no duplicate commercial event; no new owner attention.
3. **Source bytes changed without reply proof**: a source-only change event is stored once, and never presented as a verified reply, qualified buyer or executable campaign.
4. **Simulated interruption after journal append but before snapshot replacement**: retry deduplicates the event by stable event ID and successfully materializes the snapshot without creating a second event.
5. **Original owner source temporarily missing**: current summary becomes unavailable, execution remains held; only validated minimal replay memory is retained and can resume on recovery.
6. **Tampered previous checkpoint containing private contact/company fields**: the new current Ops snapshot does not propagate those fields even while original source reading fails.

These tests run only in a disposable synthetic environment. The real production `empire-ops-control.timer` was **not** restarted, the canonical `/srv/empire_os` working tree was **not** changed, and no live mail/account/provider calls or authorized spending were performed.

## Pre-deployment requirements

- The live canonical checkout currently has extensive unrelated uncommitted changes from other agents. It is not safe to force merge/rebase or overwrite owner files.
- The integration candidate is based on the live committed baseline recorded in the preceding handoff. Rerun conflict and current-HEAD checks before release.
- Existing Ops Control owner must approve the integration, runtime budgets, owner/tenant visibility, and change-journal retention policy.
- Use an approved release coordinator to reconcile the dirty live tree and deploy on the normal existing Ops cycle. Do **not** install a second timer.
- Post-release validation should check `/v1/founder-ops/status` and the original `runtime/ops_control/latest.json` for the new passive fields without assuming authenticated buyer activity.
- Real customer communication, paid media, buyer qualification and economic learning remain separately governed by their existing owners.

**Revenue/ROI claim:** This increment is reliability and decision-quality infrastructure, not evidence of accepted orders or realized margin.
