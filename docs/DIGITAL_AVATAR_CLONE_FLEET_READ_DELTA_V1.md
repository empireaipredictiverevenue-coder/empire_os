# Empire Digital Avatar — Clone Fleet Read Delta V1

Date: 2026-10-02
Status: INTERNAL READ-MODEL FOUNDATION
Change class: Architecture delta

## Purpose

Provide a tenant-scoped, redacted Clone Fleet read model without creating a
public/self-service HTTP surface before trusted tenant authentication exists.

The current SaaS preview routes can construct TenantMembership from request
fields. That is suitable for readiness simulation, not identity authentication.
Clone Fleet must not trust those caller-supplied role/tenant fields.
## Placement

Owner: Clone Fleet control plane.
Input:
- trusted `TenantMembership` supplied by a future authenticated caller;
- validated `AvatarFleetBinding` values.

Output:
- tenant-only fleet snapshot;
- redacted avatar entries;
- no mutation or execution authority.

No DB access, no persistence, no new service and no public route are introduced
by this delta.
## Redaction contract

A fleet read item may expose:
- avatar_id;
- owner display name;
- capability labels;
- active/disabled status;
- consent_verified boolean;
- OBSERVE runtime state.

It must not expose:
- consent evidence references;
- raw voice/face media refs;
- signing secrets;
- meeting tokens;
- commercial internal economics;
- data belonging to another tenant.

Cross-tenant resources do not contribute to counts, metadata or errors visible
in the returned snapshot.
## Authority

Required permission: tenant membership `read`.
Disabled membership fails closed.

Read-model authority:
- execution_authority=none;
- speech_execution_allowed=false;
- commercial_execution_allowed=false;
- payment_execution_allowed=false;
- revenue_recognition_allowed=false.

No operation in this delta may prepare, join or speak in a meeting.
## Execution / failure model

Synchronous deterministic projection.

Before projection, fleet bindings are normalized with the V1 ambiguity rules.
Conflicting global avatar ownership fails closed before any snapshot is emitted.

For a valid set, only bindings whose tenant_id exactly matches authenticated
membership.tenant_id are projected. The result contains no count or reference
for other tenants.

No fallback to `tenants.py` SQLite state is allowed.
Migration 018 remains unchanged and held.
## Verification

Required:
- own-tenant list projection;
- cross-tenant entries invisible;
- disabled membership denied;
- consent reference redacted;
- active and disabled clone status visible inside own tenant;
- deterministic ordering;
- zero execution authority fields;
- existing Clone Fleet and Avatar regressions remain green.

Promotion to HTTP requires a separate trusted-authentication architecture delta.
