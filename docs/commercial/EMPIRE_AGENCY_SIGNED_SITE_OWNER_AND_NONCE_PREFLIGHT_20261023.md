# Empire AI Agency — Signed Site Owner, Connector Security and Replay Preflight

23 October 2026 | Additive, owner-gated engineering | NOT live production

## Purpose

The preceding real-engine milestone joined original EmpireDB 041 SQL, MCP guard, authenticated WordPress REST, and MariaDB within a single disposable stage (commit 1cd154cea). Its weakest remaining trust inputs were fixture-only site ownership, connector-security approval and a memory-only test replay set. This slice makes those inputs **independently signed and revocable**, and introduces persistent single-host replay protection. It does **not** claim a production issuer, a canonical live site ownership database, a managed vault or a deployed connector.

## Implemented in the original EmpireOS project

1. `empire_os/agency_signed_site_grants.py` supplies an owner-signed site grant reader and a **separately signed** connector-security reader. Both load owner-private, exact-path, bounded JSON envelopes; require pinned Ed25519 public keys supplied independently; verify different signing domains, distinct issuer names, canonical tenant UUID, exact site/connector/credential binding, approved read-only operations and short expiry (up to 24 hours). They reread on every call, so signature replacement, file removal, status=revoked or expiry causes access to fail closed. They accept only the isolated WordPress 127.0.0.1 source presently supported by this stage; **remote customer site origins are intentionally disallowed**.
2. `empire_os/agency_private_nonce_store.py` provides an atomic `O_EXCL` file receipt for each signed session `jti`, keyed by a one-way SHA-256 filename in an owner-only directory. It fsyncs the file and parent directory. Duplicate/replayed tokens, missing directories, unsafe ownership, symlinks, disk errors and permission errors fail closed; the receipt survives process restart on the same host. It is **not a distributed or centrally managed replay service**, and periodic retention/garbage collection must be designed by the eventual owner.
3. `empire_os/agency_owner_gated_connector.py` is a strictly typed composition of the EXISTING `AgencyCanonicalMembershipReader`, independent site-owner and security readers, nonce store, agency-audience pinned issuer keys, and protected credential reference. It refuses arbitrary caller-provided identity functions and reuse of the same signing key across issuer, site owner and connector security. `open_session()` calls our existing signed preflight; `authorize_tool()` rechecks fresh membership, both signed grants and current secret on **every** operation. No production service is launched by importing it.
4. `tests/test_agency_signed_site_grants_20261023.py` and `tests/test_agency_private_nonce_store_20261023.py` test independent synthetic signers, revoked/expired/cross-tenant grants, wrongly bound credential references, tampered signatures, unsafe filesystem permissions, nonce persistence/concurrency, and existing session invalidation. These are offline synthetic signers; they do not create customer or EmpireDB permissions.

## Ownership / activation decision

This slice **does not manufacture site-owner evidence**: its owner signatures are necessary only after the canonical EmpireOS site owner has been independently authenticated and established a real site-to-tenant grant. A generated test key proves verification works, not that a customer granted authority.

The future trusted service owner must supply and maintain: (a) approved, separately managed agency issuer, site-owner and connector-security signing keys with rotation and revocation; (b) canonical tenant membership access authorised by the existing EmpireDB/CRM owner, with least-privilege and fresh revocation reads; (c) genuine site ownership and provider terms/consent; (d) managed per-site credential delivery with revocation; (e) durable, shared nonce/replay authority where requests may span hosts; and (f) audit logs, origin/TLS policy and security review for remote MCP and WordPress. These cannot be inferred or enabled from a fixture.

A service-owned launcher must inject only independently verified, immutable trust roots and paths into `OwnerGatedAgencyConnector`. It must not read a caller-supplied registry or token public key and trust it as authority, and must not treat the prior `scoped-server.mjs` staging environment variables as proof of tenant ownership. The original read-only MCP server, the guarded wrapper, original WordPress plugin and customer booking logic remain unchanged.

## Safety and limitations

- No deployed service, new CRM, SQL migration, EmpireDB role, tenant row, external MCP endpoint, user consent, financial approval or outbound permission was created.
- All file trust checks require owned private files and directories in the local preflight. An eventual systemd `LoadCredential` copy has different file-mode semantics and requires owner-approved integration tests; no claim of direct drop-in production vault compatibility.
- Signing grants are time-bounded local snapshots, **not authoritative DB reads of actual site ownership**. Rejected credentials and authority failures must remain fail closed.
- Existing `31/31` Chromium visual/frontend assertions and joined real-engine staging receipts are historical and remain pinned to unchanged sources; this release does not assert new production UX tests.

## Next real milestone

Review and approve the actual site ownership registry and how it is updated by the existing tenant authority. Provision a distinct, least-privilege agency read identity and managed secret delivery in the existing security service. Integrate the verified inputs with the owner-gated adapter via a production-approved launcher, then perform a test-tenant E2E with fresh, authorised data. Do **not** flip any production flag until explicit owner, security and founder approvals are recorded.
