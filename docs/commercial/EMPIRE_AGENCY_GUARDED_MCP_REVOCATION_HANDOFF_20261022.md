# EmpireOS Agency Connector — Revocation-Safe MCP Read Gate

22 October 2026 | Existing isolated agency car-yard WordPress branch | No production writes

## What was actually implemented

A **per-tool read authority boundary** was added to the existing Empire AI website-delivery platform without changing the historical MCP server source and its pinned runtime receipts.

The new `empire-agency-mcp-stdio/revocation-guard.mjs` wraps the existing read-only `createAgencyServer` functions. It *requires* an externally supplied fresh authorisation callback. On every MCP capability or inventory call, the wrapper checks authorisation **before any WordPress HTTP read**, rejects false or throwing callbacks, and permits no write tools. The existing historical `server.mjs` is unchanged and remains synthetic/local-staging only, not a production authority gate.

The canonical Python preflight from commit 89383ba0d was extended:

- `empire_os/agency_connector_authority.py` binds the signed, agency-audience, short-lived grant to an expiry timestamp; previously verified signed JWTs for CRM still cannot grant agency access.
- `empire_os/agency_connector_preflight.py` adds `revalidate_agency_read_operation`. It checks *current* owner/admin tenant membership with the **existing EmpireOS tenant isolation primitive**, current site grant, current registry record, approved operation, authority expiration, and the current owner-protected credential file. A revoked, rotated or replaced credential invalidates the prior session. Credentials are not included in the non-secret session receipt.
- `empire_os/agency_connector_credentials.py` continues to use approved, private owner-only file delivery. It is **not a provisioned production vault** and the product has not obtained any real customer secret.
- Offline Python tests cover signed grant, replay, expiry, revoked membership, site grant, registry, file rotation and unsafe file permissions.

## Actual disposable WordPress/MCP validation

The new `scripts/agency_mcp_live_wp_e2e/run_guarded_revocation_e2e.sh` reused the approved temporary WordPress 6.8.11, PHP 8.5.4 and MariaDB InnoDB fixture with loopback-only HTTP and MariaDB private Unix socket; all vehicle records and users were fictional.

The new `guarded_real_wp.mjs` exercised MCP protocol calls to **real authenticated WordPress inventory and capabilities**. It then changed the **synthetic mutable authority state** during the same MCP client session:

- Active capability and inventory reads succeeded.
- Revoking synthetic tenant membership denied a following inventory read, with no new WordPress request.
- Revoking synthetic site grant denied capability access, with no WordPress request.
- Disabling synthetic connector registry denied inventory access, with no WordPress request.
- Invalidating the synthetic connector credential denied capability access, with no WordPress request.
- Closing the guard denied all later reads.
- After the fixture, the WordPress Application Password was revoked using native WordPress APIs; old credentials returned HTTP 401.

**9 guarded WordPress/MCP checks passed.** The structured run receipt is `docs/commercial/EMPIRE_AGENCY_GUARDED_MCP_WORDPRESS_REVOCATION_20261022.json`, including source SHA256 pins, WordPress version, synthetic-only status, and no client/customer data or production changes. Previous WordPress MCP proofs remain unchanged.

## What this does NOT prove

**No live EmpireDB tenant membership was queried or revoked.** The per-tool authorisation callback in the browser-stage test was a synthetic mutable test fixture. We have **not** wired the canonical Python preflight into the actual MCP launcher across the Python/Node process boundary with a production-grade authentication service. No trusted canonical site-grant service, signing authority, replay store, secret vault, TLS-verified remote WordPress or OAuth-protected remote MCP endpoint was activated.

The next owner-bound milestone is an independently authorised **site-grant reader** backed by current canonical tenant ownership and a separately controlled **agency-audience signing issuer**, followed by a service-owned secret provider. Once those exist, the MCP launcher must use a trusted per-request check through this new guard. The mutable fixture cannot be used as an authority source in any customer release. No duplicate Smart CRM or tenant service is authorised.

## Reproducibility / change control

- `node --test revocation-guard.test.mjs` verifies three guarded MCP protocol cases and mid-session revocation.
- `pytest tests/test_agency_connector_authority_preflight_20261022.py` verifies Python trust boundaries, expiry and credential revocation.
- `bash scripts/agency_mcp_live_wp_e2e/run_guarded_revocation_e2e.sh` recreates a disposable, rootless WordPress/MariaDB staging environment and declines to overwrite the historical receipt.
- All launchers and tests remain on `feature/agency-wp-car-yard-private-20261022`. Existing production website, EmpireDB, Smart CRM, live outbound and payment controls are unchanged.
