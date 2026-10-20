# Empire AI — Founder-tenant order reader: production provisioning

20 October 2026 — Existing canonical EmpireDB / original owner contract.

## Verified production state

The user's founder direction authorised a **single existing Empire AI tenant** reader, not a customer, buyer or newly invented tenant.

- Existing authenticated founder-owner membership: **one** original verified owner.
- Existing source tenant active bindings at preflight: **four**, with owner evidence.
- Before any migration: zero fulfilment orders, zero payment evidence, zero commercial outcomes, zero escrow evidence. 9053 historical commercial events are NOT 9053 sales.
- Root-protected schema recovery snapshot at `/var/backups/empiredb/order056/pre_order056_schema_20261020.sql` (mode 0600), created before applying SQL.
- Applied pre-reviewed `migrations/empiredb/056_verified_order_tenant_reader_select_held.sql` to real canonical `empiredb`. The readback proved exactly five extra row-level SELECT policies and five SELECT grants to existing NOLOGIN role `empiredb_tenant_reader`. No production rows were created or modified by this migration.
- Provisioned exactly one founder-tenant LOGIN: `empire_verified_order_tenant_login`, with `NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION`. The only membership added is `empiredb_tenant_reader` with PostgreSQL `INHERIT FALSE, SET TRUE, ADMIN FALSE`. Its binding is to the existing authenticated founder tenant in `empire_tenant_role_bindings`.
- PostgreSQL database-level CONNECT privilege was missing despite the role existing. Added **CONNECT only** to this dedicated login; no CREATE privileges were granted.
- The login uses the existing PostgreSQL localhost/127.0.0.1 SCRAM authentication. No `pg_hba.conf` changes, new public DB port, reload or restart.
- SCRAM credential is root-only in `/etc/empire/verified-order-reader/reader.pgpass`, directory mode 0700 and file mode 0600. The credential is not in Git, user-facing reports, CLI argv or logs.

## Evidence tests

Before deployment, 42 focused unit tests passed for the one-login provisioner, original exact-order operator and tenant RLS guard.

The SQL 056 policies had already passed disposable PostgreSQL 18 two-tenant isolation tests: each login could see only its own synthetic orders and direct/escrow records; revoking one tenant binding eliminated visibility. Real Python provider/transaction integration with the same temporary PostgreSQL also passed.

**Real canonical EmpireDB** post-provision test used `_canonical_read_only_repository()` with root-only `PGPASSFILE` and a private loopback DSN. It proved correct tenant, restricted role, read-only transaction, all eight relation SELECT/RLS conditions, and successful bounded reads of original finance tables. It denied a different tenant ID. All six probed categories had zero records as expected; no fake production rows were seeded.

## Safe use after a genuine fulfilment order exists

The existing exact-order command remains read-only and explicit-order only. An authenticated original owner must obtain a legitimate canonical order ID from its own first-party transaction record. Run through a root-only environment without exposing login credentials:

```bash
sudo -n env \
  PGPASSFILE=/etc/empire/verified-order-reader/reader.pgpass \
  EMPIRE_COMMERCIAL_OUTCOME_TENANT_DSN='host=127.0.0.1 port=5432 dbname=empiredb user=empire_verified_order_tenant_login' \
  PYTHONPATH=/srv/empire_os \
  /srv/empire_os/.venv/bin/python -B -m scripts.review_verified_commercial_order_20261020 \
  --read-only --tenant-id "${AUTHENTICATED_FOUNDER_TENANT_UUID}" \
  --order-id "${ORIGINAL_VERIFIED_ORDER_UUID}"
```

This command is **NOT** evidence that a purchase has occurred until original source returns independently verified terms, fulfilment, payment and actual cost. Revenue learning and model mutation remain separate owner-gated tasks. Do not run with guessed IDs. Never print the secret or order/customer identifying content into shared logs.

## Recovery and key management

- Root-only pre-provision schema snapshot above. Proposed DBA rollback SQL is `migrations/empiredb/056_verified_order_tenant_reader_rollback_dba_only.sql` and **must not** be run without operational review.
- To de-authorise this one login urgently, original owner/DBA can deactivate the exact role-to-tenant binding, revoke group membership/CONNECT, and subsequently rotate/disable the login. This is a separate approved operation, not automatically performed.
- Provisioner: `scripts/provision_verified_order_tenant_login_20261020.py` with `--preflight` and explicit `--apply-founder-approved-one-tenant-login`. Preflight is intentionally HELD after successful one-time provisioning; do not create a second login.
- Existing Ops Control remains observe-only. No new scheduler or agent, no outbound actions, payments, model training, settlement generation or buyer promotion was performed.

## Remaining commercial blocker

**There is no real canonical fulfilment order, recognised payment receipt, commercial outcome or realised gross profit in the database to reconcile.** The next commercial step is to acquire a real authorised buyer transaction through the existing checkout/CRM/sales owner flows. Only after that event can exact order/settlement/cost proofs drive real calibration. Never invent a sale to clear the learning gate.
