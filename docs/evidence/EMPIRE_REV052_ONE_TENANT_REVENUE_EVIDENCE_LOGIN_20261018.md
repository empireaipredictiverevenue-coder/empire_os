# EmpireDB REV052 — one founder-approved restricted revenue evidence login

**18 October 2026 | Existing canonical EmpireDB | PREPARED, NOT YET EXECUTED IN PRODUCTION**

## Approval and exact scope

The founder approved **one distinct, tenant-bound, read-only login**
for the original REV051 revenue-event evidence capability. This is separate
from the earlier approved and live NOLOGIN role/function, and deliberately
does **not** reuse existing CRM, intelligence-materializer, payments or
customer account login credentials.

Prepared local operator:
`scripts/provision_revenue_event_evidence_login_20261018.py`

One login:
`empire_predictive_revenue_evidence_login`

Only capability:
`empire_predictive_revenue_evidence_reader`

Only trusted existing founder tenant:
`708efd4b-53b2-43d7-961d-1cecab67f17a`

The operator refuses live changes unless the canonical PostgreSQL 18 primary,
previously installed REV051 function/role, existing active CRM founder
owner membership, existing evidenced tenant binding, original source-table
existence, clean HBA parse, active pgBackRest backup no older than seven days
and matching live WAL archive command are all verified first. The active repo
is the existing encrypted POSIX `/etc/pgbackrest/empiredb.conf` stanza
`empiredb`; it does not create or mutate backups.

The exact local first-match HBA change is only:

```text
local empiredb empire_predictive_revenue_evidence_login scram-sha-256
```

The operator stores a byte-for-byte copy of the old HBA privately under
`/var/backups/empiredb/rev052-one-reader-hba`, inserts only the prefixed
new line, and **reloads, never restarts** PostgreSQL. Existing CRM/outbound
HBA rules remain byte-identical. No public network listener, HTTP endpoint
or tunnel is enabled.

The new login is `NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
NOREPLICATION NOBYPASSRLS`. It receives `CONNECT` on EmpireDB and
membership with `INHERIT FALSE, SET TRUE, ADMIN FALSE` in exactly the
already-verified REV051 capability role. The only tenant mutation is one
active, explicitly evidenced `empire_tenant_role_bindings` row for this
login, inside the same PostgreSQL transaction as the role/grant creation.
The trusted tenant resolver continues to use the authenticated
`session_user`. Direct SELECT and writes to buyers, orders and original
commercial-events tables remain denied. The login is not a financial
operator or a customer account.

A fresh strong password is generated **on the server** with
`secrets.token_urlsafe(48)`, converted to a SCRAM-SHA-256 verifier using the
existing first-party CRM helper, and submitted as a derived verifier to
PostgreSQL over a local peer-admin stdin transaction. The server-side
credential stays inside `/etc/empire/revenue-event-evidence/reader.pgpass`
(root-only 0700 directory and 0600 file), never printed to terminals or
ChatGPT, never carried in process arguments, repository commits, or ordinary
environment variables. Production account login does not share the
founder's CRM password. Do **not** paste the password or the .pgpass file.

If PostgreSQL refuses the transaction, the operator restores HBA if its
exact prefixed version remains unchanged and destroys the unused credential.
If transaction commits but subsequent authentication fails, it stops with
`HOLD_OR_UNVERIFIED_NO_BLIND_RETRY` and preserves credential/active HBA
for reconciliation; **never blindly rerun the mutating command**.

## Source-level verification

Existing `public.empire_current_tenant_id()` remains private. REV052
does not grant direct EXECUTE on it: the installed restricted
`SECURITY DEFINER` event function invokes it internally. Authenticated
readback checks PostgreSQL `session_user/current_user`, no raw source
table privileges, `SET LOCAL ROLE`, and successful bounded function
execution with one intentionally absent UUID. This is **NOT** a genuine
financial event; it exercises zero-output permission behaviour only.
Independent root-admin readback verifies exactly one active tenant binding
with evidence_ref. No customer financial rows/amounts are returned.

Isolated actual PostgreSQL 18 test:
`scripts/test_revenue_event_evidence_login_20261018_ephemeral.sh`
operates on a disposable private Unix socket cluster with entirely
**synthetic** order, buyer, recognised-event and tenant records. It
verified exact new-role SCRAM authentication, rejection of incorrect
password, founder-bound own single-event match, denied cross-tenant event,
and denied direct ledger SELECT. All fixture data and roles are removed
after the test; production database/services were not changed.

## Run the already approved scope in an authorised local EmpireOS terminal

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.provision_revenue_event_evidence_login_20261018 --preflight &&
sudo ./.venv/bin/python -B -m scripts.provision_revenue_event_evidence_login_20261018 --apply-approved-one-tenant-login
```

Do not run this before the reviewed source is committed to the canonical
branch. A successful final result is:

```text
REV052_TENANT_BOUND_AUTHENTICATED_FUNCTION_PROOF=PASS
REV052_PRIVATE_CREDENTIAL_SERVER_ONLY=YES
REV052_REVENUE_EVENT_FETCHED=NO
REV052_FINANCIAL_WRITE_AUTHORITY=NO
REV052_STATUS=ONE_RESTRICTED_EVIDENCE_LOGIN_VERIFIED
```

If the preflight returns a HOLD, no DDL/HBA edits have occurred. If the
apply step returns HOLD following a transaction commit, do not retry until
the exact state is reconciled and credentials confirmed safe.

## What remains after one successful login

One authorised, legitimately **pre-existing** `revenue_recognized` event
identifier can then be retrieved *only through the authenticated bounded
tenant function*, with a separately reviewed source event ID and report
scope. The absence of events is unknown, not evidence of zero revenue.
This does **not** prove complete daily totals, finalised BSC settlement/
refunds, payment receipts, independently observed buyers, a customer
release, or any realised revenue amount. No live cash, outbound, mail,
paid tools, business terms or public applications are activated.
