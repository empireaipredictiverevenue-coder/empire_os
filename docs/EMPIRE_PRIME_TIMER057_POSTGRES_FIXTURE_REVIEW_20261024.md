# EmpireOS / PRIME Timer Migration 057 — Actual PostgreSQL Fixture Review

Date: 24 October 2026
Original scope: EmpireOS, PRIME, ASTRA/Voice Lab, canonical EmpireDB PostgreSQL.
Branch: `feature/prime-universal-evidence-fusion-20261024`
Release: **HOLD** (isolated research; not owner-signed, not production applied)

## What was actually executed

Used the installed `pg_virtualenv -t` to launch a **disposable PostgreSQL 18.6 cluster**. It ran on port **5433**, with data in `/tmp/pg_virtualenv.../data/18/regress`. The main PostgreSQL service runs separately on port 5432 and was not targeted, queried, restarted or migrated by this fixture. The temporary fixture and its roles/data were discarded when the `pg_virtualenv` process finished.

From the existing original research worktree:
```bash
cd /home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024

# Only this wrapper creates the throwaway cluster. The script refuses any
# postgres instance without a temporary pg_virtualenv data directory.
pg_virtualenv -t bash scripts/rehearse_prime_timer_pg_fixture_20261024.sh

# Automated pytest wrapper, including a refusal check on port 5432:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_prime_timer_pg_fixture_20261024.py \
  tests/test_prime_flagship_timer_recovery_shadow.py
```

The exact held `migrations/empiredb/057_flagship_voice_timer_ledger_held.sql` file executed successfully **inside the disposable `empire_timer_fixture` database only**, following the intended migrator NOLOGIN/non-superuser role preflight. The script separately established wrong-DB and missing-role fail-closed behaviour.

## Concrete actual PostgreSQL observations

30 actual fixture assertions passed:

- Guard for wrong database fails, and missing migrator-role guard cannot leave half-created tables.
- Deliberately injected SQL division-by-zero **after table/function creation** causes an atomic transaction rollback; both tables and the trigger function are absent afterward.
- Unmodified migration 057 runs cleanly; second application is rejected rather than overwriting prior objects.
- Both request and event tables have **FORCE ROW LEVEL SECURITY**. There are zero installed row policies and no PUBLIC table grants. A temporary unprivileged role with SELECT and INSERT grants created *only in the disposable fixture* sees zero rows and cannot insert because no row policy permits it.
- Owner/superuser-only synthetic INSERT data proves tenant-bound composite foreign keys, unique request/event key enforcement and payload check constraints; duplicate seq and digest, missing foreign tenant, invalid duration/due date and provider receipt constraints are rejected by PostgreSQL.
- Both append-only triggers reject UPDATE and DELETE, including from the superuser in the disposable fixture.
- There is **no automatically installed atomic claim RPC** or runtime delivery permission.

### Important gap found, independently reproduced on PostgreSQL

The existing 057 DDL enforces **storage integrity**, not the complete legal event lifecycle. A privileged database writer can insert a syntactically valid `PROVIDER_DELIVERED_REPORTED` event immediately after `TIMER_CREATED`, **without** an intervening `DISPATCH_CLAIMED` and `PROVIDER_ACCEPTED_REPORTED`.

This was demonstrated only in a **rolled-back disposable test transaction**, with no claimed provider receipt considered authentic. No invalid event remained in the fixture.

**Consequently 057 must not be used as a production general-purpose writer**. Existing forced RLS/no runtime grants remain critical, but they do not replace a verified, tenant/consent-bound atomic state transition and separate authentic provider-receipt validation. The Python `prime_flagship_timer_recovery_shadow.py` already rejects invalid sequence transitions in synthetic replay. The database still needs its own approved enforcement for any future writer.

## Next original-owner approval boundary

1. Original EmpireDB and Security owner: review the actual migration fixture receipts; approve or revise the proposed 057 schema, RLS policy strategy, exact tenant/actor/consent proof contracts, the migration location and rollback evidence. **No production migration was run.**
2. Original ASTRA/Scheduler owner: design the atomic claim and legal-transition writer, including transaction isolation and concurrency, bounded lease/recovery, revocation/cancellation ordering, source authentication, idempotency and exactly-once *claim* (not a promise of exactly-once external delivery).
3. Original Notification/Privacy owner: independently verify delivery receipts, external-transport opt-in, device bindings, retries and erasure policy; no automatic resend of ambiguous in-flight claims.
4. Original Voice/Founder owner: only connect a real task interface after authenticated ingress and opt-in test; the current GET-only cockpit must still say **NOT_CONNECTED**.
5. Independent validation: run concurrency and crash-recovery in a disposable real PostgreSQL database, then owner-signed production deployment review and a separately permitted test notification before any user-facing claim.

## Commercial truth

This is a verified isolated database-engineering milestone, not an active timer service, external notification, £250k appraisal, purchase order or new realised revenue. Existing production EmpireDB, Smart CRM, Voice Gateway, scheduled tasks, trading/payment systems and buyer communications remain unmodified.

One original EmpireOS. One original EmpireDB. One PRIME, ASTRA and Voice Lab.


## Current independent test results and limitations

- Direct disposable PostgreSQL 18.6 fixture execution: **30/30 actual SQL assertions passed**, with explicit successful disposal of the temporary `18/regress` cluster afterward.
- Reproducible pytest wrapper and original timer recovery contracts: **42 passed**, one inherited Starlette/anyio deprecation warning. The wrapper also rejects a port-5432 invocation *before connecting*.
- Original Voice Lab/timer/AGI/Founder/recovery cross-check: **157 passed**, same inherited warning. `bash -n` and `git diff --check` passed.
- The fixture proves DDL integrity and permissions in a disposable database, **not** signed original EmpireDB DBA approval, end-to-end durability with a real persistent server, multi-writer atomic claim, authenticated source receipts, real devices, actual reminder delivery, zero downtime, commercial revenue or a £250k valuation.
- **Explicit material design gap:** privileged direct INSERT can bypass the logical event state machine; this was observed and rolled back. There must be no live runtime writer until the original owners approve and independently validate an atomic guarded transition interface.
