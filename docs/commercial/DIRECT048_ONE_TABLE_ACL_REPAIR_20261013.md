# EmpireDB 048 — Restore the sealed capability ACL after committed 047
Date: 13 October 2026 · **PREPARED, NOT APPLIED**

## Production evidence — reproduced exactly in disposable PostgreSQL

047 installation reported verified backup, SQL COMMITTED, then exit 5 for
POSTCOMMIT_PRIVILEGE_DRIFT_DO_NOT_RETRY. The **separately run read-only
postcommit inspector** proved table, forced RLS, zero policies, trigger
and function owner/public-execute protection PASS; check 03 for
`empiredb_app` SELECT FAIL.

Actual table ACLs revealed:
- `empiredb_app`: SELECT, INSERT, UPDATE, DELETE.
- `empiredb_readonly`: SELECT.
- Owner `empiredb_migrator`: its owner privileges.

Reason: previously configured
`ALTER DEFAULT PRIVILEGES FOR ROLE empiredb_migrator IN SCHEMA public`
automatically grants those five privileges on newly created tables.
047's explicit `REVOKE ... FROM PUBLIC` did not remove grants to named roles.

Because FORCE RLS is active and there are **zero RLS policies**, there
is another deny-by-default barrier for normal app and readonly access.
However, unwanted ACLs violate the sealed-table invariant and need
separate remediation. Do not assert all security checks passed or that
there was a verified data exposure.

## Proposed change — strictly one table

`migrations/empiredb/048_direct_bsc_buyer_capability_acl_seal.sql`

- Refuses wrong DB, wrong migrator, absent 047 objects, incorrect
  RLS/ownership/trigger/function, unexpected table grants, grant options
  and unexpected role ACL entries **before any REVOKE**.
- Transactionally `REVOKE ALL PRIVILEGES ON TABLE
  public.direct_bsc_buyer_capabilities FROM empiredb_app, empiredb_readonly`.
- Verifies only owner privileges remain, zero policies, forced RLS still
  active, and both restricted roles denied table privileges.
- Does NOT modify PostgreSQL `ALTER DEFAULT PRIVILEGES`, other tables,
  existing roles, functions, service configuration, checkout, buyer
  records, payment switches, RPC, blockchain or money.
- Refuses repeated application; if COMMITTED but postcheck fails, STOP
  and inspect read-only, do not rerun blindly.

## Independently verified proof

`scripts/test_empiredb_direct_bsc_capability_acl_048_ephemeral.sh`
runs only in disposable PostgreSQL 18 on a nonproduction port.
Creates the same migrator default grants, executes exact 047 SQL,
confirms failed application SELECT check, adds an unexpected third-party
grant to prove 048 aborts atomically, removes that test-only grant,
executes exact 048 SQL, confirms all nine postcommit checks PASS, checks
DEFAULT PRIVILEGES unchanged and verifies the second 048 execution
is blocked.

Python/shell/regression gauntlet: **131 passed**, one existing Starlette
DeprecationWarning; disposable PostgreSQL replay/ACL/RLS suite PASS.

## Exact release operator — approval is still missing

`scripts/deploy_empiredb_direct_bsc_buyer_acl_048.sh`:

- Requires exact **separate founder approval** for 048, and privileged
  terminal execution with its single-use approval flag.
- Checks committed source blobs, canonical DB instance matching the
  production application, actual checkout payment flags OFF,
  original 047 backup hash and exactly 8/9 expected current checks.
- Creates a **new** root-protected, checksum-verified production archive
  of the database AFTER 047 and BEFORE 048, plus globals and restore list.
  No full restore rehearsal is claimed.
- Executes only the exact 048 transaction and performs independent
  **all-nine** security readback and separate readonly-role denial.
- Checks checkout financial flags still OFF; no service restarts.

The user has previously approved migration 047 only. That does not
extend to 048 or general production ACL/security modifications.
**DO NOT run 048 until the founder explicitly approves exactly this
one-table privilege removal.**

## After 048, only if independently verified

The new capability table will be SEALED, not usable by customer checkout,
because it has no RLS policies and no application role grants. Separate
issuer, private reader, secure token transport, real status endpoint,
customer UI and transaction reconciliation remain future gated work.
Nothing should be presented as payment-ready or revenue recognised.
