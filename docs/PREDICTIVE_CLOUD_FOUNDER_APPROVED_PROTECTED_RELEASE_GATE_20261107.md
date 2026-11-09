# Founder-approved Data Intelligence release gate — 2026-11-07

## Founder decision
Founder has **approved** the protected EmpireDB migration and gateway activation only when SQL/ownership, fresh backup and independently tested rollback, founder-only access, spending caps, and one real live canary pass. No further approval for this unchanged objective is being requested.

## Independently observed live evidence
- Production EmpireDB PostgreSQL 18.6, service healthy.
- Canonical `empire_data_cloud_api` schema: absent.
- Dedicated `empire_data_cloud_meter_login`: absent.
- Active Search Intelligence `/v1/search/health`: HTTP 200.
- Production `/v1/data/usage`: HTTP 404.
- Existing public gateway, Revenue CRM pilot and Search Intelligence services: active.
- Protected root gateway code is dirty in `hub.py`, `public_gateway.py`, `search_fabric/search.py`, `search_intelligence/api.py`; no root modifications here.

## Private engineering completed
- Existing feature branch `feature/predictive-cloud-founder-session-20261107`, commits `441ac8b3d`, `b74175ef8`, `a895fe5e9`.
- Separate verified Data Cloud founder token issuer and public-key verifier; no separate account system.
- Guarded route assembly and source-archive provenance check. Private suite 79 tests pass; prior isolated PostgreSQL suite passed real concurrency/quotas/isolation.
- Isolated PostgreSQL 18 rollback rehearsal **PASS**, strictly checked disposable PG data directory and Unix socket. Removed `empire_data_cloud_api` and `empire_data_cloud_meter_login` in disposable PostgreSQL; both absent after. Test instance stopped. Rollback rehearsal SHA256 `099a1b2633cf0b51cf290907db24279ec4ca119a993bd2dfa517fab77d826289`.

### 7 November incremental SQL security hardening (review-only)
- An independent SQL review identified that the original candidate's SECURITY DEFINER functions would be created by the bootstrap superuser and that successful settlement could be recorded with no cost evidence. Both have been corrected in the **review-only** exact-source hardened candidate; it has **not** been run against production.
- The hardened SQL creates `empire_data_cloud_api_owner` and `empire_data_cloud_meter_login` as **NOLOGIN, NOSUPERUSER, NOBYPASSRLS** roles, transfers the four SECURITY DEFINER functions and their tables/schema to the restricted owner, and grants the metering role only schema usage and audited EXECUTE.
- Site-audit reservations now require an explicit allowlisted host; null operation/state and evidence-free settlement fail closed. No independent monetary cost evidence can be inferred from synthetic test references.
- Pinned review-only SQL: `docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql`, SHA256 `d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393`. Original source SHA256 `f302ad611e93b5f1bdaad40a09cba53c1652c7abe1399a1255ac54d7bdc078e9`. Any drift fails before generation.
- Isolated PostgreSQL 18.6 real DDL + concurrent metering acceptance **PASS**, including 3 permitted and 17 rejected concurrent reservations, no direct table SELECT, cost-integrity hold and key/host checks.
- Hardened isolated rollback **PASS**: schema, metering role, owner role removed; disposable server stopped. Production PostgreSQL untouched.
- Current private auth/route/CRM/SQL source test suite **82/82 PASS**; independent DBA approval of this *new exact SQL* and secure production LOGIN activation/credential custody remain REQUIRED.

## Actual production recovery evidence
- Existing pgBackRest stanza `empiredb`, config `/etc/pgbackrest/empiredb.conf`, encrypted repo, health `ok`.
- Last listed full backup 16 October 2026, differential 20 October 2026. The pgBackRest archive `check` successfully pushed a WAL segment on 7 November 2026; pg_stat_archiver showed zero failures.
- **Fresh encrypted backup was NOT executed**. Connector explicitly returned **Command not allowed** to privileged `pgbackrest backup`. Do not bypass the connector guard, switch transports, or count the old backup as fresh.
- **Independent restore from a fresh pre-release backup NOT VERIFIED**. Prior separate October off-node restore is historical only.
- No production SQL, role, credentials, provider calls, email or gateway restart were performed.

## Fail-closed decision
**HOLD_RECOVERY_PRIVILEGE_AND_FRESH_RESTORE_UNVERIFIED**

Authorised protected release operator must (1) obtain an existing-owner sanctioned backup and fresh independent restore receipt through the installed backup workflow, (2) reconcile ownership/dirty gateway release paths and acquire its existing exclusive mutation lease, (3) review SQL and least-privilege SECURITY DEFINER ownership (do not introduce superuser function ownership without a specific DBA review), (4) verify dedicated founder entitlement and trusted issuer key custody, (5) stage original byte-pinned customer API and canonical principal adapter, (6) apply DB migration only with approved transaction and rollback controls, (7) activate the guarded customer route in the existing owning gateway and perform one cost-capped founder-authenticated live canary, (8) inspect runtime rollback and 401/403/409/429/503 fail-closed results.

Customer access, unlicensed third-party data reuse, paid provider requests and billing remain OFF.

## Exact source proofs
- `/home/ubuntu/empire_worktrees/predictive_cloud_founder_session_20261107`
- `/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107/candidate.sql` SHA256 `f302ad611e93b5f1bdaad40a09cba53c1652c7abe1399a1255ac54d7bdc078e9`
- `/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107/rollback_rehearsal.py`
