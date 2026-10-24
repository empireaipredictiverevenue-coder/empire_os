# EmpireOS / Original PRIME — DB Consent Guard 061

**Date:** 24 October 2026
**Status:** HELD; isolated original `feature/prime-universal-evidence-fusion-20261024` research worktree only. No production migration, provider connection, real Identity consent or notification.

## Why this build belongs to the original flagship

One original EmpireOS, canonical EmpireDB PostgreSQL, PRIME, ASTRA, Digital Twin and Voice Lab. The existing original timer migrations remain:
- **057:** immutable timer/event metadata.
- **058:** atomic claim/cancel and ordered event transitions.
- **059:** immutable callback custody, nonce uniqueness, tenant and claim binding.
- **060:** controlled metadata receipt writer; test-only separate SCRAM reader/writer with tenant-restricted read access.
- **061 (new, held):** no receipt can be inserted unless a DB-side independently owned current-consent check returns TRUE.

**Security gap discovered:** 060 validated claim/receipt integrity but did not verify original Identity/Privacy consent at the SQL write boundary. ASTRA's application preflight could be bypassed by a caller permitted to execute 060. The real original Identity/device authority is not verified as available. We do not substitute a fictional consent for it.

## New candidate and fail-closed production stance

`migrations/empiredb/061_flagship_timer_consent_write_gate_held.sql`

- Refuses wrong DB, missing canonical restricted NOLOGIN migrator, unexpected migrator membership, missing 057–060, non-FORCE-RLS predecessor, duplicate installation.
- Creates an owner-only `empire_prime_timer_consent_authority_held(uuid,text,text)` which **returns FALSE for every request** until independently reviewed, authenticated original Identity authority is connected.
- Adds a `BEFORE INSERT` gate on original 059 receipt table. If consent is absent/unverified, PostgreSQL rejects the write with `TIMER061_ORIGINAL_CONSENT_AUTHORITY_UNVERIFIED`. The 060 writer and direct INSERT cannot pass through merely by claiming consent in a request.
- Uses `SECURITY DEFINER`, a bounded empty search path, FORCE RLS and revokes PUBLIC function EXECUTE in the same DDL transaction.
- Creates **no real-user consent table, provider, sender, credential, application permission, production scheduler or login**. Importantly, if 061 were applied with its default deny function to production it would hold all callback writes, not enable notifications. No owner has approved deployment.

## Actual isolated PostgreSQL 18.6 fixture

`scripts/rehearse_prime_consent_gate_061_20261024.sh` is invoked only when `EMPIRE_REHEARSE_HELD_CONSENT_061=disposable_only` inside the existing verified `pg_virtualenv -t` fixture. It applies held 061 after normal 057–060 tests, then tests:

1. Wrong-DB and duplicate migration refusal and no PUBLIC grant.
2. **Default deny** for the independently SCRAM-authenticated original 060 writer, as well as a direct privileged table INSERT.
3. **Fixture-only** replacement of the deny function with a synthetic owner adapter limited to the test tenant and test SCRAM writer. Its `fixture_authorised_device` record is fictional, not a real Identity authority or production consent system.
4. Missing fictional consent keeps writer denied; a matching active fictional consent allows one ACCEPTED metadata receipt through 060.
5. Revoking consent blocks a subsequent otherwise-valid DELIVERED-REPORTED event **inside PostgreSQL** even if the ASTRA preflight were skipped. Existing receipts remain immutable.
6. In a real revocation-first SQL race, the restricted writer waits for the consent row lock, then is denied after revocation commits. No callback row is inserted.

The temporary PostgreSQL cluster, secrets, roles, fictional identities and data are disposed after testing. Production 5432 was not migrated; no real callback signature or device notification was used.

Automated coverage: `tests/test_prime_timer_consent_write_gate_061_20261024.py`. The previous original fixture continues to verify signed fictional gateway callbacks, tenant isolation, replay, and callback-first/revocation-first lock behaviour.

## Critical remaining real-world authority

The current fixture only proves **DB fail-closed logic**, not verified permission to contact a real user. The original 057/059 metadata does not yet bind a verified receiving device digest; real owner-approved user/device/tenant identity, authenticated consent and revocation, provider-specific cryptographic callback verification and a secure gateway-to-EmpireDB trust boundary are still absent.

Original Identity/Privacy/Security owners must establish the existing genuine authority and source rights; the EmpireDB owner must review 057–061, real RLS, restricted roles, rollback and grants; the Notification owner must select one authorised sandbox provider and verify genuine delivery semantics. Do not grant 060 EXECUTE or replace 061 deny function in production until those approvals and tests are independently supplied. The original Founder cockpit remains **NOT_CONNECTED**.

**One EmpireOS. One original EmpireDB. One PRIME / ASTRA / Digital Twin / Voice Lab.**
