# Empire AI Predictive Cloud V4.7 — dual-owner signed source admission (held research)

Date: 24 October 2026. Original EmpireOS / PRIME / ASTRA / Predictive Cloud / EmpireDB PostgreSQL / one Smart CRM.
Branch: `feature/prime-universal-evidence-fusion-20261024`
Release state: **OBSERVE / research only / no production admission**.

## Problem addressed

The original PRIME source fusion accepts owner-prepared, privacy-reduced custody review summaries, and correctly disclaims that a caller's `OWNER_REVIEWED_PERMITTED` claim authenticates source rights. The earlier Redis Streams recovery proof (V4–V4.6) guarantees no source identity or tenant authority. This increment creates a **separate offline cryptographic validation fixture** that is subordinate to the existing EmpireDB and CRM, not a second identity provider.

## Built and exercised

- `empire_os/predictive_cloud_v47_admission_shadow.py` accepts a strictly scoped, canonical JSON event claim and two detached Ed25519 signatures from **separately sourced trust roots**: source custody owner and CRM tenant authority owner. It requires distinct key material, valid key IDs, an exact RFC3339 UTC interval, 15-minute maximum claim lifetime, a 5-minute recent issue bound, supported sector, permitted purpose `PRIVATE_PREDICTIVE_RESEARCH_ONLY`, canonical UUID, SHA-256 opaque digest fields, exact event kind and a positive bounded revision.
- The signed envelope **cannot supply its own trusted public keys**. An externally injected fixture trust-root object owns the source and tenant keys; role-swapping and key reuse are rejected. Signature bytes cover an exact, domain-separated, sorted JSON payload with an event-specific nonce digest.
- A **second, independently supplied** revocation snapshot vetoes source digests, event digests and either signing key ID. The verifier also requires a separate canonical owner-held EmpireDB readback (exact tenant, sector, entity/source/event digest, revision, kind, latest watermark, withdrawn, source review, delivery and execution authority). Even a correctly signed claim cannot outrun a newer revision or withdrawal.
- `scripts/rehearse_predictive_cloud_v47_pg_admission_20261024.sh` runs only in isolated PostgreSQL 18 `pg_virtualenv`, applies the already-prepared **held** migration 064 in the disposable DB, and creates no new production table/role. `scripts/rehearse_predictive_cloud_v47_pg_admission_20261024.py` generates two independent Ed25519 keypairs in volatile memory, stages a fictional candidate, reads it back using a real read-only PostgreSQL transaction, tests valid fixture signatures and negative cases, then stages a newer withdrawal and proves the earlier signed event no longer passes.
- `tests/test_predictive_cloud_v47_signed_admission_20261024.py` covers signer forgery, cross-tenant injection, tampered signatures, wrong purpose, malformed IDs, expired claims, stale/cross-tenant canonical records, revoked events/sources/keys, key-role impersonation and missing owner readbacks. `tests/test_predictive_cloud_v47_pg_admission_20261024.py` repeats the isolated PostgreSQL acceptance.

## Exact authority boundary

The offline test's **signature verification is real Ed25519 cryptography**, but the signers, tenant, keys, events and source custody records are fictional. Neither trusted production key custody nor real source usage rights, consent, partner contracts, CRM login authority, tenant memberships or data licensing are available in this test. The caller-provided fixture root and revocation snapshot do not establish genuine production trust.

A passing fixture returns `fixture_dual_signature_valid=true`, but forces **`production_source_admitted=false`, `redis_publish_authorized=false`, `real_source_rights_independently_verified=false`, `real_crm_membership_verified=false`, `execution_authority=none`, recognised revenue null**. It never calls Redis, outbound, treasury, payment, CRM, live source APIs or production EmpireDB. Nothing is mounted to the application.

## Owner-controlled next steps

1. Original CRM/Security owners define real *separate* trusted key issuance, rotation, verifier role and custody; bind authentic tenant sessions from canonical EmpireDB roles and a strict revocation reader. Keys cannot be provided by the untrusted request.
2. Original Data Cloud/source owners independently verify source licences, permitted uses, genuine event timestamps, source withdrawal rights and entity scope; link source status to canonical EmpireDB readback in a fully read-only transaction.
3. EmpireDB owner reviews schema/ACLs and approves any later migration and signed event journal through the existing backup and rollback governance. Held 064/065 remain unapplied.
4. Only thereafter evaluate whether a minimal advisory event may be displayed to ASTRA/PRIME. There is **no** inferred permission for automated outreach, ads, payment, order, pricing, or real routing.

This is a genuine tested cryptographic gate for a fictional admission fixture, **not evidence that real third-party commercial data has been admitted**.

No live database migrations, external API calls, redis publishing, scheduled workers, outbound, paid traffic, treasury or money changes.

**One EmpireOS. One Predictive Cloud. One canonical EmpireDB. One Smart CRM.**
