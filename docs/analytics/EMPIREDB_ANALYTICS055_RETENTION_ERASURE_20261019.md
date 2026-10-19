# EmpireDB Analytics055 — staged controlled retention and erasure

**19 October 2026 | Empire Analytics continuation | NOT deployed**

## Why this wave exists

Analytics054 is staged and tested in a disposable PostgreSQL database.
It stores pseudonymous session/consent/event references, but its three
tables are append-only. Without a safe erasure mechanism and an approved
retention schedule, a live website collector would be inappropriate.
The objective is still measured visitors, real session source attribution
and verified CRM-to-payment conversion, not simulated dashboard numbers.

## Implemented

Prepared migration:
`migrations/empiredb/055_first_party_analytics_erasure_held.sql`

Built as an additive migration on top of exact unchanged Analytics054.
It can be tested only against the fixture database
`empire_analytics_fixture`; production needs a **separate explicit
founder-approved privileged DBA migration** after privacy review.

- Exact EmpireDB/isolated-fixture database name, NOLOGIN migrator
  ownership, forced RLS and collision preflights.
- Restricted erasure audit table, forced RLS, append-only, with one
  generated audit UUID, tenant/property, a separately verified request
  reference fingerprint, reason and deleted row counts. It DOES NOT
  keep the session digest, URL, IP, cookie or email.
- Function `public.empire_analytics_erase_session(uuid,text,text,text,text)`
  performs one exact tenant/property/session operation. It obtains a
  session lock, checks the reason, deletes its event receipts and
  consent decisions first, then its session row, and writes one audit
  entry **in the same transaction**.
- For proposed `EXPIRED_RETENTION`, expiry must be at least seven days
  in the past (this interval is an engineering example, NOT an
  approved legal retention policy). For `VERIFIED_ERASURE_REQUEST`,
  the trusted future operator must verify the erasure request outside
  the function. A caller-supplied SHA256 is NEVER sufficient proof.
- Protected 054 append-only triggers remain enforced for direct
  UPDATE/DELETE by application roles, admin, and migrator. An internal
  maintenance DELETE context requires BOTH an exact authenticated
  future `session_user='empire_analytics_maintenance_login'` AND a
  SECURITY DEFINER function executing as the NOLOGIN migrator.
- Forced-RLS policies permit only the existing migrator to read/lock
  and delete scoped rows and insert audit rows in that guarded context.
  An explicit WITH CHECK(false) UPDATE policy permits row locking but
  does not permit writing updated record versions.
- Migration creates **NO maintenance login**, grants **NO runtime
  EXECUTE**, no table rights, no tenant binding and no public endpoint.
  The maintenance login exists only inside disposable PostgreSQL
  tests, provisioned explicitly by the test fixture *after* migration.
- Cross-tenant references and events remain isolated, and concurrent
  deletion attempts yield one completed erasure, not duplicate proof.

## Verified with REAL PostgreSQL 18

`tests/analytics/test_analytics_erasure_pg18_20261019.py`

Fresh /tmp PostgreSQL 18 cluster, private Unix socket,
`listen_addresses=''`, disposable fixture database only. Tests cover:

- 055 cannot run without correct 054 schema/role boundary.
- No runtime role grants and forced RLS on all four analytics tables.
- Neither direct application login nor admin/migrator can rewrite or
  delete records outside the guarded function.
- Fixture-provisioned maintenance login cannot read/delete raw tables
  and cannot SET ROLE to the migrator.
- A valid future privileged call deletes exactly one scoped session
  plus related consent/event rows, commits the non-identifying audit.
- Tenant mismatch, revoked/expired requests, malformed reasons,
  early retention, session digest as audit reference and double
  erasure all fail closed.
- Atomic concurrent erasure produces one receipt.
- Existing 054 consent/receipt validations remain functional.
- No live PostgreSQL primary connection, DB migration or row mutation.

## Safe preflight (NOW)

    cd /srv/empire_os
    ./.venv/bin/python -m scripts.review_analytics_erasure_preflight_20261019 --read-only

Expected:
`ANALYTICS055_ERASURE_SOURCE_PREPARED_PRIVILEGED_APPROVAL_HELD`

Separate isolated real-DB tests:

    ./.venv/bin/python -m pytest -q \
      tests/analytics/test_analytics_ledger_pg18_20261019.py \
      tests/analytics/test_analytics_erasure_pg18_20261019.py \
      tests/analytics/test_analytics_erasure_preflight_20261019.py

The preflight opens NO production database connection, and the tests
use only their temporary PostgreSQL fixture.

## Remaining critical blockers

1. Approve exact retention periods, subject-request verification,
   exceptions for legal holds, scope/rights for audit records,
   deletion/backup restoration consequences and secure deletion
   timelines. This migration is **not** a privacy-policy certification.
2. Verify Analytics054 has been applied in canonical EmpireDB by a
   privileged, read-only DBA and review exact source/object ownership;
   it is currently only staged, so 055 must **not** be applied yet.
3. Require separate founder/DBA approval for 055, with no unreviewed
   053/055 numbering collision or concurrent owner changes.
4. In an independent, later authority wave: create/bind the dedicated
   maintenance login, verify the actual authenticated operator and
   source of erasure requests, and grant EXECUTE under minimal scope.
   Future role must never inherit/SET ROLE to the migrator.
5. Design bounded expired-session scanning, independent retention job
   cadence, backup deletion/replay and incident audit procedures.
   This wave has an exact one-session eraser, not an automatic timer.
6. ASTRA and founder must explicitly approve public website consent
   UI/event sender and applicable UK privacy requirements. Then
   implement secure server session/token authority, tenant scoping,
   source classifier and first real collector receipts.
7. Keep the founder dashboard metrics labelled **Not connected**
   until independently observed, consent-authorised visitor/session
   aggregates exist. CRM/payment provenance must be independently
   verified before attributed revenue is claimed.

No funds, live outbound, public website edits, systemd restart,
real visitors, cookies, runtime roles, production DB migrations,
or payments are introduced here.
