# EmpireOS Agency — Combined Canonical PostgreSQL ↔ Guarded MCP ↔ WordPress/MariaDB

23 October 2026 | One disposable end-to-end environment | No production activation

## Verified engineering result

The existing original EmpireDB migration 041 was applied, unmodified, to an isolated **PostgreSQL 18** fixture database named crm_membership_fixture. The production implementation of EmpireDbCrmMembershipReader was invoked through AgencyCanonicalMembershipReader for a synthetic active owner. The identity check used the same restricted SQL function as the canonical CRM authority.

Simultaneously, a separate, real **WordPress 6.8.11 / PHP 8.5.4 / MariaDB InnoDB** staging application activated the existing car-yard plugin and read-only agency integration plugin. Its synthetic WordPress administrator had a freshly issued WordPress Application Password, with the credential stored only in owner-private temporary files, not in the repo or receipts.

A trusted, private Python child process under scripts/agency_mcp_live_wp_e2e/combined_authority_bridge.py created a short-lived **test-only agency-audience Ed25519 envelope**, authenticated the canonical PostgreSQL membership, bound it to a **synthetic** WordPress site grant and connector registry, and checked an owner-only credential reference. A Node MCP process used the existing revocation-guard.mjs before every tool. This is **actual Python-to-Node process integration** over local private stdio; it does not open a new network service. The classic server.mjs remains unchanged.

## Real connected test

Runner: scripts/agency_mcp_live_wp_e2e/run_combined_pg_wp_mcp_e2e.sh

1. Verified MCP tool list contains only two read tools.
2. Allowed an MCP capabilities read with an active PostgreSQL 041 membership, then successfully read the real synthetic WordPress/MariaDB inventory through the authenticated REST API.
3. While the SAME MCP session remained open, updated only the **synthetic membership row in the disposable PostgreSQL** instance to disabled/revoked.
4. On the following MCP inventory and capability calls, the private Python authority re-read membership through the actual 041 SQL function; the guard rejected those calls **before another WordPress API read**.
5. Closed the guard and verified another tool request was denied.
6. Revoked the temporary WordPress Application Password through the real WordPress API and confirmed the old credential returned HTTP 401.
7. Removed the temporary databases, HTTP listener, Unix sockets and credential files on exit. PostgreSQL TCP and MariaDB TCP were disabled; PHP was bound to 127.0.0.1.

**8/8 combined MCP checks passed.** Evidence is recorded under docs/commercial/EMPIRE_AGENCY_COMBINED_PG041_MCP_WORDPRESS_REVOCATION_20261023.json with SHA256 hashes of the exact source, unmodified SQL migration and existing WordPress/MCP plugins. No passwords or signing private keys are in the receipt.

## Important limitations and next owner-bound tasks

This is the FIRST combined **real-engine isolated test**. The PostgreSQL database was a disposable replica containing only a synthetic owner, **not** the live EmpireDB production instance. The WordPress site was a disposable installation containing fictional stock and no customer PII.

The signing key is generated exclusively in the isolated test, the site grant/connector registry are still synthetic fixtures, and credential delivery is via private temporary files, **not a managed production vault**. The Node MCP guard takes a private Python child-process callback; a customer deployment requires its own trusted service launcher, signed site authority, durable replay storage, key rotation, per-tenant secret access and remote API TLS/OAuth review.

The next actual production prerequisite is authorised canonical **agency WordPress site ownership grants** plus a service-owned credential provider, not another tenant database or CRM. Production tenant membership reader access requires approval from the canonical security owner; this test does not imply new database grants. On real customer tenants, never deactivate memberships merely to test; use an authorised synthetic test tenant or an isolated replica.

No production services, EmpireDB records, Smart CRM data, outbound messages, public bookings or payments were changed. No remote MCP or externally published WordPress API was activated. The React/Three.js/Tailwind premium website and V0.3 booking plugin remain intact.
