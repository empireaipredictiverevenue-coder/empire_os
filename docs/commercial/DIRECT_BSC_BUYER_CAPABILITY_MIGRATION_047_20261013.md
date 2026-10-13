# EmpireOS direct-USDT buyer capability — schema release 047
Date: 13 October 2026. **PREPARED ONLY, NOT APPLIED.**

## Why

The current checkout accepts/records a *pending* direct BSC payment request
but has no authenticated follow-up path through which its buyer can retrieve
independently approved payment instructions. A predictable order UUID, payer
wallet or customer email MUST NEVER be sufficient access authority.

The sealed security projection in
`empire_os/direct_bsc_buyer_status.py` already validates a random 256-bit
capability, an HMAC fingerprint, exact buyer/order/request matching, immutable
terms/price/payer, separate human approval and receipt evidence. That module
has NO public route, DB lookup or production key. It is not an activated buyer
retrieval service.

## Proposed migration — exact impact

`migrations/empiredb/047_direct_bsc_buyer_status_capability.sql`

Adds ONLY `public.direct_bsc_buyer_capabilities` with:

- random UUID key; a 64-char HMAC-SHA256 fingerprint, never a raw token;
- FKs to existing canonical fulfilment order and BSC payment request;
- unique one-unrevoked-per-order and one-unrevoked-per-request bindings;
- issue, expiry (strict max 48 h), revocation and created timestamps;
- trigger proof: matching order/request, buyer, DIRECT mode, valid request
  state, order state, issuance after request creation, and capability expiry
  no later than underlying payment request expiry;
- immutable row except first, irreversible revocation;
- RLS ENABLED and FORCED **with zero policies** and no table GRANT;
- guard trigger SECURITY DEFINER owned by empiredb_migrator, blank search
  path, public function EXECUTE revoked. It only rejects unsafe bindings;
  it never reveals buyer data, sends a blockchain transaction or records
  a payment.

**No NOLOGIN role or SQL LOGIN is created.** No public function, web endpoint,
service restart, permission/membership change, wallet operation or payment
flag alteration. Applying this migration alone does not unlock checkout.
No secret key is generated or stored by the migration.

This migration must not be installed without a distinct approval naming
**EmpireDB 047**. Direct-USDT verifier/HBA and RPC deployment approvals are
not permission to apply this change. No production migration has been run.

## Independent test proof — disposable PostgreSQL 18

`scripts/test_direct_bsc_capability_migration_ephemeral.sh` creates an
isolated PG 18 cluster (port != 5432), dummy parent identities, checks the
migrator privileges, executes the exact SQL and verifies:

- table creation, migrator owner, FORCE RLS and deny-by-default;
- no SELECT granted to ordinary `empiredb_app`;
- valid same-order/same-buyer DIRECT request binding;
- cross-order request rejected, duplicate active bearer rejected;
- illegal token modification and repeated revocation rejected;
- test-app granted SELECT **only inside disposable instance** still reads
  zero rows due to forced RLS. No production DB touched.

The Python catalog inspector:
`scripts.inspect_direct_bsc_capability_migration --preflight`
is READ ONLY and verifies canonical EmpireDB, restricted migrator,
parent-table/FK/read permissions and absence of the new table/guard function.

Operator command (READ ONLY):

```bash
cd /srv/empire_os
sudo -n -u postgres ./.venv/bin/python \
  -m scripts.inspect_direct_bsc_capability_migration --preflight
```

Expected safe response:
`READY_FOR_SEPARATELY_APPROVED_CAPABILITY_MIGRATION`.
If HELD, do not apply; inspect role/schema drift before any correction.

## Future follow-up: separately approved access

After schema installation, design and independently verify an exact
capability issuer and a dedicated status reader limited to one fingerprint.
Never grant a public gateway, checkout app login or customer a broad SELECT
on global payment tables. Enforce atomic issuance and idempotent retries,
prevent leaking the bearer token in URL, logs and analytics, source it from
a protected first-party server key, keep expiry/revocation and implement a
recovery process through the founder-controlled mailbox.

Only after that, add a same-origin no-store rate-limited POST status endpoint,
buyer UI refresh, honest prices/terms, secure human operator assignment,
transaction replay/reorg checks, and separately authorised controlled service
restarts with rollback proof.

**Money stays OFF until the entire approved buyer payment flow is verified.**


## 13 October 2026 — production migrator preflight held

Founder-read-only production output from
`scripts.inspect_direct_bsc_capability_migration --preflight`:

- canonical DB, both payment/order parent tables, FK + SELECT permissions:
  **PASS**
- proposed capability table and trigger function absent: **PASS**
- migrator exact NOLOGIN/NOINHERIT/no-privileged-attributes check: **HELD**
- result: `HELD_SCHEMA_OR_AUTHORITY_DRIFT`; **047 NOT APPLIED**.

The exact mismatched role attribute was not disclosed by the original
inspector. Source-only diagnostic enhancement now returns
`migrator_attributes` and `migrator_mismatched_flags` from pg_catalog, with
READ ONLY transaction, no credentials, no role writes, no changes to the
original seven-flag acceptance rule. A non-inheriting NOLOGIN migrator is the
*expected* profile, not an observed production fact. Don't assume that
`rolinherit=true` is the only mismatch without a new catalog read.

**Do not ALTER ROLE, GRANT, REVOKE or run migration 047** to make the
preflight green. Review the actual attribute(s), existing deliberate
migration authority, dependent role memberships and separate founder
approval before any remediation or migration.


## 13 October 2026 — production membership audited; exact-profile correction

The founder supplied the read-only production pg_catalog result:

- `empiredb_migrator`: NOLOGIN, INHERIT TRUE, NOSUPERUSER,
  NOCREATEDB, NOCREATEROLE, NOBYPASSRLS.
- **Exactly one direct role membership**:
  `empiredb_tenant_reader`; INHERIT TRUE, SET TRUE, ADMIN FALSE;
  inherited privileges YES. No other direct memberships.
- Do not modify or revoke this existing intentional membership. It is not
  evidence of compromise and may support unrelated EmpireDB operations.

The original 047 preflight mistakenly assumed NOINHERIT for the migrator.
The revised **v2 read-only preflight** enforces the actually audited profile
instead: migrator INHERIT TRUE + EXACTLY one inherited
`empiredb_tenant_reader` membership with exact per-membership options,
restricted NOLOGIN/NOINHERIT tenant reader and **zero** memberships owned
by that tenant reader. Extra direct or transitive groups fail closed.
All previous canonical DB, FK/source privilege and object-absence checks
remain mandatory.

The proposed 047 SQL now repeats the same profile and membership checks
*inside the migration transaction*, preventing a stale preflight from allowing
unexpected later role grants.

Independent verification:
- Python tests including additional arbitrary-role, inherited financial
  role, admin-option, privilege-escalation and missing-role negative tests.
- In a disposable PostgreSQL 18 instance: intentionally add a second
  finance-role membership -> **exact migration aborts, table absent**;
  remove the test-only role membership -> exact migration succeeds.
- Existing cross-order, replay, revocation, force-RLS tests remain PASS.
- Production 5432 NOT accessed by those migration tests.
- Still NO PRODUCTION MIGRATION, NO LOGIN GRANTS, NO LIVE PAYMENT.

Run the revised, **read-only** v2 preflight as `postgres` before any
separately approved production migration. Its result may still be HELD
if the tenant reader has unknown attribute/role drift not visible in the
founder's first output. Do not silently bypass such a gate.
