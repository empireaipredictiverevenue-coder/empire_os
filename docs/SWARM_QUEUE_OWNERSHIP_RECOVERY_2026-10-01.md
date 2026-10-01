# Swarm / Empire Coder Queue Ownership Recovery

Date: 2026-10-01
Status: bounded runtime recovery

## Observation

Swarm V6 verification failed before processing because a small set of pending
Empire Coder PLAN jobs were unreadable by the canonical worker account.

## Diagnosis

The queue directories are private and owned by ubuntu:ubuntu (0700), and the
canonical Empire Coder worker runs as ubuntu:ubuntu.

Ten historical pending PLAN JSON files created on 2026-09-28 were instead
root:root mode 0600. Swarm's queue scan therefore raised PermissionError while
quarantining/examining pending jobs.

The affected jobs are internal PLAN jobs with execution_authority=none and no
execution-plane request id.

## Classification

Runtime ownership drift. Not a business-logic failure and not authority
expansion.

## Plan

- Change ownership only on root-owned JSON files under
  runtime/coder/jobs/pending to ubuntu:ubuntu.
- Preserve file mode and content.
- Do not execute the old backlog as part of the repair.
- Verify every pending job is readable by ubuntu.
- Re-run targeted verification only.

## Positive example

A root-owned 0600 pending PLAN file becomes ubuntu:ubuntu 0600 and is readable
by the governed coder/verifier.

## Negative example

Do not chmod the private queue world-readable and do not recursively chown
unrelated runtime/secrets or repository files.

## Authority

No outbound, payment, settlement, canonical-data mutation, production deploy,
or revenue-recognition authority.
