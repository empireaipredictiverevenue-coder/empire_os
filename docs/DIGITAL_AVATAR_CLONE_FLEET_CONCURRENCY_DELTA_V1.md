# Empire Digital Avatar — Clone Fleet Concurrency Delta V1

Date: 2026-10-02
Status: PLANNING / OBSERVE-ONLY
Change class: Architecture delta

## Purpose

Allow multiple authorised clones to be planned for simultaneous B2B meetings
without double-booking one avatar, colliding canonical meeting IDs, or inventing
tenant capacity.

This slice is a deterministic planner only. It does not schedule provider jobs,
join meetings, start Output Media or speak.
## Canonical placement

Owner: Clone Fleet control plane.
Inputs:
- validated tenant-scoped AvatarFleetRuntimeBinding;
- requested meeting reservation;
- existing reservation set;
- explicit verified concurrency policy supplied by caller.

Outputs:
- allowed/blocked reservation decision;
- blockers and observed overlap counts;
- zero execution authority.

Existing Recall session/activation modules remain the execution owner after a
future approved reservation is promoted. This planner does not duplicate them.
## Reservation identity

A reservation is identified by:
- tenant_id;
- avatar_id;
- canonical meeting_id;
- timezone-aware starts_at / ends_at;
- planned meeting mode.

Rules:
- end must be strictly after start;
- one avatar may have at most one overlapping meeting;
- canonical meeting_id must be globally unique across active reservations;
- cross-tenant reservations do not consume another tenant's concurrency quota;
- a disabled/unbound avatar cannot be planned;
- direct provider URLs/tokens are not stored in this policy object.
## Capacity policy

Capacity is explicit evidence-backed input, never inferred from legacy pricing
tiers or hard-coded plan names.

FleetConcurrencyPolicy contains:
- max_concurrent_meetings for one tenant;
- max_concurrent_meetings_per_avatar (V1 must equal 1);
- capacity_evidence_ref.

Missing/invalid capacity evidence fails closed.

Future product billing may map verified subscription terms into this policy, but
that mapping is outside V1.
## Authority and failure behavior

Authority: OBSERVE / recommendation only.

Planner cannot:
- persist a booking;
- call Recall/Zoom/Teams/Meet;
- create a bot;
- start Presence;
- render/speak audio;
- modify commercial terms;
- send calendar invites;
- mutate tenant state.

Conflicting meeting_id, same-avatar overlap or capacity exhaustion returns a
blocked decision. Unknown/invalid time or policy raises validation failure.

No SQLite fallback. No Migration 018 change.
## Verification

Required:
- non-overlapping meetings for same avatar allowed;
- overlapping same-avatar meetings denied;
- different avatars may overlap inside tenant until tenant capacity reached;
- cross-tenant reservations do not consume quota;
- duplicate meeting ID denied even across tenants;
- max tenant concurrency enforced at interval boundaries;
- adjacent intervals where one ends exactly as another starts do not overlap;
- missing capacity evidence fails closed;
- output has zero execution authority;
- Clone Fleet + Digital Avatar regressions remain green.

## V1 mode ceiling

Concurrency V1 accepts only SHADOW and COPILOT reservation modes.
REPRESENT, NEGOTIATE and CLOSE reservations fail closed at validation even when
their requested time/capacity would otherwise fit. This planner cannot be used
as an indirect authority-promotion mechanism.
