# Production Branch Convergence — Architecture Delta

Date: 2026-10-02
Status: CORRECTIVE / REQUIRED FOR WORKER ASSIGNMENT

## Purpose
Converge the active Agent & Tool Execution Plane on the current production base
branch `agent/data-cloud-wave4`. The September revenue-intelligence branch remains
an explicitly allowed legacy base where historical recovery requires it, but it
must not be selected by default for new builder, verifier or capability-probe work.

## Owner and placement
Owner: Engineering / Agent & Tool Execution Plane.
Affected components: Hermes, Pi sandbox, Empire Coder sandbox, candidate verifier,
Promptfoo candidate evaluation and builder capability probes.

## Authority impact
None. This change does not expand execution, deployment, commercial, payment or
revenue-recognition authority. It only corrects repository base-branch identity.

## Failure behavior
Unknown or non-allowlisted branches remain fail-closed. Existing legacy branch
support remains explicit and bounded.

## Verification
Focused tests cover Hermes control, Pi sandbox, Empire Coder sandbox, execution
plane dispatcher, candidate verification, Promptfoo and enterprise contact repair.
