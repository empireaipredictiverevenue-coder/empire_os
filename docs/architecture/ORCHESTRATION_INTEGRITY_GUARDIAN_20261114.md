# Orchestration Integrity Guardian — Architecture Contract

Date: 14 November 2026
Status: CODE IMPLEMENTED, ACTIVATION PENDING CONTROLLED RELEASE
Owner: Engineering / Control Fabric assurance; escalates to ASTRA and Founder.

## Purpose and reuse
The Reliability Agent owns runtime recovery. Completion Task Monitor owns
checklist evidence. ASTRA owns goal coordination and DepartmentWorker owns
execution. Neither existing monitor independently audits ASTRA's own
organisational completeness against canonical queue records and real service
wiring. This Guardian is a new independent assurance agent, not another queue,
executor, scheduler, repair loop or source of commercial approval.

## Canonical placement and evidence
Independently observes canonical DepartmentWorkQueue, ASTRA dispatch and
evaluation snapshots, and the actual systemd department cycle. Publishes one
atomic read-only report to runtime/orchestration_integrity/latest.json.
Its reports must remain critical when ASTRA reports a successful cycle
without delivery proof.

## Verification conditions
- An item with implementation_performed=false is stage-complete only, not a
  delivered customer outcome. Parent objectives require independently
  verified live evidence under the existing completion reconciler.
- Every unresolved job has one accountable owner and root cause.
- Missing/stale executive evidence rejects a positive assurance claim.
- The live known-bad 57 ExecStartPost hooks and 42 drop-in files are
  NON-GROWTH ceilings, not approval. Further growth rejects release.
- The 57-hook serial chain remains an outstanding structural failure.
- Process-exit success does not establish business success.

## Execution, ownership and failure policy
Deterministic, local, no model, spend or third-party provider required. Fail
closed on unavailable queue, service configuration or executive evidence.
No restart, outbound, financial authority, database writes, task closure,
service modification, deployment or approval changes. CLI --check-release
returns a nonzero exit for a regression violation.

Integrate inside the EXISTING long-running Reliability Agent cycle,
independent of ASTRA, rather than adding a 58th post-hook or new timer.
Continuous activation requires the pre-existing release process and real
post-activation runtime verification. Source edit alone does not prove activation.

## Tests and rollback
Focused tests in tests/test_orchestration_integrity_guardian.py cover false
success, root-cause ownership, service-growth rejection, missing evidence and
no queue mutation. Roll back the limited Reliability Agent call and Guardian
files; do not rewrite canonical work history.
