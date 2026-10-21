# Empire AI consumer subscriber database — atomic operator installer

Date: **2026-10-21**. Staged and tested, **not applied to EmpireDB**.

## Current original production evidence

Founder-operated privilege-scoped read-only psql output on 21 Oct 2026:
`empiredb_migrator=t`; `empire_consumer_optin_writer=f`; five consumer tables present `f`.
Privileged pgBackRest backup reviewer returned `PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED`, one healthy stanza, two completed backups and newest backup age 15.1h against the 168h maximum. It is **backup metadata**, not an independent restore test or authorization to migrate.

## Installer

`scripts/guarded_install_consumer_schema_20261021.py` creates the NOLOGIN/NOINHERIT/no-superuser consumer writer role and executes the exact SQL from migrations 057 and 058 **inside one outer PostgreSQL transaction**. A failure rolls back the role and both migrations together. It rejects existing conflicting roles, partial tables or policies, wrong target DB, wrong operator identity and digest mismatches.

The installer then verifies all five tables have forced RLS and migrator ownership, exactly five `consumer_writer_` policies, writer NOLOGIN, no public table SELECT/INSERT, and no implicit existing `empiredb_app` read grants. **It does not create a LOGIN, activate email delivery or enable subscriber intake.**

To protect against source changes, it requires the exact release digest:

`2fa878eb0d93d011dc55b1cba0e9c37b58603944b9c99abb4959a1238b80de0c`

This fingerprint binds the writer-role statement and both exact SQL files.

## Operator-accessible bundle

The operator `postgres` cannot traverse `/home/ubuntu` because its home folder is mode 0750. Do not run the installer from that worktree with `sudo -u postgres`; it cannot read the code.

Instead, stage the three nonsecret files in a random operator-readable `/var/tmp` release folder using:

```bash
cd /home/ubuntu/empire_worktrees/consumer_optin_roofing_20261020
bash scripts/stage_consumer_atomic_installer_20261021.sh
```

The staging script verifies the release digest before printing the new `BUNDLE_PATH`. A verified instance was staged at `/var/tmp/empire-consumer-db-20261021.gxcWAogm`, which contains only the installer and two SQL files. The generated bundle is **not** a live DB migration or service deployment.

Preflight, read-only, in the authorized terminal:

```bash
sudo -n -u postgres /srv/empire_os/.venv/bin/python -B \
  /var/tmp/empire-consumer-db-20261021.gxcWAogm/scripts/guarded_install_consumer_schema_20261021.py --read-only
```

This should report `migrator_ready=true`, `writer_exists=false` and `consumer_table_count=0`. The remote-desktop shell blocked this privileged command; do not claim it was independently executed from ChatGPT.

**Apply requires separate explicit founder schema activation approval.** Only then run the exact digest-gated command using the authorized privileged terminal. Retest backup metadata immediately before the command if its freshness or original evidence has changed. Do not execute a raw `CREATE ROLE` independently and do not apply 057/058 piecemeal.

## Test evidence

On the server, two fresh disposable PostgreSQL 18 clusters verified:

1. Positive path: NOLOGIN consumer role created, migrations 057/058 applied transactionally, 5 forced-RLS tables and 5 policies, zero public access, no consumer login, no payment/outbound/browser activation.
2. Negative path: preexisting incompatible LOGIN role is rejected with **zero tables created**.

The selected customer-privacy, sender, DB, public-gateway and installer test suite passed **136 tests**; one existing upstream AnyIO deprecation warning.

## Additional live activation requirements

Installing the empty, locked schema is **not** permission to collect any email addresses. The separately protected service login, encryption/HMAC key custody, actual Resend provider send/readback, webhook authentication, suppression/unsubscribe and the exact legally reviewed privacy notice remain required, as does content signoff for the free roofing guide and email-preferences page. Newsletter subscriptions cannot be resold as buyer referrals without a distinct lawful original buyer-sharing consent.

No production database was modified by this work.
