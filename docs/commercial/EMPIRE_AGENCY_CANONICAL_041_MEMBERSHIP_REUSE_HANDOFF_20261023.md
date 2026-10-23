# EmpireOS Agency — Canonical 041 Membership Reader and PostgreSQL Revocation Rehearsal

23 October 2026 | Isolated feature branch | No production DB access

## What was implemented

The existing EmpireDbCrmMembershipReader is the canonical bounded reader of migration 041's public.empire_crm_read_member(text,uuid) function. It requires the dedicated empire_crm_membership_login database identity, a read-only transaction, an exact user/tenant and active membership.

The new agency_canonical_membership.py is a minimal adapter around that exact existing reader. It accepts an approved canonical tenant UUID and permits only active owner/admin membership. CRM bearer tokens or their signing keys are never accepted as authority for agency WordPress/MCP access. No second CRM, user table, database role, API or production connection was created.

Membership is necessary but insufficient. The signed agency-specific grant, separately authorised WordPress site grant, connector registry and approved credential reference remain mandatory before real customer access.

## Actual PostgreSQL evidence

Runner: scripts/agency_mcp_live_wp_e2e/run_canonical_041_revocation.sh

The test initialised an isolated, user-owned PostgreSQL 18 cluster in a temporary directory with UTF-8 encoding, a private Unix socket and TCP disabled. It applied the unmodified canonical migration 041 in database crm_membership_fixture, granting the temporary dedicated reader only EXECUTE on the bounded membership function.

The reader could resolve one synthetic active owner through the real function. A separate temporary fixture owner then disabled the membership, changed its role to operator, set expiry in the past, and reactivated it. The new agency adapter and the preflight's per-operation revocation check observed the changes. An expired/revoked member could not access the connector. The dedicated membership reader was forbidden to SELECT the underlying membership table (SQLSTATE 42501). Synthetic site-grant and connector-registry checks continued to be independent requirements.

14 checks passed. Immutable evidence: docs/commercial/EMPIRE_AGENCY_CANONICAL_041_POSTGRES_REVOCATION_FIXTURE_20261023.json. Its SHA256 manifest pins the source and original migration. It explicitly records live_empiredb_queried=false, live_user_revoked=false and production_changes=false. All temporary database files and sockets were torn down.

## Boundaries and next actual owner handoff

This is a real PostgreSQL execution of the canonical SQL membership rules, but it is NOT a query or revocation against the live EmpireDB tenant table. Previous separate tests proved actual WordPress/MariaDB MCP authenticated reads and synthetic per-tool MCP revocation. No single combined live EmpireDB/WordPress/MCP production transaction has been claimed or deployed.

Still required: canonical owner approval for a dedicated agency membership-read service, verified site ownership and connector grants, approved agency signing issuer and key rotation, durable replay prevention, managed per-site secrets, and a trusted Python-to-Node per-call authority integration. The protected empire_crm_membership_login role is owned by the canonical CRM security owner: these experiments do not authorise credential sharing, permission widening or a new production database account.

No real customers, WordPress public bookings, CRM writes, emails, payouts, production systemd changes, or financial actions were involved. The premium React/Three.js/Tailwind storefront and existing WordPress booking/MCP plugins remain unchanged.

The next integrated test should use an authorised test tenant and owner-approved read-only authority without modifying a real customer's membership. For revocation transitions, use the isolated replica unless specific production test-tenant approval is recorded.
