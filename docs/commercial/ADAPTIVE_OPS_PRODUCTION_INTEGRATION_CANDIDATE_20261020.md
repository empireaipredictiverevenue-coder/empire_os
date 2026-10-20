# Empire AI — Adaptive Ops Production Integration Candidate

**Date:** 20 October 2026
**Integration branch:** `feature/commercial-adaptive-ops-integration-20261020`
**Integration worktree:** `/home/ubuntu/empire_worktrees/commercial_adaptive_ops_integration_20261020`
**Based on canonical committed HEAD at integration start:** `a9f4eb96`
**Deployment state:** ISOLATED CANDIDATE. NOT LIVE / NOT MERGED.

## Why a separate candidate

The live canonical `/srv/empire_os` worktree has extensive concurrent uncommitted changes from other agent owners, including frontend, CRM and acquisition work. The existing `empire-ops-control.timer` is active. The adaptive intelligence branch was based on an older ancestor (`41e0f803`). Changing the canonical dirty worktree or restarting its service without reconciling those owners is inappropriate.

A new clean worktree was therefore created at the then-current canonical commit, and **all nine incremental commercial-intelligence commits** from `feature/video-commercial-framework-20261019` cherry-picked without conflict. Every test was rerun in the resulting integration candidate. No file in the current canonical production worktree was altered.

## Actual integration

Already integrated (in the candidate only):
- Existing `scripts/run_ops_control_cycle.py` imports and invokes `observe_ops_adaptive_commercial` on the Ops cycle.
- The same Ops snapshot holds the previous Sales Director adaptive checkpoint and commercial dependency/recurrence checkpoint.
- Existing `conversation_evidence_review` result is reused rather than re-running the owner observer.
- The existing Founder Ops API can expose `health_domains.adaptive_commercial_intelligence` and `adaptive_commercial_summary` from the Ops snapshot without a new route or dashboard service.
- The owner cycle writes a separate change-only `adaptive_commercial_transitions.jsonl` ledger. There is no new timer, agent or campaign worker.

### Crash/replay enhancement on the integration candidate

- New `empire_os/commercial_adaptive_event_journal.py` ensures a single event per stable `event_id`, with Linux file locking and an OS-private JSONL event file.
- The ID is derived from the privacy-safe commercial decision signature, allowlisted original-source hash-set digest and event kind. It **does not expose raw contacts**.
- If source facts do not change, the Ops cycle suppresses repeated events. If the original source bytes change but evidence quality does not, it writes a source-only review event and does not claim buyer/reply proof.
- Append the journal **before** atomic `latest.json` replacement. A crash between these steps can retry without duplicate commercial events.
- An incomplete final journal record from interrupted append is repaired, retaining complete earlier events.
- No journal input may authorize sending, dispatch or CRM writes. The schema is strict and allowlists existing source names and review gates.

## Tests and risks

Tests use synthetic TEST-only source files and ephemeral JSONL ledgers. They cover:
1. Initial review, next-cycle no-op, source-only change, schema failure, unavailable sources, and replay memory retention
2. Exact privacy-safe source digest changes and unchanged source hash
3. Journal duplicate retries, stable ID across observation clocks, event changes, crash-tail recovery, private-data exclusion and forged authority rejection
4. Existing Ops/Founder Console and Conversation OS compatibility
5. All commercial opportunity, buyer-capacity, catalog, Sales Director, Revenue Distribution and Revenue OS learning regressions

Important remaining checks before deployment:
- Recheck current canonical Git HEAD and conflict set **immediately before owner merge** because it changes frequently.
- Check service sandbox can write the new journal in `/srv/empire_os/runtime/ops_control`; existing service `ReadWritePaths` includes `/srv/empire_os/runtime`.
- Verify file ownership, retention, disk growth, journal privacy, existing timer cadence, and Ops Control time budget.
- Prove on a nonproduction local Ops snapshot that the new fields survive an entire existing owner cycle, not merely the pure bridge.
- Require the existing Ops Control owner to approve merging the candidate and activating via its next normal timer run.
- Do not run `scripts/run_ops_control_cycle.py` manually against `/srv/empire_os` for a dry-run; it writes Ops and incident snapshots and can use guarded healer behaviour depending on environment.

## Intended operator result

At the next normal existing Ops cycle **after an approved deployment**, EmpireOS can:
- Remember which eight commercial evidence gates are persistently blocked, resolved or recurring
- Compare source revision receipts without mistaking byte changes for replies
- Suppress repeated owner reviews until material evidence advances
- Surface one privacy-minimal readiness summary through existing Founder Ops
- Preserve buyer, suppression, contact, billing, spending, fulfilment and commercial authority held by their existing owners

It **cannot** invent buyer proof, send follow-ups, certify paid orders, recognise revenue or train predictive prices from unverified counts.

## Exact deployment boundary

**This document is a technical integration candidate, not an instruction to force a production merge.** The canonical tree has unrelated dirty work. Source owners should resolve it through their existing coordinator, review this candidate, and merge/deploy only in a controlled, conflict-free window.
