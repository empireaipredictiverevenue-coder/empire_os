# Empire AI / Original PRIME — EmpireDB 059 Durable Callback Nonce Custody

**Date:** 24 October 2026
**Branch:** `feature/prime-universal-evidence-fusion-20261024`
**Status:** Implemented and exercised **in a disposable PostgreSQL 18.6 fixture only**. **NOT applied to canonical production EmpireDB**. No live notification provider/sender, webhook, customer or scheduled delivery.

## Original flagship continuity

This is the immediate next increment in the **same** original EmpireOS flagship:

1. Original Voice Lab local Kokoro/Whisper recognised a fictional spoken command, spoke an acknowledgement, and executed a real **two-second in-memory timer** with one **local-only** expiry receipt.
2. Held original EmpireDB 057 created append-only tenant-bound timer/event tables and was exercised in a disposable PostgreSQL fixture. Its original DDL alone permitted logically impossible event order from privileged INSERT.
3. Held original EmpireDB 058 added atomic database claim/cancel and an INSERT state guard. Two competing real PostgreSQL sessions yielded exactly one accepted claim. Never deployed.
4. Original `prime_flagship_provider_reconciliation_shadow.py` tested signed **fictional** provider callbacks but explicitly had only in-memory replay protection. Restart could lose the "seen nonce" set.
5. **This increment (059)** supplies proposed **durable original EmpireDB callback custody** that distinguishes accepted/failed/delivered-reported, binds back to the real claimed timer row in the disposable fixture, and rejects repeated callback nonces across connections and concurrently competing workers.

The original EmpireDB, original PRIME/Digital Twin, original ASTRA, original Voice Lab and original Smart CRM remain canonical. No Supabase, new standalone assistant or duplicate production scheduler.

## Implemented

### Held migration

`migrations/empiredb/059_flagship_timer_provider_receipt_custody_held.sql`

Preflight rejects incorrect database, missing 057/058 predecessor objects, absent or overprivileged `empiredb_migrator`, preexisting migrator memberships, already-installed receipt objects and non-FORCE-RLS predecessor tables.

The new `empire_prime_timer_provider_receipts` table contains only **bounded metadata**: tenant UUID, timer digest, provider code, globally provider-scoped nonce digest, receipt digest, original dispatch-claim event digest, delivery-reference digest, source-attestation digest, stage, ordinal, UTC timestamps. No raw speech, transcript, email, location, device identifiers, webhook body or credential.

It has:
- Unique `(provider_code, callback_nonce_digest)` and `(provider_code, receipt_digest)` for replay protection across **timers and tenants**, including process restarts. PostgreSQL indexes enforce atomic uniqueness in a two-worker race.
- Unique event sequence `(tenant_id,timer_digest,callback_seq)` plus source and original timer claim binding. Receipt cannot be attributed to an unclaimed or cancelled timer, nor to an unrelated dispatch event.
- Allowed stage order: first **ACCEPTED** or **FAILED**; if accepted, second **DELIVERED** or **FAILED**. No delivered-before-accepted, more than two callbacks, mismatched provider or delivery reference, fake old/future timestamps or state promotion after failure.
- A database INSERT guard takes `SELECT ... FOR UPDATE` on the same request row used by migration 058. An append-only trigger refuses UPDATE/DELETE.
- Forced row-level security, a policy solely for original NOLOGIN non-superuser migration owner, no public/application row access or runtime writer grant, no webhook, no service, no scheduled worker or callable sender.
- Late-error rollback and repeat-apply fail-closed behaviour.

This is **not a substitute for provider cryptographic signature verification**. A privileged and authorised database writer could still introduce fabricated data if source governance fails; a PostgreSQL superuser can disable triggers. The callback digests do not establish a real sender, intended device, user permission or human receipt. The owner must verify real provider signatures and consent *before* any permitted future INSERT.

### Executable isolated fixture and automated test

