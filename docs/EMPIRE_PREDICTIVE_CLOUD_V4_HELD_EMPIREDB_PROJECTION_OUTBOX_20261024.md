# Empire AI Predictive Cloud V4.2 — canonical projection and held outbox

**24 October 2026** · Original EmpireOS / ASTRA / PRIME / EmpireDB PostgreSQL / Smart CRM
**Status: research branch, migration 064 PREPARED ONLY, not applied to canonical production EmpireDB.**

## Engineering result

The earlier real Redis 8.0.5 fixture proved Lua single-key revision fencing but also exposed its limits: after TTL removes a feature Hash, a delayed smaller revision may be accepted as a fresh key. Redis Streams similarly append duplicate digests as distinct IDs. Neither mechanism establishes durable revision or payment truth.

This increment introduces a **PostgreSQL 18 disposable research candidate**. It is intentionally named and constrained as `_held` so it cannot imply that a real source was verified:

- `migrations/empiredb/064_predictive_v4_projection_outbox_held.sql` — canonical-namespace **candidate**, no live application. Unique tenant/sector/entity revision watermark survives Redis TTL conceptually as long as its owning database persists. `INSERT .. ON CONFLICT .. DO UPDATE ... WHERE` enforces a monotonic compare-and-swap under concurrent transactions; withdrawal is terminal for this contract.
- A separate event-digest PRIMARY KEY and tenant/sector/entity/revision UNIQUE constraint reject collisions. A single transaction stages a candidate watermark and an advisory event, or rolls both back. Repeated identical event digests return `HELD_DUPLICATE`, never a new event.
- `delivery_state='HELD'`, `source_review_state='UNVERIFIED'`, `execution_authority='none'` and `redis_publish_authorized=false` are enforced or explicitly returned. No message is sent to Redis Streams, and no stream consumer is created.
- FORCE RLS, an existing-style restricted NOLOGIN migrator prerequisite, no runtime grants, no SECURITY DEFINER. Outbox UPDATE and DELETE trigger rejection helps preserve an append-only candidate event history. No assertion of immutability against a privileged DBA.
- `scripts/rehearse_predictive_cloud_v4_held_outbox_20261024.sh` allows only `pg_virtualenv` temporary PostgreSQL 18 at port >=5433, with `/tmp/pg_virtualenv.*/data/18/regress` server directory. Its cluster is automatically discarded. This script does **not** access production port 5432.
- `tests/test_predictive_cloud_v4_held_outbox_20261024.py` exercises the real temporary PostgreSQL engine plus negative/static boundary checks.

## Fixture acceptance

The disposable PostgreSQL rehearsal verifies rejection of wrong database and duplicate migration, unique source/event digest collision, stale event replay, permanent withdrawal, RLS/no execute grants to a separate unprivileged role, forbidden outbox UPDATE/DELETE and two independent concurrent connections unable to regress the final revision.

These are **structural, fictional-data tests**. The real canonical EmpireDB has *not* been migrated; there are no actual authorised model/source revisions, source rights, tenant memberships, Redis Cloud provider credentials, real economic outcomes or outbound receipts asserted here.

## Owners' next handoff (NOT released)

1. EmpireDB + Identity: bind an existing trusted CRM tenant membership and independently verified event/source authorisation to a signed or owner-controlled revision assignment. The fixture's caller-chosen digests **are not** proof of rights. Review schema backup, restore, ACL, RLS, source erasure and withdrawal semantics before any production migration.
2. Predictive Cloud: define an authenticated projection reader for real canonical source records, with source timestamp custody and independent revocation checks. Do not permit an arbitrary caller to stage events through a production public function.
3. Chief of Staff: implement separately reviewed polling/claiming, delivery receipts, durable idempotent outbox consumer, crash replay handling and backlog controls before any advisory Stream publication. HELD means no queued delivery permission.
4. Cloud Ops: budget/contract, Scaleway-to-Redis Cloud TLS connectivity, region choice, failover, p50/p95/p99 and realistic throughput benchmark. Do not claim Active-Active distributed locks.
5. Finance: actual realised net revenue requires external settled payment/order/cost evidence reconciled in EmpireDB. No Redis event, simulated pCVR or pending outbox proposal can spend funds, route live traffic or authorise USDT on BSC.

**No production schema applied, no service installed, no cloud subscription, no emails, no paid traffic, no money moved.**

One original Predictive Cloud. One EmpireOS. One canonical EmpireDB. One Smart CRM.
