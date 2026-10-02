# Empire Coder PLAN Fallback Architecture Delta V1

Date: 2026-10-02
Class: bounded architecture delta
Owner: Agent & Tool Execution Plane / Empire Coder

## Problem

Complex advisory PLAN jobs are delegated to Hermes. A temporary OmniRoute
zero-cost model outage currently converts safe internal planning jobs directly
to FAILED, starving the revenue-first completion queue.

## Design

PENDING PLAN
-> complexity routing
-> Hermes delegated PLAN
-> provider/model outage?
   -> yes: restore same PLAN to PENDING with local_fallback_after_hermes=true
           -> Empire Coder local planner
   -> no: normal delegated success/failure handling

The marker prevents the delegation cycle from immediately sending the same job
back to Hermes.

## Scope and authority

Fallback is PLAN-only.
It does not apply to IMPLEMENT, VERIFY, deployment, service control, external
outbound, database mutation, payment or revenue recognition.
Local fallback remains advisory/non-actionable and production_mutation=false.

Only provider-availability failures qualify. Lease, verification, candidate
gate and substantive worker failures remain failed and require review.

## Verification

- provider outage restores delegated PLAN to PENDING;
- fallback marker persists durably;
- delegation skips marked jobs;
- non-provider Hermes failure remains FAILED;
- local Coder worker can claim the restored PLAN;
- no implementation authority changes.
