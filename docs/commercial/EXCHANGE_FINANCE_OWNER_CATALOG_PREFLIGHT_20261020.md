# Exchange Seats — Finance/DBA read-only catalog gate (20 October 2026)

## Purpose and current boundary

The Exchange seat build has a dedicated bounded owner-read adapter and a **draft**, never-applied native monthly membership+invoice-cycle schema. The actual EmpireDB financial roles and catalog may have drifted from the repository migration history. A privileged **read-only** catalog check is required before anyone can claim role/table readiness or approve a new owner LOGIN.

Remote orchestration cannot execute the privileged DBA catalog query under its current command permissions. **Do not bypass that restriction or substitute the application role or a legacy database.** This is an owner handoff, not evidence that the live check ran.

## Safe local operator step

Only the already-authorised EmpireDB DBA, using their existing approved privileged session, may run:

```bash
cd /home/ubuntu/empire_worktrees/exchange_fulfilment_mrr_review_20261020
sudo -n -u postgres psql -X -qAt -v ON_ERROR_STOP=1 -d empiredb \
  -f docs/commercial/sql/EXCHANGE_NATIVE_SEAT_ROLE_PREFLIGHT_READONLY_20261020.sql
```

The script begins `BEGIN TRANSACTION READ ONLY` with a 5-second statement timeout, looks up only `pg_catalog`/schema metadata, returns a single JSON report containing booleans and possibly names of missing **columns**, and finishes with `ROLLBACK`. It never reads application or transaction rows, financial values, wallet addresses, contact details or secrets.

The outputs `finance_role_reader_grants_proven`, `tenant_rls_identity_proven`, `settlement_authenticated`, `entitlement_activation_authorized` and `schema_migration_authorized` are **always false by design**. Do not upgrade them based on matching column names or presence of old roles.

A role visible in `pg_roles` is not proof that it is the correctly authenticated dedicated finance-reader LOGIN/NOLOGIN with safe grants, inherited privileges, RLS tenant boundaries, secrets custody and correct service transport. Separate non-mutating role grant and session login checks must be created and reviewed by the existing DBA owner.

## Schema draft tightened

`docs/commercial/sql/EXCHANGE_NATIVE_SEAT_TABLES_REVIEW_ONLY_NOT_APPROVED.sql` now requires a composite `(membership_id,tenant_id,buyer_id)` foreign key to stop invoice cycles from referring to one member while claiming another tenant/buyer. It continues to require:

- unique `(membership_id,period_index)`, unique source invoice/order and BSC payment request/evidence IDs, and immutable authenticated finance proof before any paid claim;
- default PROPOSED/PENDING, RLS ENABLE and FORCE, no policies, no app or PUBLIC table grants;
- no actual new owner roles, public API, entitlement writer, payment movement, MRR accounting or customer lead delivery;
- separate tenant/buyer RLS proof and transactional buyer `org_id` binding **not provided** by the composite FK;
- fresh DBA catalog comparison, working backup, dry-run SQL fixture and explicit founder/DBA migration approval before any execution.

## Safe engineering result

Static SQL boundaries + synthetic owner-reader tests pass. This is not a live SQL parse/DDL execution or production permission audit. Branch remains isolated from shared dirty `/srv/empire_os`.

Next implementation after the DBA report: design a transactionally idempotent and independently authorised native Exchange seat renewal writer, with accepted commercial terms, independently reconciled BSC USDT per-cycle settlement and cancellation/reversal journal. Do not assume automatic wallet renewal or claim billable recurring MRR until real finance and entitlement receipts exist.

The existing A2A public-source research and Buyer Scout continue independently; no Brave Search API results should enter persisted Exchange inventory without rights.
