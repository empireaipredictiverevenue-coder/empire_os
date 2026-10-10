# EmpireOS founder CRM — approved dedicated login provisioning preflight

Date: 10 October 2026. **Production status: NO LOGIN ROLE OR PASSWORD CHANGES.**

The founder explicitly approved two dedicated first-party CRM logins and one strictly tenant-bound CRM reader for the **already active** founder membership. The membership must never be recreated. No permission was given for general application-reader grants, customer export, public HTTP activation, outbound, payments, or future unrelated migrations.

The founder's verified `scripts/check_crm_pilot_readiness.sql` shows migrations 040/041/042 present, two prepared NOLOGIN roles with restricted grants, zero dedicated tenant readers, and independent HTTP identity not proven. The current founder tenant's canonical identity was cross-checked with `scripts/probe_crm_empire_founder_evidence.sql` and the prior active-membership deployment receipt; the new reader name must be derived from that existing tenant, not guessed from a client header.

**Crucial new dependency:** The CRM pilot DSNs in `empire_os/revenue_crm_pilot_activation.py` require PostgreSQL Unix sockets, `host=/var/run/postgresql`. The Linux service runs as `ubuntu` while the required PostgreSQL role names differ. Unless PostgreSQL has *first-matching, exact, role-specific local SCRAM-SHA-256 HBA rules*, creating LOGIN roles with passwords could still leave human login and tenant reads unusable. Never activate a LOGIN without verifying this transport and a safe server-side secret store.

## Single read-only production preflight

```bash
cd /srv/empire_os
sudo -n -u postgres psql -X -w -v ON_ERROR_STOP=1 -d empiredb \
  -f scripts/probe_crm_first_login_auth_readonly.sql
```

No passwords, tenant identifiers, raw contacts or identity records are printed. This checks canonical database, active founder owner, staged roles, absence of the new tenant role/binding, HBA syntax, and first-matching role-specific SCRAM policy. It ends in `ROLLBACK`.

If `next_action` is `PREPARE_EXACT_LOCAL_SCRAM_AUTH_RULES`, stop without creating login roles or credentials. First review and back up the actual HBA file, then arrange a narrowly scoped local SCRAM rule for **each of the three roles** ahead of generic local peer/trust rules, with independent PostgreSQL reload/readback and no change to other roles. HBA changes are a separate critical step and should not be guessed or silently made by an automation.

If `next_action` is `READY_FOR_APPROVED_THREE_LOGIN_PROVISIONING`, the remaining approved writer must atomically provision two existing role passwords with LOGIN, create one `LOGIN NOINHERIT` tenant reader, grant only `empire_revenue_crm_reader` with `INHERIT FALSE`, store randomly generated SCRAM credentials in a restricted on-server `PGPASSFILE`, insert exactly one tenant role binding, verify `session_user` for all three roles and verify tenant isolation in a real read-only transaction. No secrets should be sent in chat, shell arguments or system logs. Take a verified backup before changing role authority. **Do not run a general identity-role bootstrap again.**

The dedicated CRM service source has been promoted to main as `efc52246` and its listener corrected to unused loopback `8783` in `15322433`. It is not installed/activated. The Gmail relay owns 8775 and must not be disturbed.

## Engineering proof

- Query: `scripts/probe_crm_first_login_auth_readonly.sql`
- Disposable PostgreSQL 18 contract test: `scripts/test_crm_login_auth_preflight_isolated.sh`
- Static safety tests: `tests/test_probe_crm_first_login_auth_readonly.py`
- No production database write, HBA change, credential file, new role, new membership or public service was performed by these tests.

This preflight is an exact stopping point, not another CRM feature wave. The next action depends only on the actual production PostgreSQL authentication configuration.
