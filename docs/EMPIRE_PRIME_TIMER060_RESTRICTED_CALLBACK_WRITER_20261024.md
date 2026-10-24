# EmpireOS / PRIME Flagship — Held Restricted Notification Callback Writer (060)

**Date:** 24 October 2026
**Original research branch:** `feature/prime-universal-evidence-fusion-20261024`
**Status:** Isolated engineering fixture. NO production migration, no provider, no real user, no device alert.

## One original flagship, one EmpireDB

Continues the previous engineering milestone where original ASTRA verified two independently signed *fictional* Ed25519 authorities and persisted ACCEPTED and DELIVERED-REPORTED metadata into the original held EmpireDB 059 callback ledger in disposable PostgreSQL 18. That earlier fixture performed direct privileged INSERTs, correctly documented as not an approved runtime security boundary.

The new milestone eliminates **direct application table-write permission** from the test receipt path, while preserving the original migrations:
- 057: tenant-linked timer and event ledger.
- 058: serialized atomic timer claim/cancel, event-transition guard.
- 059: immutable callback custody, nonce unique across timers/tenants, ordered callback status, original claim binding, force RLS.
- **060: one restricted custody function**, controlled SQL permission boundary; still HELD and unapplied to production.

## New held migration

`migrations/empiredb/060_flagship_timer_receipt_restricted_writer_held.sql`

The migration is transactional and refuses the wrong database, unverified existing migrator role/membership, missing 057/058/059 tables/functions, non-FORCE-RLS parents and reapplying an existing function.

`public.empire_prime_timer_receipt_record_held(...)` is a `SECURITY DEFINER` function owned by the original restricted NOLOGIN `empiredb_migrator`. It has `SET search_path=''`, `SET row_security=on`, exact limited arguments and returns only an event sequence plus `HELD_METADATA_RECORDED_NOT_AUTHENTICATED_OR_DELIVERED`. It:
- Requires purpose-keyed 64-hex digests, a bounded provider identifier, one of ACCEPTED / DELIVERED / FAILED, a bounded timestamp.
- Serializes on the original tenant+timer request row with `FOR UPDATE`; matches original source digest and exact original 058 DISPATCH_CLAIMED event at sequence 2.
- Determines the next receipt sequence server-side, rather than trusting a caller-supplied sequence.
- Inserts only bounded metadata into original 059, delegating status-order, tenant binding, replay detection and source consistency to 059's append-only trigger and unique indexes.
- Performs no outbound contact, provider connection, CRM action, notification delivery, scheduling or payment.
- Explicitly **REVOKES EXECUTE FROM PUBLIC in the same migration transaction**, does not grant application permissions, create a LOGIN or runtime role, connect a webhook, or activate 057–060.

**A SQL function does not itself authenticate real provider signatures or user consent.** Even a restricted EXECUTE grant is unsafe until the original Security/Identity/Notification owners supply an independently authenticated caller and verifiable real provider/consent authority. The current migration must remain HELD.

## Actual disposable PostgreSQL restricted-role integration

Updated existing *original* fixture:
- `scripts/rehearse_prime_signed_gateway_pg_fixture_20261024.sh` now installs held 057, 058, 059 and 060 in temporary PostgreSQL 18 on port 5433 under `pg_virtualenv -t`. The wrapper refuses port 5432, unexpected host or a non-temporary PG data directory.
- The fixture creates a NOLOGIN `timer_fixture_gateway_exec` role **only in the throwaway database**. It explicitly grants EXECUTE on the single new held function, but grants **no INSERT or SELECT on original 059 tables**. PostgreSQL `has_table_privilege` showed false / false, while function EXECUTE showed true. An attempted `SET ROLE` direct SELECT was denied by PostgreSQL.
- `scripts/rehearse_prime_signed_gateway_db_receipt_20261024.py` still verifies independently signed fake provider/consent envelopes and current fictionally consented device status before the write. The same transaction rechecks fixture consent under a SQL `FOR SHARE` lock. Then the receipt operation is performed under `SET LOCAL ROLE timer_fixture_gateway_exec` through ONLY `empire_prime_timer_receipt_record_held`, with parameters derived from the exact cryptographically verified payload.
- PostgreSQL 059 was the final arbiter of callback nonce replay and ordered stages. Reconnecting rejected the same signed ACCEPTED callback, an invalid provider signature caused no write, revoked fictional consent caused no write, a SQL fixture consent revocation blocked the write, and after restoring this *fictional* consent only the proper ordered DELIVERED-REPORTED record was inserted. Exactly two rows were read back.
- A second synthetic timer exercised **two competing real PostgreSQL sessions** invoking the same restricted writer for ACCEPTED. The first transaction obtained the request lock and committed one row; the second was refused by the original 059 transition guard after the first commit. There was no provider call or actual device alert.
- The temporary database and fixture-only role were destroyed after the test.

