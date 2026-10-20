# EmpireDB physical backup schedule — Data Cloud release candidate

20 October 2026. PREPARED ONLY. Not installed; no backup production, timer activation or database migration.

## Verified
Founder executed one supervised online differential pgBackRest backup against existing EmpireDB. The dedicated 057 gate reported latest completed backup 0.1h old; full backup 107.7h old. The existing 15-minute Data Cloud backup observer later reported LOCAL_ARCHIVE_HEALTHY. This observer checks health; it does not create backups.

No active backup-producing systemd timer was identified. The earlier root/postgres cron check returned UNAVAILABLE and must not be interpreted as an empty crontab. Privileged inventory remains a release prerequisite.

## Authorised root read-only schedule inspection

Run from the feature worktree:

    cd /home/ubuntu/empire_worktrees/inbound_revenue_recovery_20261020
    sudo -n /srv/empire_os/.venv/bin/python -B - --read-only < scripts/inspect_empiredb_backup_schedule_20261020.py

Only scheduling metadata is inspected, and only redacted statuses are printed. A missing user crontab is reported as NO_CRONTAB; sudo/access failure is UNAVAILABLE. No cron text, database records or secrets are printed. A clean inventory means only READY_FOR_EXISTING_DATA_CLOUD_OWNER_REVIEW; it never means automatic activation.

## Inactive systemd candidates

- deploy/systemd/empire-data-cloud-physical-backup@.service: online PostgreSQL backup, existing pinned pgBackRest config, postgres identity, no restart; automatic expiry disabled to protect retained recovery sets during supervised pilot.
- deploy/systemd/empire-data-cloud-physical-backup@diff.timer: Mon/Tue/Thu/Fri/Sat differential, approximately 03:00 UTC.
- deploy/systemd/empire-data-cloud-physical-backup@full.timer: Wednesday/Sunday full backup, approximately 03:00 UTC.

DO NOT INSTALL OR ENABLE YET. Twice-weekly full backups are proposed to stay inside the strict 168-hour full-backup age threshold, including the initial run after today's 107.7-hour-old full backup. The DBA must reconcile workload, retention, storage growth, concurrent operations, existing jobs, recovery-base preservation and current recovery/restore proof before enabling anything. Explicit founder and DBA release required to activate.

Existing Data Cloud owner retains one backup schedule and one backup observer. Revenue Recovery should not spawn a parallel DB backup system. Independent restore/PITR proof remains separate from backup metadata and from approval to execute migration 057.


## 20 October — bounded physical backup job guard (staged only)

Prepared source: scripts/inspect_empiredb_backup_job_preflight_20261020.py.
The inactive DBA-owned systemd service now requires this guard through
ExecStartPre before every full/differential run. The guard is deliberately
pinned to a future, root-owned release path under
/opt/empire-ai/backup-operators/releases/20261020-empiredb-physical-guard-v1/.
**It has not been installed there.** A direct invocation from the source
worktree must return HELD_BACKUP_JOB_OPERATOR_CUSTODY.

At job runtime, the guard checks:
- Existing EmpireDB pgBackRest stanza/repository metadata and a valid full base.
- For differential jobs, an eligible full backup no older than 168 hours.
- Fewer than 28 retained backup records, to prevent uncontrolled accumulation
  while automatic expiry is disabled.
- At least 100 GiB of free repository disk space.
- Private PostgreSQL-owned config and backup-repository directory, and
  expected root-owned release-script custody.
- Exactly the full or diff job type; any unrecognised instance is denied.

This is a SAFETY CEILING, not a complete retention policy. Once the backup
count reaches 28, or disk space falls below 100 GiB, scheduled backups stop
and require an operator's remediation; unattended operation would therefore
be incomplete without tested retention and failure notification. Do not
activate the proposed units until the existing Data Cloud/DBA owner verifies
physical recovery, a bounded retention policy, alerts and the exact unit
and guard files. No repository expiry, backup creation, unit install, service
enablement or production DDL has been performed by this code change.