- `scripts/rehearse_prime_timer_pg_receipt_custody_059_20261024.sh`: requires a `pg_virtualenv`-generated temporary PostgreSQL data directory, verifies port at least 5433, and refuses the main cluster. Creates/drops synthetic schema and data solely within temporary PostgreSQL 18.6. No production connection or modifications.
- `tests/test_prime_timer_pg_receipt_custody_059_20261024.py`: wraps the real disposable fixture, statically rejects runtime privileges, verifies 5432 refusal and checks representative database receipt tests through SQL.
- Existing `prime_flagship_provider_reconciliation_shadow.py` and the GET-only Founder Console already distinguish synthetic provider statements from independent real delivery; **they remain unchanged in this increment** and still show `NOT_CONNECTED` for real providers.

## Executed real PostgreSQL fixture

```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024
pg_virtualenv -t bash scripts/rehearse_prime_timer_pg_receipt_custody_059_20261024.sh
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_prime_timer_pg_receipt_custody_059_20261024.py \
  tests/test_prime_flagship_provider_reconciliation_shadow.py
```

**35 / 35 separate actual PostgreSQL fixture assertions passed** on temporary port 5433, including:
- Wrong DB, missing 057/058, forced late SQL exception and whole-transaction rollback, RLS, owner-only policies, no PUBLIC function execution and reapply refusal.
- Actual original 058 atomic claims for multiple fictional timers before receipt processing.
- Delivered-before-accepted, claim-event mismatch, wrong tenant/source, mismatched provider/reference and terminal-status replay rejected by the database.
- Callback nonces and receipt digests remain unique across separate PostgreSQL connections and cannot be reassigned to another timer.
- A privileged UPDATE/DELETE of recorded receipt metadata is refused; an application-fixture role given test-only SQL privileges still cannot see/insert rows through FORCE RLS.
- **Two concurrent real PostgreSQL connections** attempted the same callback nonce for **different timers**; one row committed and the second failed on the unique constraint. No duplicate survived.
- No provider send function, outbound call, email, device alert or production database writer was created.

**31 new combined focused tests passed** for the disposable fixture wrapper and original synthetic receipt validator (one inherited Starlette/anyio warning). These are not independent real-world notification outcomes.

## What remains missing

1. Original DBA + Security independently review migrations 057–059, existing production migrations/roles, RLS, purpose/retention/erasure, measured concurrency and rollback. **Real production migrations remain OFF**.
2. Original Identity + Voice obtain and verify explicit user/device consent, cancellation and tenant authority. A digest field is not proof of consent.
3. Original Notification owner selects an actual provider and verifies the **provider's real signing scheme**, replay/timestamp rules, webhook rights, key rotation, sandbox credentials, accepted-vs-device-delivered semantics and delivery reconciliation. No product-provider integration is active here.
4. Original ASTRA owner implements a secure callback-custody gateway that validates original provider authenticity and identity *before* calling the held DB writer. No application INSERT permission or SECURITY DEFINER EXECUTE grant should be created without separate design and signoff.
5. Original Founder/Identity/Security owners approve private ingress and real consented device test. Existing cockpit must continue saying **NOT_CONNECTED** until provider custody and end-to-end evidence can actually be read.
6. Independently prove restart recovery and a real device **delivery confirmation** using explicitly consenting test identities before calling the flagship's reminders user-ready.

**One EmpireOS. One canonical EmpireDB. One original PRIME/Digital Twin, ASTRA and Voice Lab. No real messages or payments.**


## Current checked acceptance result

- **35/35 independent real PostgreSQL 18.6 fixture assertions passed** in temporary port 5433, including two competing sessions attempting to insert the same provider nonce across two different timers. PostgreSQL committed only one nonce row. The temporary cluster was dropped.
- **1,204 scoped affected-system regression tests passed**, with one inherited Starlette/anyio deprecation warning. This includes the new 059 fixture, prior 057/058 PostgreSQL fixtures, original Voice Lab, PRIME, Digital Twin, AGI, Founder API, CRM, Quant and source-evidence contracts. Not a full-repository suite or owner-approved release.
- A passing fake signature does **not** establish genuine provider authentication. A unique callback row does **not** mean real device delivery. Actual production EmpireDB 059 migration and provider activation remain on HOLD.
- The original Founder cockpit remains labelled provider reconciliation **NOT_CONNECTED** and has no execute endpoint.
