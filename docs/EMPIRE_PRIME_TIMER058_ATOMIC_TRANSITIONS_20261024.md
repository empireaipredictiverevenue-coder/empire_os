# Original EmpireOS / PRIME: Held EmpireDB Timer 058 Atomic Claim + Cancel

**Date:** 24 October 2026
**Branch:** `feature/prime-universal-evidence-fusion-20261024`
**Authority:** Research-only, isolated PostgreSQL fixture. No original production EmpireDB migration or runtime scheduler activation.

## Outcome: previous 057 gap closed in PostgreSQL fixture

The original timer ledger 057 had valid storage constraints, FORCE RLS and append-only triggers, but a privileged direct INSERT could skip from TIMER_CREATED straight to a fabricated PROVIDER_DELIVERED_REPORTED event. This gap was independently reproduced and rolled back in the earlier 057 fixture. It was unsuitable for a general-purpose writer.

The new **held** candidate `migrations/empiredb/058_flagship_timer_atomic_transition_held.sql`, applied to a throwaway PostgreSQL 18.6 database **only**, adds:

- An INSERT transition guard *inside the database* for the 057 event ledger. Every event checks the request's tenant and source reference, acquires the request row lock, verifies the contiguous sequence and legal previous event, and checks timer deadlines on the database clock. It rejects a direct privileged INSERT that skips claim/acceptance or duplicates a terminal event.
- A narrowly defined `empire_prime_voice_timer_transition_held` function supporting **only** TIMER_CANCELLED and DISPATCH_CLAIMED. It acquires the **same request-row lock** before reading state and inserting the next immutable event, so competing transactions serialize.
- An original NOLOGIN, non-superuser `empiredb_migrator` ownership restriction, and new FORCE RLS policies for that existing database-only migrator role. A missing role, unexpected role membership, existing policy, non-forced RLS, wrong database or duplicate function **fails the migration closed**.
- `SECURITY DEFINER` routines with an empty search path, FORCE RLS still on, and explicit **REVOKE EXECUTE FROM PUBLIC** in the same DDL transaction; no runtime service role, LOGIN, app EXECUTE/INSERT grant or background process is installed. The original migrator can operate only under original DBA authority; a production role-membership audit is mandatory.
- Provider report transitions are **order-checked by the trigger**, but not exposed via the claim/cancel function. A provider receipt digest is only an unverified *claim*; even a legal PROVIDER_DELIVERED_REPORTED row is **not** independent delivery evidence.

## Real database fixture: what was proved

The original PostgreSQL 18.6 engine was started using `pg_virtualenv -t` on port 5433 and an isolated temporary data directory. The main PostgreSQL 5432 cluster was neither accessed nor modified. A shell fixture refuses the production port or any non-ephemeral PG data directory.

`scripts/rehearse_prime_timer_pg_atomic_058_20261024.sh` performed **29 successfully asserted real PostgreSQL checks**, including:

1. Wrong database refusal; forced error at the *end* of 058 leaves no RLS policies or new functions, demonstrating transactional DDL rollback.
2. Fresh successful migration and strict no-PUBLIC-execute checks; app fixture role cannot call the function.
3. Five synthetic tenant-bound timer rows and first-event entries; source mismatch, cross-tenant scope and unsupported action refused.
4. Cancellation allowed only for a still-pending timer; a claim before due is rejected; a claim after due creates one immutable event and cannot be repeated.
5. A privileged direct INSERT of PROVIDER_DELIVERED_REPORTED without prior claim/acceptance is **now rejected in PostgreSQL**. Ordered synthetic provider claims can be inserted but are never validated as genuine source receipts.
6. **Two competing PostgreSQL sessions** attempted the same timer claim. Worker one claimed and held the request row locked for 1.5 seconds, worker two waited, then failed on the updated state after commit. One DB claim event was observed; no duplicate claim, external send or notification occurred.
7. Owner-only RLS, event-guard trigger, lack of runtime grants and non-destructive repeat migration refusal were confirmed.

The separate original 057 and Python recovery tests remain intact. `tests/test_prime_timer_pg_atomic_058_20261024.py` turns the 058 disposable fixture into an automated regression and rejects execution on port 5432. No customer, provider, microphone, CRM, commercial content or production DB data were read for this experiment.

## Important limits / remaining security work

This milestone proves an **atomic database claim** in a *disposable synthetic fixture*. It does **not** create a production-capable timer service, prove authorisation of any user, publish the voice cockpit, recover a production database after a real crash or send a real alert.

Even with the new event trigger:
- A PostgreSQL superuser can disable triggers/change privileges; production DBA governance, migrations, monitoring and audited role memberships are still indispensable.
- Role-owner policies and a SECURITY DEFINER function require **formal Security/EmpireDB review** before any deployment, especially the implications of membership in the original migrator role.
- Caller-supplied digest equality is *not* proof of lawful microphone processing, user identity, tenant binding or signed consent. The holder of a digest might be untrusted.
- Event ordering is not provider-source authentication. "PROVIDER_ACCEPTED_REPORTED" and "PROVIDER_DELIVERED_REPORTED" remain unverified metadata.
- Atomic database claim does not guarantee exactly-once external delivery. Crash between a provider call and receipt requires a separate authenticated reconciliation process with no blind resend.
- A real owner-operated task must handle genuine clock policy, cancellation UX, the intended device, error/expiry alerts, telemetry, durability and external notification verification.
- No paid buyer, accepted £250k offer, realised revenue, real voice call, reminder subscription, transaction or independent product valuation was established.

## Owner acceptance and next actions

**Original EmpireDB + Security:** independently review 058, role ownership/EXECUTE/RLS, audit existing authentic role memberships and reconcile with canonical production schema; authorise a migration only with verified backups, staging and rollback.
**Original Voice/Privacy/Identity:** bind authentic user/device opt-in and revocation to timer requests; the current digests are synthetic placeholders.
**Original ASTRA/Notification:** provide a permissioned dispatcher, lease/reconciliation semantics, source-authenticated provider receipts, idempotent delivery attempts and failure handling. No automatic live dispatch before approval.
**Original Founder:** private console ingress/auth/mobile acceptance, and truthful NOT_CONNECTED labels until signed evidence exists.

**One EmpireOS. One canonical EmpireDB PostgreSQL. One PRIME, ASTRA and original Voice Lab.**


## Verification and repository boundary

- Actual disposable PostgreSQL 18.6 fixture: **29/29** separately asserted tests passed. Two real competing PostgreSQL sessions serialized their claim attempts and yielded one successful database claim and one rejected competing request. There was no provider call.
- 058 + prior 057 fixture + Python timer recovery suite: **45 passed**, one inherited Starlette/anyio deprecation warning.
- Expanded original Voice Lab, PRIME, Digital Twin, AGI, Founder API, source, Smart CRM and Quant affected-contract regression: **1,173 passed**, one inherited Starlette/anyio warning. This is a scoped regression, not the full repository gauntlet or a signed deployment acceptance.
- The 058 migration and fixture are present on the original research branch only, and the fixture's original PostgreSQL cluster on port 5433 was discarded. Main PostgreSQL 5432 and canonical production EmpireDB were not migrated or written by these tests.
- A successful local claim is not a provider delivery; the original private Founder cockpit still reports timer recovery NOT_CONNECTED. No real timers were activated, real customer data processed, calls/emails sent or funds moved.
