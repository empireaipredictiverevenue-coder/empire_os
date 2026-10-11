# EmpireOS founder CRM — exact CONNECT-only postcommit repair

Date: 11 October 2026
State: **Code verified in disposable PostgreSQL 18; production grant not applied.**

## Grounded production truth

The founder's production `--internal-readback` reported `CATALOG_VERIFIED`, confirming three SCRAM LOGIN identities, narrowly restricted membership and the one active founder tenant binding. These roles were already created and their secret passfile already stored on EmpireOS. **Do not repeat role provisioning, secrets, HBA migration or founder membership activation.**

The read-only, temporary-password-file session check on actual EmpireDB returned `DATABASE_CONNECT_DENIED` for exactly these three roles:
- `empire_crm_auth_login`
- `empire_crm_membership_login`
- `empire_crm_tenant_708efd4b53b2`

The remote diagnostic used server-owned secret bytes only in a temporary 0600 file; the original passfile was never printed or rewritten. The failed earlier passfile lookup repair restored the original three-row file and left a mode-0600 owner-only backup. No password was rotated.

## Narrow grant

`scripts/grant_crm_three_logins_connect.sql` is an **atomic** PostgreSQL grant of `CONNECT` **only on database `empiredb`** to those three named roles. Its transaction verifies:

1. Canonical writable `empiredb` and postgres DBA session.
2. All three existing logins safe with SCRAM verifiers.
3. No unintended role memberships and one evidenced founder tenant role binding.
4. Exactly one active owner membership for the founder.
5. None of the three already has `CONNECT` (including via PUBLIC); partial or repeated applications refuse to proceed.

The script does not create or change roles, passwords, membership rows, data tables, schema privileges, `CREATE`, `TEMP`, SMTP, or the CRM HTTP service. It prints a constant receipt only after commit. It must be run by the founder's privileged terminal because Remote Desktop Commander rejects sudo.

## Exact privileged command — once

```bash
cd /srv/empire_os
sudo -n -u postgres psql -X -w -v ON_ERROR_STOP=1 \
  -d empiredb -f scripts/grant_crm_three_logins_connect.sql
```

Expected `CRM_CONNECT_RESULT=EXACT_THREE_ROLE_CONNECT_GRANT_COMMITTED`. On a failed/uncertain result, do not rerun. Reconcile catalog and privilege evidence, rather than changing roles or credentials.

Following a successful receipt, the next safe check uses the committed read-only script:

```bash
cd /srv/empire_os
PYTHONPATH=. /srv/empire_os/.venv/bin/python \
  scripts/diagnose_crm_committed_login_sessions.py --read-only
```

It creates a disposable **0600** passfile using unchanged existing secret bytes with the `localhost` compatibility aliases, checks all three roles' `session_user`, the exact founder tenant binding, and denial of raw global binding-table access. It deletes that temp file and never prints credentials. A successful result is `CRM_SESSION_DIAGNOSTIC=ALL_PASS`.

Then separately reconcile the original persistent `PGPASSFILE` lookup alias for the eventual CRM service; the previous failed repair left an exact backup and must not be blindly retried unchanged.

## Isolated evidence

`scripts/test_crm_three_connect_grant_isolated.sh` PASSED on disposable PG18: refusal without active founder membership, one atomic three-role grant with no database `CREATE`, and second application blocked. No live DB modified.

`tests/test_grant_crm_three_logins_connect.py` and `tests/test_diagnose_crm_committed_login_sessions.py` cover exact SQL scope, no data writes, error classification and no-secret temporary passfile use.

Human founder login remains a separate stage: no `empire_crm_login_credentials` row or private signing configuration is yet verified. Do not claim the CRM HTTP pilot is activated.


## After verified database CONNECT: existing passfile repair can safely resume

The first passfile repair failed because all three database roles lacked CONNECT. It restored the original three-row passfile, but **left its original private backup intact**, correctly refusing the next attempt.

This release also updates `scripts/repair_crm_login_passfile_lookup.py` so it will accept the existing backup **only if it is owned by ubuntu, mode 0600, is not a symlink and matches the current unchanged original bytes exactly**. Otherwise it refuses the repair. It does not rotate or generate credentials.

Only after `CRM_SESSION_DIAGNOSTIC=ALL_PASS` should the passfile lookup alias be made persistent:

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python \
  scripts/repair_crm_login_passfile_lookup.py --preflight && \
/srv/empire_os/.venv/bin/python \
  scripts/repair_crm_login_passfile_lookup.py \
  --apply --approved-passfile-lookup-only
```

Expected `CRM_PASSFILE_BACKUP=PREEXISTING_EXACT_MATCH_VERIFIED`, then `CRM_PASSFILE_RESULT=THREE_LOGINS_AND_TENANT_PROOF_VERIFIED`. If the live proof fails, the original is restored. Don't rerun blindly.

The privileged independent catalog readback is **already verified** by the founder (`CATALOG_VERIFIED`); no second role provision, membership activation or password migration is needed. These checks close the DB-identity stage, not the founder-human invitation or public CRM deployment.
