# EmpireOS Agency — Canonical Tenant Authority and Credential Reference Preflight

22 October 2026 | Isolated feature branch | No production activation

## Outcome

A new **preflight-only** agency connector authority adapter now uses existing, canonical EmpireOS `saas_scale.TenantMembership` and `tenant_isolation.authorize_tenant_resource` primitives. It does not establish a new CRM, mutate the database, issue a production access token, or start a connector automatically.

It solves a trust-boundary problem with the old staging registry: matching tenant/site strings supplied as environment variables is **not** proof of canonical tenant authority. The old `scoped-server.mjs` remains valid for its **synthetic** WordPress/MCP tests, but MUST NOT be treated as production tenant verification or launched against real client records.

### New code

- `empire_os/agency_connector_authority.py`: verifies a purpose-bound, short-lived Ed25519 signed **agency** envelope from pinned trusted issuer keys, not a CRM-only token; demands an exact canonical UUID tenant, site, connector, credential reference, WordPress loopback origin and two read-only permissions. Requires a live/fresh authoritative membership callback, matching site-specific grant callback, and one-time nonce consumption. A disabled/cross-tenant member, invalid signature, revoked site grant, incorrect audience, expiry or replay fails closed.
- `empire_os/agency_connector_credentials.py`: reads one owner-only credential file selected by a trusted reference. Enforces private directory/file ownership and permissions, no symlinks or traversal, size/format limits and inode checks with O_NOFOLLOW. An approved credential reference is not itself a credential.
- `empire_os/agency_connector_preflight.py`: joins the signed issuer + canonical membership and site grant to a **separately authoritative, owner-controlled registry** callback before resolving the secret. Returns a sealed session with a non-secret receipt; the secret is excluded from representation/metadata.
- `prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/canonical-authority-contract.json`: describes precisely the dependencies the real site/tenant owners must provide; all production flags remain false.
- `tests/test_agency_connector_authority_preflight_20261022.py`: deterministic, synthetic Ed25519 signing test, canonical membership/site grant and connector registry fixtures, revoked/expired/cross-tenant/replay tests and owner-only secret rotation/revocation/permissions tests.

## Existing independently proven capability — unchanged

Previous staging evidence from commit 7578d489b: a real WordPress 6.8.11 and MariaDB database accepted authenticated reads through the MCP stdio adapter using a synthetic temporary WordPress Application Password. 12 end-to-end checks passed; credential revocation returned HTTP 401. That test did **not** connect canonical EmpireDB tenant membership.

This new preflight extends the trust contract on the EmpireOS side. It has **not yet been inserted into a production-approved MCP runtime** because the actual trusted issuer, current site membership/ownership lookup, replay store and credential-delivery owner have not been provisioned. The offline signed-envelope tests use ephemeral test keys and synthetic grants only. Do not mistake them for a production root signature.

## What the existing owner must supply

1. A separately approved agency-audience Ed25519 issuer and an immutable trusted public-key roster, **not** a CRM-audience token/key substitute. The CRM verifier is intentionally bound to audience `empire-revenue-crm` and scope `crm:read`; those claims are never sufficient for the agency.
2. Fresh, bounded canonical tenant membership lookup and an authenticated *site ownership + connector grant* reader from the existing owner; query both user and tenant, and recheck revocations. Never construct grant rows from user-supplied connector names.
3. Trusted, append-safe nonce/replay protection and a separately controlled connector registry (tenant/site/connector/credential_ref/operations).
4. A dedicated service identity with credential delivery using existing root-controlled systemd LoadCredential or an approved vault provider. The new private-file adapter demonstrates secure file reading in temporary synthetic tests, **not a production vault**. It is not sufficient to have multiple tenant sites share the same Unix credentials.
5. A separately authorised connector-launch owner that invokes the preflight before starting stdio, with actor/tenant audit receipts; later OAuth 2.1 for any remote MCP HTTP endpoint, HTTPS WordPress access and correct token audiences.

No services, secrets, systemd files, web endpoints, financial permissions or CRM/database records have been changed. No client integrations are live. Existing WordPress premium child theme, V0.3 booking store, EmpireDB, Smart CRM, outbound and payments remain unaffected.

## Commercial objective

Once the canonical issuer/site-binding owner and credential provider are supplied, the optional WordPress inventory reader can be activated per authorised client, with strict least-privilege boundaries. Real stock feeds, enquiries, booked work, outbound and payments require separate consent, retention, counterparty and financial approvals. Avoid creating another CRM or website builder.
