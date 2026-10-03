# Empire Digital Avatar — Clone Fleet Dispatch Delta V1

Date: 2026-10-02
Status: PLANNING / OBSERVE-ONLY
Change class: Architecture delta

## Purpose

Compose Clone Fleet routing, identity/consent validation and concurrency policy
into one deterministic workforce-dispatch recommendation.

Dispatch V1 answers: "which authorised clone is ready for this meeting slot?"
It does not create a meeting bot, persist a reservation, send an invite or join.
## Flow

```text
TRUSTED TENANT MEMBERSHIP
  -> MEETING NEED / CAPABILITIES
  -> DETERMINISTIC FLEET ROUTER
  -> UNIQUE OR EXPLICITLY PREFERRED CLONE
  -> OWNER IDENTITY + CONSENT VALIDATION
  -> OBSERVE-ONLY FLEET RUNTIME BINDING
  -> MEETING RESERVATION CANDIDATE
  -> CONCURRENCY / CAPACITY POLICY
  -> DISPATCH-READY RECOMMENDATION
  -> [future human/provider activation gate]
```

Existing routing, fleet runtime and concurrency modules remain canonical owners.
Dispatch is composition, not a second implementation.
## Inputs

Required:
- trusted TenantMembership with operate permission;
- AvatarFleetMeetingNeed;
- requested timezone-aware meeting start/end;
- fleet bindings;
- DigitalAvatarIdentity records keyed by avatar_id;
- existing reservations;
- verified FleetConcurrencyPolicy.

No raw voice/face media is required.
No provider URL/token/API key is accepted by this layer.
## Decision contract

A dispatch is ready only when all are true:
- routing selected exactly one clone;
- selected binding is tenant-owned and active;
- matching DigitalAvatarIdentity exists;
- avatar_id, owner name and owner-consent evidence all match binding;
- requested SHADOW/COPILOT mode remains within V1 ceiling;
- no canonical meeting-ID conflict;
- selected clone is not overlapping another meeting;
- tenant concurrency capacity is available.

Any failure returns blockers and zero execution authority.
## Authority

Dispatch V1:
- recommendation_only=true;
- reservation_persisted=false;
- provider_call_performed=false;
- calendar_invite_sent=false;
- meeting_join_performed=false;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- execution_authority=none.

It cannot promote meeting mode or commercial authority.
## Failure behavior

Routing ambiguity -> human_selection_required.
Missing selected identity -> selected_avatar_identity_unavailable.
Identity/consent mismatch -> selected_avatar_identity_invalid.
Concurrency blockers are preserved exactly from canonical planner.
Invalid tenant/membership/policy input fails closed.

Cross-tenant identities or bindings cannot be selected or surfaced.
No persistence, no SQLite fallback and no Migration 018 change.
## Verification

Required:
- unique eligible clone + valid identity + free slot => dispatch_ready;
- ambiguous routing stops before identity/concurrency work;
- missing identity blocks;
- owner/consent mismatch blocks;
- same-avatar overlap blocks;
- tenant capacity exhaustion blocks;
- preferred eligible clone flows through;
- zero external side effects/authority;
- Fleet and adjacent Avatar regressions remain green.

## Architecture reconciliation — 2026-10-02

A separate `digital_avatar_fleet_assignment` composition owner now exists and
is canonical for capability + availability selection.

Dispatch is therefore narrowed to:
1. validate the dispatch request;
2. identify capability-eligible tenant-local candidates using the canonical
   router only to determine which identities need validation;
3. materialize zero-authority AvatarFleetRuntimeBinding objects through
   `prepare_avatar_fleet_runtime`;
4. delegate final capable+available selection to
   `assign_avatar_for_meeting`;
5. adapt the assignment result into a dispatch recommendation.

Dispatch must not independently implement concurrency thresholds, availability
selection or human-selection logic.

This improves the earlier V1 flow: when multiple clones are capability-eligible,
availability may narrow them to one. Human selection remains required only when
multiple capable **and available** clones remain.

Missing/invalid identity is represented as candidate identity blocking and the
Assignment planner sees no runtime for that candidate. Dispatch still performs
no reservation persistence, provider call, calendar invite, join or speech.
