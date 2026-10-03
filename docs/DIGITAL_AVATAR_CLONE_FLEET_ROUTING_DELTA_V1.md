# Empire Digital Avatar — Clone Fleet Routing Delta V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Architecture delta

## Purpose

Select an authorised tenant-owned clone for a meeting from explicit capability
requirements without using model intuition, hidden ranking or cross-tenant data.

Routing is recommendation-only. It does not schedule, join or speak.
## Inputs and truth

Inputs:
- authenticated TenantMembership supplied by a trusted caller;
- validated AvatarFleetBinding set;
- meeting need containing tenant_id, canonical meeting_id, required capability
  labels, objective evidence ref and requested mode;
- optional founder/user-selected preferred_avatar_id.

Required capability labels must come from an evidence-backed meeting objective or
an explicitly selected workflow. The router does not infer capabilities from
free-form buyer text in V1.
## Selection rules

1. Membership tenant must equal meeting-need tenant.
2. Membership requires operate permission.
3. Fleet bindings are normalized before routing; ambiguous/cross-tenant avatar
   ownership fails closed.
4. Disabled clones are excluded.
5. A clone is eligible only when all required capability labels are present.
6. A preferred avatar is selected only if eligible.
7. Zero eligible clones -> no_eligible_avatar.
8. More than one eligible clone without a preferred avatar ->
   human_selection_required.
9. Exactly one eligible clone -> deterministic selection.
10. Cross-tenant preferred avatar is indistinguishable from missing/unavailable.
## Authority ceiling

V1 routes SHADOW and COPILOT only.
REPRESENT, NEGOTIATE and CLOSE fail validation before selection.

Routing output always has:
- recommendation_only=true;
- provider_call_performed=false;
- meeting_join_performed=false;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- execution_authority=none.

Routing cannot be used as an authority-promotion mechanism.
## Composition boundary

Routing answers "which clone has the required capability?".
Concurrency answers "is that clone/time slot available?".

Neither subsystem may silently override the other. A future assignment planner
must compose both and only emit assignment_ready when capability routing and
concurrency policy both pass.

A capability match is not proof of availability. An available avatar is not
proof of capability.
## Verification

Required:
- unique capability match selected;
- ambiguous match requires human selection;
- preferred clone must be eligible;
- disabled clone excluded;
- cross-tenant preferred clone not disclosed;
- viewer cannot route;
- tenant mismatch denied;
- capability labels normalized deterministically;
- higher-authority modes rejected;
- zero execution authority preserved;
- fleet and adjacent Avatar regressions remain green.
