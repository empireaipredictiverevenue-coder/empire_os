# EmpireOS Verified Orders — tenant-scoped transaction access

20 October 2026 — isolated integration branch:
`feature/verified-order-tenant-access-20261020`

## Engineering status

- The canonical verified-order reader is already committed in production.
- The manual original-order operator previously accepted the broad `EMPIREDB_DSN`. A read-only transaction alone is not proof of customer-specific read authority. That access gap is addressed in this increment.
- `empire_os/commercial_order_tenant_session.py` verifies the real login is nonprivileged, member of `empiredb_tenant_reader`, uses the existing read-only transaction, and has a matching trusted session-user tenant binding.
- Before order or payment data is read, it executes a fixed `SET LOCAL ROLE empiredb_tenant_reader` and verifies read-only mode, eight table SELECT grants, and active table RLS.
- `scripts/review_verified_commercial_order_20261020.py` now accepts only a separate dedicated `EMPIRE_COMMERCIAL_OUTCOME_TENANT_DSN` connection configured by the existing tenant owner. It never uses the global application `EMPIREDB_DSN` for this workflow.
- The operator does not discover tenants, enumerate orders, send messages, write to the database, change financial recognition or train models.

## Actual database catalogue facts (read-only)

The production EmpireDB catalogue showed:
- The `empiredb_tenant_reader` NOLOGIN role exists, and four active tenant role bindings are recorded.
- There were **zero role memberships to individual tenant LOGINs**, so no permitted per-tenant session for this operator yet.
- SELECT was already granted for buyers, fulfilment orders and commercial events, but was absent for commercial outcomes, payment requests/evidence and escrow agreements/evidence.
- Those five tables have RLS enabled; adding unrestricted SELECT without exact tenant policies would be unsafe.

## Permission design held for separate activation

`migrations/empiredb/056_verified_order_tenant_reader_select_held.sql` is a **prepared, NOT APPLIED** migration. It grants SELECT only to the NOLOGIN tenant reader role and establishes five RLS SELECT policies. Each nested payment/escrow row must resolve through a real canonical order/buyer owned by `public.empire_current_tenant_id()`; orphan rows are invisible. No tenant account, binding, payout, or writer role is created.

The migration was tested in a throw-away PostgreSQL 18 cluster using synthetic tenant A/B logins, orders, direct payments and escrow records. The test checks both tenants can see only their own rows, sees none after an active tenant binding is revoked, and can read through the actual Python `_canonical_read_only_repository` transaction with the intended role and permissions.

A production rollout of SQL 056 requires existing DBA/identity-owner approval, a reviewed tenant-specific LOGIN and session binding, privileged recovery checkpoint and equivalent production privileges audit. Do not reuse `empiredb_app`, `empiredb_readonly`, postgres or a superuser as the tenant reader.

## Validation & deployment boundary

Run:

```bash
cd /home/ubuntu/empire_worktrees/verified_order_tenant_access_20261020
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_commercial_order_tenant_session.py \
  tests/test_verified_commercial_order_operator.py

pg_virtualenv -v 18 bash scripts/test_verified_order_tenant_056_ephemeral.sh
```

All synthetic passwords and UUIDs in test fixtures are disposable; no real buyer, transaction or private credential is introduced to production.

On release of Python-only hardening, the existing Ops timer and Founder status remain running as before; the manual order operator stays fail-closed until the dedicated login and ACL are approved and provisioned. Real payments, recognised revenue and profits remain UNKNOWN until independently verified original orders can be read.
