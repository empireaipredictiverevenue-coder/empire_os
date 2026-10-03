# Empire Digital Avatar — Clone Fleet Assignment Delta V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Compose capability routing and concurrency planning into one deterministic
meeting-assignment decision for the Digital Avatar workforce.

This layer answers: "which authorised clone is both capable and available for
this requested SHADOW/COPILOT meeting?" It remains recommendation-only.
## Inputs

Required:
- authenticated TenantMembership;
- AvatarFleetMeetingNeed;
- validated AvatarFleetBinding set;
- validated AvatarFleetRuntimeBinding set produced by the V1 identity/consent
  boundary;
- requested timezone-aware starts_at / ends_at;
- existing AvatarMeetingReservation set;
- explicit FleetConcurrencyPolicy with capacity evidence.

No provider URL, meeting token or secret belongs in the assignment request.
## Decision pipeline

1. Normalize fleet bindings and runtime bindings.
2. Run capability routing to establish tenant-local eligible candidates.
3. Reject any candidate lacking a matching validated runtime binding.
4. For each eligible candidate, run the canonical concurrency planner using the
   same requested meeting_id/time/mode.
5. Remove candidates blocked by avatar overlap, cross-tenant avatar conflict or
   tenant concurrency exhaustion.
6. Preferred avatar:
   - must be capability-eligible;
   - must have validated runtime binding;
   - must be available;
   - otherwise fail closed with preferred_avatar_unavailable.
7. Without preferred avatar:
   - zero available -> no_available_eligible_avatar;
   - one available -> deterministic selection;
   - more than one available -> human_selection_required.
## Important separation

Capability is evaluated before availability.
Availability may narrow an eligible set but may never make an unqualified avatar
eligible.

A runtime binding proves tenant/avatar/owner-consent identity coherence but
grants only OBSERVE/zero execution authority.

The assignment result does not persist a reservation and does not call the
meeting provider. A later explicitly approved scheduler/promotion step is
required.
## Idempotency and conflict

An identical existing reservation for the selected avatar/meeting/time is an
idempotent duplicate and may be returned as assignment_ready with
duplicate=true, but no persistence/provider call occurs.

A canonical meeting_id conflict with different details blocks all candidates.

Cross-tenant resources remain invisible except for generic fail-closed conflict
semantics where global identity integrity requires it.
## Authority ceiling

Accepted modes: SHADOW and COPILOT only.

Output always:
- recommendation_only=true;
- reservation_persisted=false;
- provider_call_performed=false;
- meeting_join_performed=false;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- payment_execution_allowed=false;
- execution_authority=none.

REPRESENT/NEGOTIATE/CLOSE are rejected upstream by routing/concurrency V1.
## Verification

Required:
- unique capable+available clone selected;
- busy capable clone removed while another available clone may be selected;
- multiple capable+available clones require human selection;
- preferred busy clone fails closed rather than silently substituting;
- candidate without validated runtime binding is unavailable;
- tenant concurrency exhaustion blocks all candidates;
- canonical meeting conflict blocks assignment;
- idempotent duplicate preserved;
- cross-tenant data not surfaced in decision;
- zero execution authority;
- full fleet and Avatar regressions remain green.
