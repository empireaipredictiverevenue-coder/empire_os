# EmpireOS — Authenticated Agent Kanban through the existing CRM

## Goal and boundaries

Continue the original EmpireOS Agent OS integration. **No new company,
agent runtime, scheduler, queue, database, public web endpoint, or automatic
credentials.** The first Kanban reader is integrated into the existing
opt-in first-party CRM tenant read router rather than the general Founder
Console API, which is loopback-only but **not sufficient proof of founder
login or tenant scope**.

## Implementation

The existing `create_revenue_crm_router()` provides
`GET /v1/revenue-crm/department-kanban` with bounded
`max_cards_per_lane=1..50` (default 20):

- If the opt-in server-authenticated CRM tenant reader is not configured,
  returns 503; the legacy/open Hub router cannot expose work cards.
- If the signed first-party tenant session is missing or invalid, returns 401.
  Untrusted headers, cookies, query tenant IDs or claimed roles never supply
  tenant scope.
- Existing `require_repository()` verifies the authenticated tenant and the
  dedicated `PostgresRevenueCrmRepository` matches the same tenant.
- Before listing local task metadata, a bounded 1-row CRM reader call
  verifies the *actual database session* and dedicated role/tenant binding.
  Transport errors are sanitised to 503 and no private login/DSN leaks.
- Calls the **existing** `build_kanban_board()`, always passing the tenant ID
  supplied by the verified server principal, not any client-supplied value.
- Returns only compact queue cards for **exactly that tenant ID**. All
  tenant-unbound executive/internal work, other tenants, raw task instructions,
  source notes, A2A messages, buyer details and secrets are excluded.
- No DB modification, no independent task-state writes, no acceptance of
  agent messages as authoritative status transitions, no auto-approval.

This adds an authenticated backend reader, **not** a new browser page or
founder-global board. The wider unbound internal queue requires an
independently proven founder-owner login/privilege check.

## Agent runtime readiness

`empire_os/agent_collaboration_readiness.py` now inventories declared
department roles and existing execution-plane worker definitions without
claiming those definitions are live authenticated agent instances. Its
operator-level aggregate explicitly reports current message/credential
activation as held and has no model/network/DB calls.

The first signed agent task protocol was already delivered in
`empire_os/department_collaboration.py` and the existing canonical queue.
**Credential provisioning, process identity attestation, JEV/OpenManus/
Hermes runtime adapter wiring, reviewed SkillForge activation and peer wake
notifications still require separate execution/identity proof.** None is
auto-activated by a read-only CRM endpoint.

## Tests and activation

`tests/test_agent_kanban_authenticated_crm.py` covers:
legacy router denial; spoofed login/tenant claims; true server-side scope;
SQL role/session binding; tenant A/B/unbound isolation; mismatched CRM
principal/reader; mismatched DB session; response limits and no task bodies.

`tests/test_agent_collaboration_readiness.py` checks no invented agent
sessions or leaked task content and a read-only synthetic queue.

**Do not restart a live CRM service or publish a Founder web page solely
because tests pass.** First reconcile concurrent changes, confirm the exact
auth routing, validate independently with the owner login, then deploy the
read-only change with rollback and 401/503/200 proofs. No financial or
outbound activation is in this change.
