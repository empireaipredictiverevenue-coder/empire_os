# TAM 043 — Stage 1 production preflight record (10 October 2026)

## Authority boundary

The founder approved **stage 1 only** in continuation of the explicitly proposed isolated-TAM database installation. That covers the prepared NOLOGIN roles and isolated RPC **only after live schema and verified current backup prerequisites pass**. It does **not** cover credential provisioning, switching LOGIN on, installing or starting the systemd unit, a canonical TAM market read, migrations beyond the approved 043, or outbound/payment activities.

## What was actually verifiable from this remote session

- Code pinned: commit `63f6699b`, with both held production SQL files SHA-256 and Git object identity matching the reviewed release.
- Server PostgreSQL service: `postgresql@18-main.service` active at time of inspection; this is not equivalent to authenticated DBA catalog proof or a verified backup.
- Canonical release SQL and rollback: executable disposable PostgreSQL gauntlet passed (177 tests before this stage).
- **Production DBA read-only catalog check:** not executed. The remote command provider rejected privileged PostgreSQL inspection with `Command not allowed`. No attempt was made to bypass its security policy.
- **Backup freshness, capacity and integrity:** not verified. The current session cannot read `/etc/pgbackrest/pgbackrest.conf` or the protected `/var/backups/empiredb/pgbackrest`. The existence of old CRM backup directories does not satisfy a fresh stage-1 backup requirement.
- **Production roles and RPC:** no DDL applied in this continuation. The proposed new service remains not found/inactive and the canonical TAM snapshot remains absent.

## New executable read-only preflight

`scripts/preflight_empiredb_tam043_stage1.sql` is a read-only transaction with a 5-second statement timeout and a final ROLLBACK. It verifies:

1. Canonical `empiredb` primary, expected nonlogin migrator, existing legacy materializer and app roles.
2. No colliding isolated TAM roles or `get_tam_market_observations(integer)` function.
3. The original materializer still has its two required SELECT grants (protect Market GPS).
4. All 12 source-table columns and their PostgreSQL types needed by migration 043 match the real canonical schema.
5. No source table rows or prospective company information are queried, and no roles/objects are changed.

Five tests in `tests/test_empiredb_tam043_stage1_preflight.py` passed in a disposable PostgreSQL cluster. Negative cases prove that collisions, missing columns, wrong column types and revoked legacy grants stop the release.

## Single authorised-DBA unblock

An operator who already has authorised canonical PostgreSQL access can execute **one read-only preflight**:

```bash
cd /srv/empire_os &&
sudo -n -u postgres psql -X -w -v ON_ERROR_STOP=1 -d empiredb   -f scripts/preflight_empiredb_tam043_stage1.sql
```

**This command was not executed by ChatGPT** because the remote command policy denied DBA access. A passing message from this query still **does not** authorise applying stage 1 before a fresh SHA-256-verified backup of the database and global roles, database-instance identity check, adequate disk and a recovery plan have been verified by the authorised DBA. Follow the existing `scripts/deploy_empiredb_crm042.sh` backup standard; never run that CRM deployment script for TAM.

Only after these prerequisites can the authorised DBA apply the already prepared `deploy/empiredb/tam_isolated_roles_bootstrap.sql` and `migrations/empiredb/043_tam_isolated_restricted_reader.sql` under the exact released hashes, with a post-deployment catalog proof and legacy Market GPS comparison. Keep both new identities NOLOGIN and PASSWORD NULL.

The held rollback is at `deploy/empiredb/tam_isolated_rollback_held.sql` and must not be auto-run after a partial release. If the role bootstrap succeeded but the function migration failed, the account is still dormant; inspect before any retry.

**Status: approved stage 1, blocked before production DDL by unavailable DBA preflight and backup evidence.**
