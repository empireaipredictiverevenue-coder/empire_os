# Empire AI Website Delivery — API, integrations and MCP foundation
22 October 2026 | Isolated feature branch | Synthetic staging only

## Goal

Make our existing WordPress + React + Three.js delivery engine extensible to clients' stock feeds, APIs, analytics, schedules and future EmpireOS agents, while preserving the V0.3 booking plugin, isolated website releases and canonical Smart CRM authority.

The optional WordPress companion API and the separately launched MCP adapter are NOT installed on a live website or connected to real client data.

### Architecture

Authorised AI host
 → trusted EmpireOS tenant-scoped gateway (future, NOT live)
 → local stdio MCP adapter (implemented, disabled by default)
 → authenticated WordPress GET on 127.0.0.1 (tested through mock)
 → optional WordPress integration plugin (tested with real disposable WordPress)
 → existing synthetic vehicle CPT.

The browser-side React bundle must not contain MCP credentials or a public MCP URL.

## Added components

- WordPress companion plugin: prototypes/agency_wordpress_service_handoff_20261022/empire-agency-integration-bridge/
- Versioned connector configuration contract: integration-contract.json in that directory
- Separate MCP stdio server: prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/server.mjs
- Source-specific integration tests: scripts/integration_wp_e2e/ plus private Node test.mjs

These extensions do not change the existing V0.3 booking store or published theme. No new database migrations or WordPress writes are introduced by the optional API.

## Native WordPress REST contract

Routes register ONLY when all three independent conditions hold: explicit EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED true, EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY true, and WP environment local/development.

The only endpoints are:
- GET /wp-json/empire-agency/v1/capabilities
- GET /wp-json/empire-agency/v1/vehicles?page=1&limit=10

Authenticated WordPress administrator permission manage_options is required. WordPress core handles browser cookies/nonces or future HTTPS Application Passwords. There are no public custom vehicle writes, no bulk customer export, no booking-write API, no CRM/funds/email endpoints. Vehicles return explicitly allowlisted synthetic fields, published visible inventory only, maximum 20 records, Cache-Control private/no-store and noindex.

On a production WordPress environment, or without one of the flags, routes are NOT registered. No global WordPress REST API restrictions are introduced.

## Local MCP bridge

The isolated Node adapter uses official MCP SDK v2 packages @modelcontextprotocol/server v2.3.1 and @modelcontextprotocol/client v2.3.1 for tests, with Zod schema validation. The protocol is stdio only; it does not listen on a public HTTP port.

Startup requires explicit EMPIRE_AGENCY_MCP_STAGING_ENABLED=1, EMPIRE_AGENCY_MCP_SOURCE=wordpress_loopback, a WordPress base URL on 127.0.0.1 with port, and separate WordPress user/application-password credentials supplied through the environment. A live remote dealership, arbitrary external URL, redirect or empty credentials is rejected. Only bounded authenticated GET to fixed API paths is allowed, with 5-second timeout and no token leakage in output.

MCP tools:
- agency_get_capabilities — lists synthetic site reading capabilities
- agency_list_demo_vehicles — reads at most 20 synthetic records, paginated

No booking calls, webhook registration, customer data access, CRM writes, email sending, account changes or payment actions are exposed.

MCP remote HTTP production authorization remains UNIMPLEMENTED. A future remote MCP gateway requires OAuth 2.1, audience-bound tokens, protected-resource metadata, actor and tenant binding and separate client approval. Do not treat WordPress application passwords as MCP bearer tokens or forward tokens between different audiences.

## Evidence boundaries

Real WordPress 6.8.11 / PHP 8.3.33 on disposable Playground:
- Default disabled state: no routes and GET returns 404.
- Explicit synthetic local enable: 27 checks passed. Anonymous inventory read 401, Editor 403, Administrator GET 200, POST rejected, pagination bounded, archived and draft records hidden, private meta/content excluded, no write/MCP/CRM/payment activation.

Official MCP SDK v2:
- Six tests passed: actual protocol handshake and tool calls, parameter limits, no unregistered write action, rejection of misleading backend capability, disabled-by-default startup, loopback-only environment restriction and a real spawned stdio MCP server calling an authenticated local mock of the WordPress REST contract.

These are complementary but separate tests. An actual MCP agent authenticated against the native WordPress/MariaDB staging site and customer tenant ACLs are NOT YET verified; no real external connector has been activated.

## Connection roadmap for client deliveries

1. Canonical signed tenant and per-site identity, data-use rights and source provenance.
2. Credential vault, rotation and app-scoped revocation. No credentials in Git, theme bundles or browser JavaScript.
3. Approved vehicle-stock feed import with data quality checks, idempotency and restricted write ownership.
4. Analytics and Search Console read connections; calendar availability reads.
5. Consented enquiries into the EXISTING Smart CRM authenticated tenant reader/writer only after separate authorisation.
6. For any eventual booking, email, social or payment writes: explicit scopes, confirmations, suppression checks, audit receipts, retry/idempotency and rollback.
7. MCP OAuth resource metadata, audience-bound tokens, and permissioned tool registration for any later remote connection.

Keep real third-party API keys, WordPress clients, production EmpireDB, public booking, live outreach and money movement unchanged.

References:
- WordPress REST authentication: https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/
- WordPress Application Passwords: https://developer.wordpress.org/advanced-administration/security/application-passwords/
- MCP 2026-07 authorization: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/index.mdx
- MCP SDK v2: https://ts.sdk.modelcontextprotocol.io/v2/
