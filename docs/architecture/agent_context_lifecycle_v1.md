# Agent Context Lifecycle v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Agent & Tool Execution Plane / Engineering

## Purpose
Guarantee that agent working context is task/job-scoped and disposable.

EmpireOS must preserve durable engineering truth while preventing completed agent
work from carrying a stale/full context window into unrelated future work.

## Canonical lifecycle

```text
ASSIGN TASK
  -> BUILD BOUNDED CONTEXT
  -> EXECUTE
  -> PERSIST RESULT / CHECKPOINT / AUDIT / TEST EVIDENCE
  -> RELEASE MUTATION LEASE
  -> RETIRE EPHEMERAL CONTEXT
  -> DESTROY SANDBOX / WORKTREE / SESSION
  -> NEXT TASK BUILDS FRESH CONTEXT FROM DURABLE STATE
```

## Durable vs ephemeral

### Durable — MUST be preserved
- task state records;
- job result records;
- execution-plane request/result/reconciliation artifacts;
- architecture contracts;
- progress checkpoints;
- audit trail;
- test/verification evidence;
- candidate/proposal metadata required for audit;
- commits / proposal branches that passed the candidate boundary;
- compact promoted knowledge explicitly accepted into canonical knowledge stores.

### Ephemeral — MUST be retired after terminal worker execution
- rolling model context snapshots;
- temporary prompt/context packs;
- transient session identifiers;
- disposable sandbox clones;
- disposable worktrees not required for a surviving proposal branch;
- transient provider/session caches owned by the task;
- model conversation state that is reconstructable from durable evidence.

## Coder rule

Empire Coder keeps rolling context in `runtime/coder/context/<task_id>.json`.
After a job reaches terminal `COMPLETED` or `FAILED`:

1. `LocalJobQueue` persists the terminal job result first.
2. Worker releases any execution lease.
3. `ContextMemory.retire(task_id, terminal_state, job_id)` removes the full rolling
   context file.
4. A small tombstone is written to `runtime/coder/context_retired/<task_id>.json`
   containing only lifecycle metadata:
   - task_id;
   - job_id;
   - terminal_state;
   - retired_at;
   - last_context_version;
   - full_context_removed=true.
5. If another stage later uses the same task, `ContextMemory.refresh()` rebuilds a
   fresh compact context from durable task state, audit events and proposal metadata.

A retry is not terminal and MUST NOT retire context before retry state is persisted.

## Pi rule

Pi already executes with:
- `--no-session`;
- `--no-context-files`;
- isolated clone cleanup in `finally`.

These invariants become regression-tested lifecycle requirements.

## Empire Coder sandbox rule

Sandbox clones are removed in `finally` after result/lease handling. This remains
mandatory and is regression-tested.

## Hermes rule

Hermes uses isolated worktree/job roots and removes job-local transient roots after
result publication. A proposal branch/result record may survive; the transient worktree
and local context must not.

## Swarm / verifier rule

Verification workers retain verification result artifacts but not model context. A
verification job may remain queued/running, but once terminal its working context is
reconstructable from the verification request + durable result.

## Context-window pressure

If a provider reports context saturation before terminal completion:
- compact current durable state;
- persist a checkpoint;
- start a fresh model invocation using compact durable context;
- do not continue an overfull session;
- do not discard unresolved blockers/evidence.

This is context rollover, not task retry, and must not violate the NO LOOPING rule.

## Sandcastle component-mining alignment

Sandcastle patterns worth evaluating:
- disposable sandbox providers;
- branch/worktree lifecycle;
- bounded `maxIterations`;
- lifecycle hooks;
- commit/result extraction before teardown;
- provider abstraction;
- parallel isolated agents.

EmpireOS remains canonical. Sandcastle is not installed by this contract.

## Authority

No authority expansion. Context cleanup cannot:
- delete canonical business data;
- delete checkpoints/results/audit evidence;
- alter production database state;
- send outbound;
- change payment/settlement/revenue authority;
- delete a proposal branch required for verification.

## Files
- `empire_os/coder/memory.py`
- `empire_os/coder/worker.py`
- `tests/test_coder_context_lifecycle.py`
- existing Pi / Empire Coder sandbox / Hermes lifecycle regressions

## Completion
The slice is complete when:
- terminal Coder jobs persist result before context retirement;
- rolling context is removed and a tiny tombstone remains;
- subsequent work on the same task rebuilds fresh context successfully;
- retries do not retire context;
- Pi remains no-session/no-context-files;
- sandbox/worktree cleanup regressions pass;
- no durable evidence is deleted.
