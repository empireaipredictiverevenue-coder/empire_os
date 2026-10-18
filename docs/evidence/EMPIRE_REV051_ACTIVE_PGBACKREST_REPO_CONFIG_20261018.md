# EmpireDB REV051 — active encrypted repository path correction

**18 October 2026 · Canonical pgBackRest v58 architecture reused · no DDL**

The founder's latest strictly read-only REV051 backup inspection returned
`stanza_count:0, reason:NO_HEALTHY_BACKUP_STANZA`, and therefore the `&&`
operator prevented REV051 DDL entirely.

This was **not authoritative evidence that the live EmpireDB physical backup
is missing**. We traced it to the earlier script probing pgBackRest's
**default** configuration. The existing EmpireDB disaster-recovery programme
already proved on 16 October that PostgreSQL's live archive command is

```
/usr/bin/pgbackrest --config=/etc/pgbackrest/empiredb.conf --stanza=empiredb archive-push %p
```

This exact configuration uses a local POSIX repository at
`/var/backups/empiredb/pgbackrest`, AES-256-CBC encryption and a dedicated
`empiredb` stanza. The V58 read-only production audit documented two
retained full backups, including a backup from 2026-10-16 08:00:00 UTC,
and validated archive metadata. See
`docs/architecture/EMPIREDB_V58_ACTIVE_PGBACKREST_REPO_AUDIT_20261016.md`
in the existing historical worktree. This is **past evidence**, not a claim
that today's repository has been rechecked.

## Bounded correction

`scripts/review_rev051_pgbackrest_backup_readonly.py` now invokes only
`pgbackrest --config=/etc/pgbackrest/empiredb.conf --stanza=empiredb --output=json info`
as the postgres identity. It prints redacted readiness booleans and times,
not raw backup metadata or passphrases.

`scripts/deploy_approved_rev051_guarded_20261018.sh` now uses that **same**
explicit repository. Before reading it, the script checks the existing
postgres-owned, mode 0600, non-symlink config and pinned nonsecret options:
`pg1-path=/var/lib/postgresql/18/main`,
`repo1-type=posix`,
`repo1-path=/var/backups/empiredb/pgbackrest`,
`repo1-cipher-type=aes-256-cbc`.
It then checks that the live primary's exact `archive_command` matches the
active repository. If the configuration, current PostgreSQL archive command,
backup freshness, trusted source tables or missing REV051 objects differ, the
deployment still returns HOLD **before** its single guarded DDL transaction.

The shared `empire_os/rev051_pgbackrest_readiness.py` validator now insists
that exactly one named `empiredb` stanza was returned, with healthy status,
repository key 1 if a repo array exists, and a full-base backup plus a
completed backup at most seven days old. The diagnostic still does not
independently prove off-node recovery or a current restore drill.

Unchanged: exact reviewed REV051 SQL SHA256, founder's approval scope
(NOLOGIN capability + single-event function only), isolated PostgreSQL
tenant-isolation fixture, post-commit capability verification and denial
of creating logins, roles beyond REV051, tenant grants, customer release,
money movement, database table edits or service restarts.

## Founder deployment command (already approved scope)

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.review_rev051_pgbackrest_backup_readonly --read-only && \
sudo bash scripts/deploy_approved_rev051_guarded_20261018.sh --apply-approved-role-function-only
```

The first output must be
`PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED`; only then does the guarded
release proceed. If any HOLD appears, stop and review the exact reason.
Success must end with
`REV051_DEPLOYMENT_DONE=ROLE_FUNCTION_ONLY_LOGIN_AND_PAYMENTS_UNCHANGED`.

**This change does not create a new backup or replace the existing working
physical recovery infrastructure.** Off-node backup protection remains a
separate workstream and is not implied by a successful local backup preflight.
