# REV052 — restricted admin process execution preflight repair

**18 October 2026 · exact founder-approved one-login scope unchanged · production login not provisioned**

## Live founder result

Founder ran the read-only preflight of the previously reviewed REV052 release
as the first command in a preflight-then-apply shell `&&` chain.

It emitted `REV052_STATUS=HOLD_OR_UNVERIFIED_NO_BLIND_RETRY`. As the first
command returned nonzero, shell `&&` did **not** invoke
`--apply-approved-one-tenant-login`. No evidence the database login,
tenant binding, password or HBA change was applied.

## Reproduced exact cause

The `pg()` helper passed subprocess a restricted
`PATH=/usr/bin:/bin`, but attempted to launch the unqualified executable
`runuser`. On the actual EmpireOS Ubuntu host, `runuser` is at
`/usr/sbin/runuser`, and `shutil.which('runuser',path='/usr/bin:/bin')`
returned `None`. A test subprocess with this restricted PATH failed with
`FileNotFoundError` **before any PostgreSQL SQL was executed**.

The repair uses the exact pinned, known existing absolute paths:

- `/usr/sbin/runuser`
- `/usr/bin/psql`

The tightly restricted child environment, local postgres peer database
connection, parameters via process stdin, redacted logs and preflight
transaction `BEGIN READ ONLY` remain unchanged.

To avoid another opaque failure, the operator now emits one **sanitised**
`REV052_FAILURE_STAGE` value on unexpected exceptions, never the raw SQL
exception, secret path, password or full database result. On a preflight-only
error this stage is `CATALOG_READONLY`, and no HBA, credential or database
write is attempted. Mutating apply still requires the exact separate
founder-approved activation argument and commit-matched source file.

## Evidence

The regression `test_pinned_runuser_exec_starts_under_restricted_path`
launches actual `/usr/sbin/runuser --version` using exactly that restricted
environment, without requiring root or touching a database.

The expanded isolated ephemeral PostgreSQL 18 test executes the **exact**
`readiness_sql()` against the synthetic fixture and checks that each source,
role/function, tenant and privilege requirement is true, with only its
deliberately different temporary HBA and data-directory paths false.
It then authenticates the synthetic dedicated login over SCRAM, tests its
tenant-owned event, denies cross-tenant reads and ledger-table SELECT,
and destroys the temporary test-only database.

No production roles, HBA, credentials or payments were changed by this
repair. The already-verified REV051 role/function remain installed.
The authorised tenant is the existing EmpireDB founder tenant only.
No service restart or additional infrastructure is required.

## Next authorised local preflight and one-time deployment

Once the exact patch is committed in `/srv/empire_os`, run:

```bash
cd /srv/empire_os
sudo ./.venv/bin/python -B -m scripts.provision_revenue_event_evidence_login_20261018 --preflight &&
sudo ./.venv/bin/python -B -m scripts.provision_revenue_event_evidence_login_20261018 --apply-approved-one-tenant-login
```

The preflight must report
`REV052_STATUS=READY_ONE_FOUNDER_TENANT_RESTRICTED_LOGIN`
before the second command runs. On a blocked preflight, share only the
sanitised `REV052_STATUS`, `REV052_FAILED_PREREQUISITES` or
`REV052_FAILURE_STAGE` values; never print credentials, raw config,
role password hashes or private pgBackRest paths.

If the apply step reports a transaction-committed but verification-failed
status, **do not retry** without reconciling the existing role, binding
and private credential. Success of this login test still does not prove
one actual customer payment or a complete revenue census.
