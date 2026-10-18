# REV051 founder-approved release — pgBackRest metadata preflight repair

**18 October 2026 · read-only recovery proof preserved · no DB changes made**

## Trigger

The founder ran the previously approved exact local release command:

`sudo bash scripts/deploy_approved_rev051_guarded_20261018.sh --apply-approved-role-function-only`

It returned **`REV051_DEPLOYMENT_HOLD=RECENT_VERIFIED_BACKUP_NOT_PROVEN`** before any PostgreSQL DDL. This is a correct fail-closed outcome; however, the release parser itself mistakenly required a `repo[].status.code=0` entry in every `pgbackrest info --output=json` response.

Official pgBackRest documentation says a single-repository healthy stanza may be represented by top-level `status.code=0` without the extra per-repo progress array. Therefore the old parser could produce a false-negative even when a real completed backup exists. Source: https://pgbackrest.org/user-guide.html (Backup Information).

## Narrow repair

- `empire_os/rev051_pgbackrest_readiness.py` validates top-level healthy stanza status; if `repo` is **present**, it additionally requires at least one healthy repository; if `repo` is *absent*, it relies on healthy stanza status, never on implicit backup existence. An explicitly empty repository list is **not** accepted.
- The healthy stanza must also enumerate a full backup and at least one completed full, differential or incremental backup with a valid start/stop UNIX timestamp **within seven days**. Unhealthy, malformed, stale, future-dated or missing backups still return HOLD.
- `scripts/deploy_approved_rev051_guarded_20261018.sh` now calls the same shared validator instead of repeating the incorrect inline parser. The remaining SHA256 pin, read-only PostgreSQL/archiving preflight, actual database object checks, single atomic migration and post-deploy role/function catalog verification are unchanged.
- `scripts/review_rev051_pgbackrest_backup_readonly.py` is a strictly read-only, root-local, redacted diagnostic. It invokes *only* `runuser -u postgres -- pgbackrest info --output=json` and prints counts, time age and reason codes, **never** repository paths, raw metadata, credentials, buyer rows or WAL secrets.
- `tests/test_rev051_pgbackrest_backup_readiness_20261018.py` tests JSON schemas with and without repo arrays, genuine missing/old backup, explicit unhealthy repository, invalid timestamps, root-only local diagnostic and redacted stderr.

No migrations, new backups, restores, credentials, activations, timers or source-record reads have occurred in this repair. The previous failed founder deployment likewise did not execute REV051 DDL.

## Safe production diagnostic

Run on the authenticated EmpireOS host:

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.review_rev051_pgbackrest_backup_readonly --read-only
```

Expected successful status `PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED`. A HOLD with `reason=NO_FULL_BACKUP_IN_STANZA` or `NO_RECENT_COMPLETED_BACKUP` is a **genuine missing/stale physical backup**, not a parser issue. Do not disable the safety check or treat the separate encrypted logical restore proof as a fresh pgBackRest physical backup.

If the diagnostic passes, the prior approved migration can be attempted again using the **same exact command**:

```bash
sudo bash scripts/deploy_approved_rev051_guarded_20261018.sh --apply-approved-role-function-only
```

This next command still checks primary/WAL archive and live catalog. The founder approved only NOLOGIN role + restricted single-event SECURITY DEFINER function. An actual login, tenant binding, authenticated event retrieval and customer report release remain separate unapproved steps.

A good metadata summary proves only that pgBackRest reports a recent completed backup for a healthy stanza. It is not an independent restore drill and does not establish backup integrity beyond pgBackRest's own completed status.
