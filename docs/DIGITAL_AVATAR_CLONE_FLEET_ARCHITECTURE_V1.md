# Empire Digital Avatar — Clone Fleet Architecture V1

Date: 2026-10-02
Status: ARCHITECTURE FOUNDATION / NO PRODUCTION TENANT CUTOVER
Change class: Architecture change

## Purpose

Turn the single authorised Digital Avatar runtime into a safe multi-avatar
workforce capability for Empire AI and future B2B tenants.

A clone is an authorised AI representative of one real human or approved
business persona. Clone Fleet coordinates many such avatars without allowing
identity sharing, tenant bleed, authority inheritance or hidden impersonation.

V1 defines the control contract only. It introduces no EmpireDB migration,
does not activate tenant RLS, and does not make legacy SQLite SaaS state
canonical.
## Diagram

```text
AUTHENTICATED TENANT MEMBERSHIP
  -> TENANT RESOURCE ACCESS DECISION
  -> TENANT-SCOPED AVATAR BINDING
  -> OWNER CONSENT / VOICE / VISUAL EVIDENCE
  -> AVATAR ROLE + CAPABILITY PROFILE
  -> MEETING SESSION BINDING
  -> EXISTING DIGITAL AVATAR AUTHORITY ENGINE
  -> SHADOW / COPILOT / FUTURE REPRESENT
  -> TENANT-SCOPED READ STATE / AUDIT
```

The existing single-avatar runtime remains the execution engine. Clone Fleet is
a control-plane layer above it, not a second meeting/speech implementation.
## Canonical placement and truth

Domain owner: Conversation OS / Revenue OS.
Isolation primitive: `tenant_isolation.authorize_tenant_resource`.
Membership primitive: `saas_scale.TenantMembership`.
Avatar runtime owner: existing `digital_avatar*` modules.

EmpireDB remains canonical business truth. Migration 018 remains HELD and is
not modified or applied by Clone Fleet V1. Required protected SHA256:

`e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21`

`tenants.py` SQLite records are legacy SaaS compatibility state only and must
not authorize clone ownership, commercial evidence, meeting authority or
cross-tenant access.
## Tenant and identity contract

Every fleet resource carries a non-empty `tenant_id`.
Every avatar binding carries:
- tenant_id;
- avatar_id;
- owner user/person reference;
- owner-consent evidence ref;
- permitted role/capability labels;
- active/disabled state.

The bound DigitalAvatarIdentity must match avatar_id and owner consent.
Tenant membership and avatar binding are separate proofs: being a tenant member
does not imply consent to clone a person, and owner consent does not imply
cross-tenant access.

Cross-tenant access always fails closed, including read-only state.
## Authority contract

Clone Fleet V1 authority: OBSERVE / internal decision only.

Fleet permissions:
- read fleet entry: tenant membership `read`;
- prepare/use avatar runtime: tenant membership `operate`;
- manage clone bindings: tenant membership `admin`.

Fleet V1 cannot:
- create or infer owner consent;
- clone a voice or visual identity without explicit evidence refs;
- expand Digital Avatar meeting/commercial authority;
- speak, join meetings, send outbound or accept terms by itself;
- move funds or recognize revenue;
- change tenant DB bindings/RLS;
- use caller-supplied tenant IDs to bypass authenticated membership.
## Execution model

V1 is synchronous deterministic policy evaluation only.

No persistence is introduced in this slice. Callers provide authenticated
TenantMembership plus tenant-scoped fleet binding; the policy returns an access
decision and a validated runtime binding.

Future persistence must use an approved canonical tenant context after its own
architecture/migration gate. It may not silently fall back to SQLite.

Identity key:
`(tenant_id, avatar_id)`.

A given avatar_id may not be rebound to another tenant by an in-memory merge or
lookup. Ambiguous or conflicting bindings fail closed.
## Worker assignment / ownership

Canonical owner modules for V1:
- `digital_avatar_fleet.py`: tenant/avatar binding + fleet access policy;
- `tenant_isolation.py`: generic tenant resource authorization, reused only;
- `digital_avatar.py`: single-avatar runtime identity, not duplicated.

No migration worker is assigned. No tenant persistence worker is assigned.
Migration 018 is protected and outside this change.

Verifier lane:
- focused tenant/clone policy tests;
- cross-tenant negative tests;
- disabled-membership tests;
- consent/identity mismatch tests;
- existing Digital Avatar regression after integration.
## Failure and recovery

Missing tenant membership: deny.
Disabled membership: deny.
Cross-tenant resource: deny.
Missing consent evidence: invalid binding.
Identity owner/consent mismatch: deny runtime binding.
Duplicate same-tenant binding with identical identity: idempotent.
Conflicting duplicate: fail closed and require operator reconciliation.

Tenant DB/RLS unavailable does not trigger SQLite fallback. V1 remains local
policy only until a separately approved canonical persistence path exists.

Universal fail-safe for meeting runtime remains SHADOW.
## Observability and product fit

Future fleet events:
- avatar_binding_validated;
- avatar_access_denied;
- cross_tenant_access_denied;
- consent_mismatch;
- clone_runtime_prepared;
- clone_disabled.

No event may claim a meeting action occurred unless the existing Avatar runtime
records it.

Commercial fit:
- Empire internal executive/SDR/product specialist clones;
- tenant employee digital twins;
- white-label AI workforce;
- per-seat / per-avatar / usage pricing can be modeled later from verified
  catalog and usage evidence, never hard-coded by this policy layer.
## Promotion criteria

V1 DONE:
- architecture contract;
- deterministic fleet/tenant domain;
- focused isolation/identity tests;
- existing Avatar regression remains green;
- Migration 018 hash unchanged.

V2:
- Founder read-only fleet surface using authenticated membership.

V3+:
- canonical EmpireDB persistence only after explicit tenant-context approval;
- tenant-scoped voice/visual asset registry;
- quota/metering integration;
- controlled multi-avatar meeting scheduling.

No live tenant cutover is authorized by this document.
