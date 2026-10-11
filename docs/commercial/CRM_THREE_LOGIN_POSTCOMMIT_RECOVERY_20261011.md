# EmpireOS CRM — committed three-login recovery (11 October 2026)

## Production truth

Founder's exact production output confirmed:
- HBA local SCRAM three-role release already applied successfully and reloaded. **Do not reapply.**
- Three-role database provisioning preflight: `READY_TO_PROVISION`.
- Full restricted globals/bindings backup: SHA256 verified.
- Secure three-credential server-side file: CREATED.
- Database role transaction: `CRM_LOGIN_ROLE_TRANSACTION=COMMITTED`.
- Postcommit operation: `CRM_LOGIN_STATUS=BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY`.

The database role transaction **already committed**. Do not rerun `scripts/provision_crm_dedicated_logins.py --apply`, generate new role passwords, recreate role bindings or change the founder membership.

Connected, unprivileged inspection established:
- `/var/lib/empire-crm-first-party` owner ubuntu, mode 0700.
- `/var/lib/empire-crm-first-party/pgpass` owner ubuntu, mode 0600.
- The passfile contains exactly three original `/var/run/postgresql:5432:empiredb` credential entries with long, nonempty secrets; no credential material was printed.
- A read-only PostgreSQL role login using `PGPASSFILE` returned `fe_sendauth: no password supplied`. The likely cause is libpq's default Unix-socket directory special handling: a `localhost` host entry must be available to match a default-socket connection. This is separate from the production privileged *catalog readback*, which remains unknown because the transaction operator failed **before** printing `CRM_LOGIN_POSTCOMMIT_CATALOG=VERIFIED`.

## Narrow correction

`scripts/repair_crm_login_passfile_lookup.py` adds `localhost` host alias entries for the **same three preexisting credentials**, retaining the original three lines and secrets. It refuses any unexpected role, content, path, ownership, permissions, duplicate or existing backup; saves an owner-only backup; atomically replaces the passfile; proves actual no-prompt socket logins for the three roles; proves the existing founder tenant through `SET LOCAL ROLE empire_revenue_crm_reader`; checks denied direct access to the global binding table; and restores the original file if any verification fails without an intervening independent file change. It never prints secrets, changes roles/passwords, touches PostgreSQL HBA, or activates CRM HTTP/outbound.

It runs as `ubuntu` (the passfile's current owner), **not postgres**. It is a recovery of already-approved, committed CRM credentials, not another DB-authority transaction.

## Controlled single-run recovery

```bash
cd /srv/empire_os
/srv/empire_os/.venv/bin/python scripts/repair_crm_login_passfile_lookup.py --preflight && \
/srv/empire_os/.venv/bin/python scripts/repair_crm_login_passfile_lookup.py \
  --apply --approved-passfile-lookup-only && \
sudo -n -u postgres /srv/empire_os/.venv/bin/python \
  scripts/provision_crm_dedicated_logins.py --internal-readback
```

The first command must return `CRM_PASSFILE_LOOKUP=ORIGINAL_THREE_ROWS` or `REPAIRED_SIX_ROWS`, and `PREFLIGHT_NO_CHANGES`. The repair must return `CRM_PASSFILE_RESULT=THREE_LOGINS_AND_TENANT_PROOF_VERIFIED`; otherwise **stop, do not blindly rerun**. The final privileged **read-only** `--internal-readback` returns a JSON status; only `CATALOG_VERIFIED` closes role provisioning. If it returns `CATALOG_UNVERIFIED`, inspect the returned booleans; do **not** rerun original provisioning.

No password or invitation token is required in chat. No role mutation permission is exercised by this repair. Do not expose CRM HTTP until catalog and founder-human login evidence pass.

## Test proof

`PYTHONPATH=. /srv/empire_os/.venv/bin/python -m pytest -q tests/test_repair_crm_login_passfile_lookup.py tests/test_provision_crm_dedicated_logins.py`: verifies pure host-alias transformation, strict three identities, protected backup, rollback, duplicate refusal, metadata-only logs and synthetic negative auth checks.

The previously verified disposable PostgreSQL role transaction, SCRAM verifier generation and PGPASSFILE mechanics remain covered by `scripts/test_crm_three_role_transaction_ephemeral.sh`. Do not describe a synthetic test as live production role proof.
