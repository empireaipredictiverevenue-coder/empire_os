# Revenue Recovery — EmpireDB native 057 (held release)

**20 October 2026 — Prepared, NOT applied to production.**

Empire AI's canonical database is **EmpireDB PostgreSQL**, not Supabase. Earlier files under supabase/migrations/2026102012450* are historical offline proposals, NOT authorised to deploy. They mention Supabase auth.users/anon/authenticated and are incompatible with the production native CRM identity. Do not execute them.

## Canonical database replacement

Held native schema:

migrations/empiredb/057_inbound_recovery_native_schema_held.sql

Reuses **public.empire_crm_tenant_memberships** and its trusted public.empire_crm_read_member(text,uuid) authority. No separate customer membership database or login. All tenant keys are native UUID and every calendar FKey is tenant-prefixed.

- Ten pre-existing-name inbound evidence/consent/calendar tables are created ONLY if they do not already exist; conflicting pre-existing objects abort transaction without reconciliation.
- Every table has ENABLE ROW LEVEL SECURITY AND FORCE ROW LEVEL SECURITY; **zero policies**, no grants except role ownership; all public access explicitly revoked.
- Native, privileged DBA migration owner empiredb_migrator is required. Existing CRM tenant resolver and membership authority must exist and be RLS enabled.
- Suppression and lifecycle defaults fail closed. No tenant rows, callback sends, bookings, payments, role membership, API exposure, live RLS access or service deployment are created.
- A paid invoice row requires non-synthetic and verified evidence; no row proves revenue absent authoritative payment reconciliation.

## Actual PostgreSQL validation

Run **only** the disposal-bounded fixture (never production DB):

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m scripts.verify_inbound_native_schema_ephemeral_20261020 --ephemeral-only

This command starts a new PostgreSQL 18 instance in an owner-private disposable directory, with TCP disabled and its own Unix socket. It creates fake CRM authority, applies SQL only inside inbound_recovery_057_fixture, verifies ten FORCE RLS tables, attempts unauthorised app-role queries, and tests composite tenant/calendar FKs. It stops and deletes the fixture cluster. The production server/database is never contacted.

Observed test result (20 October 2026): PASS, native_tables_force_rls=10, app_role_denials=2, cross_tenant_calendar_keys=verified, production_database_changed=false.

Regression test: tests/test_inbound_native_empiredb_migration_057.py (five tests, including the real disposable PostgreSQL runner). Whole inbound suite should also pass in this isolated feature worktree.

## Production holds

Do NOT apply 057 yet. Before any permanent DB change, canonical DBA must first:
1. Inspect the exact current EmpireDB schema and migration numbering, role attributes and existing memberships.
2. Verify tested backups, restore/PITR, lock waits, migration ownership and explicit migration approval.
3. Rehearse the exact SQL + role checks in a separate fixture with production-representative roles; test cross-tenant read/write denial and identity-coupled authority.
4. Confirm production database release and observability ownership, privacy/retention plan, rollback window, and least-privilege writer role provision.
5. Keep OAuth, live callbacks, marketing, money movement and agent dispatch disabled until their separately approved gates.

**None of this grants migration, outbound, finance, contact, or Google OAuth authority.**
