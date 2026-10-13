# EmpireDB 047 — post-commit privilege hold, 13 October 2026

## Confirmed production evidence

Founder ran the separately approved, exact-scope deployment:

- `DIRECT047_PRODUCTION_PREFLIGHT=PASS`
- `DIRECT047_BACKUP_STARTED=YES`
- `DIRECT047_BACKUP=VERIFIED`
- `DIRECT047_BACKUP_LOCATION=/var/backups/empiredb/direct-bsc-buyer-capability-047/20261013T165434Z`
- `DIRECT047_FULL_RESTORE_REHEARSAL=NOT_PERFORMED`
- **`DIRECT047_SQL_TRANSACTION=COMMITTED`**
- **`DIRECT047_STATUS=POSTCOMMIT_PRIVILEGE_DRIFT_DO_NOT_RETRY`**
- `MIGRATION047_EXIT=5`

The transaction committed, so the newly created table/function/trigger may
exist even though the installer returned nonzero. The installer emitted no
post-commit privilege success and did not reach its final checkout readback.

Independent, read-only checkout service health checked immediately afterward:
`status=online`, DIRECT settlement, binding order creation OFF, payment
proposal OFF, payment execution false, revenue recognition false. This is
**NOT** a verified all-green security clearance for the new table.

### Rules during investigation

- Never rerun the original migration 047 or its installation wrapper.
- Never assume a failed process exit rolled back a transaction that COMMITTED.
- Do NOT activate public buyer status, grant reader privileges, restart
  checkout, enable orders, propose payment or process funds.
- Preserve the timestamped root-only backup and private installer logs.
  Do not publish the archive, global-role dump, DSN or user records.
- Do not automatically REVOKE or change DEFAULT PRIVILEGES merely because
  an inherited/default GRANT is suspected. Investigate exact ACL source.
- If a failed postcommit check represents an actual public exposure, keep
  finance gates OFF and obtain a separately reviewed remedial change.

## Exact read-only catalogue forensics

`scripts/inspect_direct_bsc_capability_047_postcommit.sql` duplicates all
NINE postcommit checks by meaningful names, and also inspects owner, RLS
configuration, exact table/function ACL entries and existing default table
grants of the migrator. It does not inspect or return any buyer/order rows,
secrets or wallet evidence; it uses BEGIN READ ONLY and ROLLBACK.

The script **reports** pass/fail; its psql process may exit 0 even when a
named check FAILS. Never treat exit status alone as proof of all nine passes.

Run in the founder's privileged Ubuntu terminal:

```bash
cd /srv/empire_os
set +e
sudo -n -u postgres psql -X -d empiredb -v ON_ERROR_STOP=1 \
  -f scripts/inspect_direct_bsc_capability_047_postcommit.sql
echo "DIRECT047_DIAGNOSTIC_EXIT=$?"
```

Send the named checks and owner/ACL results back for review. The exact
next remediation, if any, must be separately approved. The previous
founder consent was limited to installing the originally approved sealed
register, not extending role permissions or applying a second migration.

## Independent forensic query proof

- Disposable PG18 applied original migration and confirmed all 9 checks PASS.
- Added intentionally unsafe `SELECT` to ordinary app in disposable PG18:
  named check `03_app_select_denied` became FAIL, while FORCE RLS continued
  to deny actual rows.
- Original duplicate/cross-order/immutable revocation negative tests passed.
- Focused Python syntax/source/security tests passed.
- No database mutation or migration executed during forensic preparation.