**Important fixture limitation:** `psycopg` connects as the fixture superuser, uses it for fake authority readback, and then `SET LOCAL ROLE` for the custody operation. This proves the restricted SQL role's effective rights for the operation, **not** safe production credentials, independent service authentication, separation of duties or real-user authority. A future production gateway must run as its own approved least-privileged identity with original owner-approved tenant/scoped authenticated reads.

## Remaining original-owner release tasks

1. Original EmpireDB/Security owner: independently review held 057–060 against canonical production roles, RLS, owned functions and migrations; approve or revise privileged function design, authentic caller-only EXECUTE rights, atomic source attestation and rollback.
2. Original Identity/Privacy owner: verify actual original per-tenant actor/device consent and revocation atomically under an authenticated, least-privileged source; a digest or fixture boolean is never real permission.
3. Original Notification owner: choose one permitted sandbox provider, authenticate its real signed callbacks and key rotation, and independently establish provider-accepted vs device-delivered semantics. No sender or provider is configured yet.
4. Original ASTRA owner: connect only the approved gateway to the original protected 060 writer, ensure durable nonce, expiry, cancellation, failure/unknown status reconciliation and no blind duplicate send. No automatic production dispatch.
5. Original Founder/Voice owner: retain private GET-only NOT_CONNECTED status until live owner evidence and consented physical device acceptance exist.

No customer, actual device alert, verified revenue, £250k independent valuation or production deployment was produced by this increment.

**One EmpireOS. One canonical EmpireDB PostgreSQL. One PRIME / ASTRA / Digital Twin / Voice Lab.**


## Latest verified acceptance

- Migration 060 installed in a disposable PostgreSQL 18 fixture, following held 057–059, with **no PUBLIC function EXECUTE rights and no live app role or table grant**.
- A fixture-only NOLOGIN role was explicitly granted **EXECUTE on the single held writer function** (this grant is **NOT** part of migration 060). PostgreSQL privilege introspection returned **receipt SELECT=false, receipt INSERT=false, function EXECUTE=true**. A direct `SET ROLE` table SELECT was rejected.
- ASTRA's two-signature synthetic callback integration produced two legally ordered callback custody records, refused the replay after new connections, refused a forged signed envelope, and refused a revoked fictional consent without further writes. Inserting now occurs under `SET LOCAL ROLE timer_fixture_gateway_exec` via the guarded function; the signed payload is the sole source of fields.
- In a separate two-worker real PostgreSQL test, simultaneous calls to 060 for an ACCEPTED callback on the same fictional timer produced **one stored row and one rejected request**.
- **53 targeted 060+ASTRA callback tests passed** after adjusting the migration static check to distinguish an INSERT *inside* the guarded function from a top-level migration DML statement.
- **1,257 scoped original-system regression tests passed**, including original Voice Lab, PRIME, Digital Twin, AGI, Founder, CRM/source/Quant, migrations 057–060 fixture and callback custody; one inherited Starlette/anyio deprecation warning. Not the full repository suite or any authorised production review.
- The disposable PostgreSQL cluster on port 5433 was removed. Canonical production PostgreSQL 5432 remained unchanged, with no notification, email, call, real-device receipt or funds movement.
