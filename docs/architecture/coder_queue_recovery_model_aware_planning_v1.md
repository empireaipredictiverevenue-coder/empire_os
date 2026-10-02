# Empire Coder Queue Recovery / Model-Aware Planning v1

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Engineering / Agent & Tool Execution Plane

## Purpose
Recover the durable Empire Coder backlog without sending complex PLAN jobs to an
undersized local model, widening the Coder service network sandbox, or creating a
second orchestration system.

Observed production state: Coder timer disabled, 293 pending jobs, healthy local
llama.cpp `qwen2.5-coder:1.5b`, healthy governed Hermes resident timer, and a
priority-100 complex PLAN timing out on the local model.

## Canonical placement
`empire_os/coder/` owns local task/job lifecycle. The existing Agent & Tool
Execution Plane owns worker routing. The existing Hermes control plane owns
networked governed model execution.

## Execution contract

```text
PENDING PLAN
  -> exact complexity classification
  -> local capability sufficient -> Empire Coder localhost worker
  -> local capability insufficient -> atomically DELEGATED
       -> OBSERVE backend_code request -> Hermes control branch
       -> Hermes result -> reconcile into Coder proposal/result
       -> COMPLETED/FAILED -> retire full task context
```

Planner capability must match objective complexity. Capability-1 is no longer a
universal PLAN override. An undersized route fails closed as `unconfigured`.

## Authority
Delegated PLAN work is OBSERVE only. It has no allowed paths, mutation lease,
outbound/commercial authority, payment authority, revenue-recognition authority,
deploy authority or authority-expansion capability.

The Coder service remains localhost-only. Hermes publication/reconciliation runs
inside the already-governed Hermes resident service.

## Queue/data contract
Add `DELEGATED` as a durable non-hot Coder job state and `jobs/delegated/` as its
store. Reservation is atomic under the existing queue lock. Delegation metadata
is persisted in `job.result` before publication. Failed publication restores the
job to PENDING without losing attempts/history.

A reconciled Hermes OBSERVE result is persisted as a non-actionable Coder
proposal and the Coder job becomes terminal. Full rolling task context is then
retired only after terminal state is durable.

## Failure behavior
- local model below required capability: never selected;
- Hermes publication failure: restore PENDING, fail closed;
- Hermes result absent: remain DELEGATED, no retry storm;
- Hermes failed result: mark Coder job FAILED and retire context;
- Hermes completed-no-changes result: persist advisory text, mark COMPLETED;
- no job deletion and no fabricated completion.

## Verification
Focused router, queue, delegation, worker, execution-plane and context-retirement
tests; Python compile; diff check; bounded live delegation/reconciliation smoke;
then timer activation only if the live queue remains safe.
