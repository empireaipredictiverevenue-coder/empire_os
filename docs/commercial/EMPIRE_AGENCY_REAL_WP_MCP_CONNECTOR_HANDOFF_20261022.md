# Empire AI Agency — Actual WordPress/MariaDB MCP Authentication

22 October 2026 | Isolated synthetic development branch | Production OBSERVE

## Completed proof

The existing read-only WordPress REST plugin and MCP v2 stdio server were preserved. A separate optional scoped entry point was added for the actual WordPress 6.8.11, PHP 8.5.4 and real MariaDB InnoDB demonstration test. HTTP was bound only to 127.0.0.1 and MariaDB used a private Unix socket with networking disabled.

A real WordPress Application Password was created for the fictional administrator, written to a temporary 0600-protected file, injected into the spawned MCP process through its environment, used to read the actual WordPress inventory, then revoked through WordPress. A final REST request with the revoked credential returned HTTP 401.

The 12 successful end-to-end checks include real WordPress anonymous HTTP 401, authenticated HTTP 200, actual MariaDB inventory, bounded and private fields, MCP handshake with exactly two read-only tools, booking-write tool rejection, oversized pagination rejection and explicit synthetic tenant/site scope.

Immutable receipt: docs/commercial/EMPIRE_AGENCY_REAL_WP_MYSQL_MCP_AUTH_E2E_20261022.json. It pins the tested source files by SHA256 and stores no secret values.

## Connector registry and test-only credential management

The registry declares exactly one synthetic connector: wp-synthetic-inventory-read-v1 for tenant empire-agency-demo and site car-yard-synthetic. The scope allows capabilities:read and vehicles:read, never writes. The optional scoped-server.mjs checks exact tenant/site/connector identifiers, local staging activation flags, runtime-injected Application Password, and a 127.0.0.1:port origin before starting the original MCP protocol adapter.

No password is committed to Git, sent to the React frontend or placed in the receipt. The original server.mjs remains available for previous mock-only local staging and does NOT enforce this new scope check: select the new scoped-server.mjs when conducting site/tenant integration rehearsals.

This is a limited credential management foundation: runtime injection, WordPress-native issuance and revocation, and scope checks. It is NOT a production credential vault, signed tenant authority, remote OAuth service, or live third-party connector. WordPress still authorises against local administrator permissions; the tenant/site registry check runs in the scoped MCP launcher, not a signed WordPress tenant ACL.

## Release boundaries and next gates

- No real vehicle feed, customer data, CRM, email, webhook, public booking, checkout or payment feature was enabled.
- No live Empire AI WordPress site, EmpireDB, Smart CRM or financial system was modified.
- No production agent gateway, remote MCP HTTP endpoint, or external SaaS API was activated.
- Remaining: canonical signed site and tenant ownership; vault-backed per-provider secrets, rotation and revocation; OAuth 2.1 and audience-bound access tokens for remote MCP; client-granted scopes; audit/redaction/rate-limits; HTTPS, abuse tests, privacy rights and separate customer publication authorisation.
- The rootless disposable runner is scripts/agency_mcp_live_wp_e2e/run_auth_e2e.sh. It requires the current isolated feature branch and creates and deletes its own temporary credentials, site and MariaDB data. It does not support a production database or customer endpoint.

This is the first actual end-to-end authenticated MCP-to-real-WordPress-on-MariaDB evidence for the existing agency delivery engine; it does not establish a production-ready multi-tenant connector service.
