# Department Hook Supervisor — Candidate Architecture Delta

Date: 14 November 2026
Owner: Engineering / EmpireOS Department Cycle, with ASTRA accountability.
Status: COMMITTED CANDIDATE ONLY; NOT CONNECTED TO LIVE SYSTEMD.

## Purpose and bounds

The existing department heartbeat has 57 ExecStartPost commands spread across
42 drop-in files. The main process completes while the post-run chain can
continue for several minutes. The existing chain includes necessary ordered
passes, consent checks, runtime promotions, and 31 optional vs 26 required
steps. These cannot be safely deleted, parallelised, or silently reordered.

The proposed Department Hook Supervisor is a narrow component beneath the
existing department-cycle owner, not a second service or operating system.
Its input is an audited, immutable snapshot of the actual systemd command
list; it does not synthesize tasks from agent plans or discover new authority.

## Truth and execution contract

Inputs: live service hook inventory at
runtime/orchestration_integrity/service_hook_inventory_20261114.json.
Before any activation, verify every command still matches systemd ordering.
Output: durable cycle checkpoint with command digest, position, stage,
timestamps, exit code, failure class, and progress. No production service
is changed by installing or shadow-running the candidate.

A shadow invocation must execute no commands and create no checkpoint.
Any executable path other than pre-existing Python or original permitted Bash
command is rejected. In executable mode the worker requires an explicit
governance callback; live production activation has NOT been wired.
The default migration is strictly sequential. Optional failures are recorded
but may permit the next step. Required failures halt the chain. Interrupted
RUNNING jobs require independent review and are never blindly replayed.
A single filesystem lease rejects competing runner processes. Each job uses
a bounded timeout, and batches contain no more than 12 steps.

## Dependencies and prohibited actions

This version records one predecessor dependency per job; it does NOT yet
prove safe parallelism or convert 57 tasks into a live worker scheduler.
Pre-existing scripts have their existing authorities and some consume
consent-sensitive data, so actual production migration needs founder-approved
service cutover, task-by-task dependency validation and exact rollback.

No external sends, payments, migrations, deployments, restarts or new
authority are granted by the supervisor. It must not override Control Fabric,
the outbound governor, suppression rules, identity or tenant boundaries.

## Tests, verification and rollout gates

Tests: tests/test_department_hook_supervisor.py. Verify inventory integrity,
complete live command match, dry-run isolation, optional/required semantics,
bounded batches, recovery without blind replay, timeout, concurrency lease and
fail-closed drift. Review all input/output dependencies, then run an isolated
integration test using safe fixtures; prepare a reversible unit change.
Only after authorisation, activate under the existing department-cycle owner
and verify actual live status and end-to-end departmental outcome evidence.

Rollback: revert the narrow supervisor integration and restore the backed-up
original systemd unit and drop-in wiring; never delete task history.
