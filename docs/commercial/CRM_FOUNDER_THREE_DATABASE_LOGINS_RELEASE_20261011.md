# EmpireOS founder CRM — three dedicated DB LOGIN authority

**Status:** Prepared and verified in disposable PostgreSQL 18. Not applied to production.

**Founder approvals:** Three exact database identities already approved; three matching local SCRAM HBA rules separately approved and confirmed **deployed** by the founder on 11 October 2026. Do not repeat the HBA change, membership activation or CRM schema migrations.

## The one remaining governed database release

`scripts/provision_crm_dedicated_logins.py` provisions **only**:

- Existing `empire_crm_auth_login`: transition staged NOLOGIN to LOGIN, with a distinct generated SCRAM password. Preserve its existing narrow credential-table privileges.
- Existing `empire_crm_membership_login`: transition staged NOLOGIN to LOGIN, with a distinct generated SCRAM password. Preserve its existing bounded membership-function privilege.
- One new `empire_crm_tenant_708efd4b53b2` LOGIN NOINHERIT, with its own distinct SCRAM password, only `empire_revenue_crm_reader` membership (`INHERIT FALSE, SET TRUE`) and one evidence-backed `public.empire_tenant_role_bindings` entry for the already verified founder tenant.

The founder CRM membership row is verified, never recreated. No login credential **account row** is created here; that requires the existing approved offline invite workflow later. No HTTP service, sender, outbound, payments or customer data grants are activated.

This release requires matching HBA SCRAM rules already live; checks role baselines, owner membership, zero existing founder credentials, absent reader/binding, canonical views and tenant function, and exact authentication policy. It fails closed on any mismatch.

**Secrets:** Three independent random high-entropy passwords are generated only on the server, stored only in `/var/lib/empire-crm-first-party/pgpass` (0700 parent / 0600 file, owner `ubuntu`, no stdout). The DDL transaction receives SCRAM-SHA-256 *verifiers only*, not plaintext passwords. The service will later need `PGPASSFILE=/var/lib/empire-crm-first-party/pgpass` in its private systemd environment; this release does not activate that service.

**Recovery:** Before changing role authority, the operator verifies a source Git hash and makes separate root-only, SHA256-checked backups of PostgreSQL globals and the canonical tenant role-binding table under `/var/backups/empiredb/crm-founder-three-dedicated-logins/`. The three-role PostgreSQL changes are one transaction. No full-DB restore rehearsal is claimed. If any step fails or final proof is uncertain, **stop and reconcile; never blindly reapply or regenerate passwords**.

## Approved single-run sequence

Run from the already active EmpireOS repository:

```bash
cd /srv/empire_os

sudo -n /srv/empire_os/.venv/bin/python \
  scripts/provision_crm_dedicated_logins.py --preflight
```

Expected: JSON `"status": "READY_TO_PROVISION"`. Only then:

```bash
sudo -n /srv/empire_os/.venv/bin/python \
  scripts/provision_crm_dedicated_logins.py \
  --apply --approved-three-crm-logins
```

Expected receipt:

```text
CRM_LOGIN_BACKUP=GLOBALS_AND_TENANT_BINDINGS_VERIFIED_SHA256
CRM_LOGIN_PRIVATE_CREDENTIAL_FILE=CREATED_SERVER_ONLY
CRM_LOGIN_ROLE_TRANSACTION=COMMITTED
CRM_LOGIN_SESSION_AUTH_AND_FOUNDER_TENANT_PROOF=PASS
CRM_LOGIN_STATUS=THREE_DEDICATED_LOGINS_VERIFIED
```

Then run the independent, credential-free readback:

```bash
sudo -n -u postgres /srv/empire_os/.venv/bin/python \
  scripts/provision_crm_dedicated_logins.py --internal-readback
```

Expected: `"status": "CATALOG_VERIFIED"` plus verified exact reader group and tenant binding and zero founder application credential rows. Do not confuse database role passwords with a human founder account login.

If the operator prints `BLOCKED_OR_UNVERIFIED_DO_NOT_BLINDLY_RETRY` or a readback check fails, **do not rerun**. The transaction may have committed. Preserve the backup and credential vault and reconcile the catalog first.

## Evidence and next boundary

- Disposable real PostgreSQL role DDL + atomic tenant binding + SCRAM verifiers: `scripts/test_crm_three_role_transaction_ephemeral.sh`
- Actual `PGPASSFILE` password authentication in disposable PostgreSQL: same fixture, PASSED
- Missing/wrong password rejection: `scripts/test_crm_three_login_scram_ephemeral.sh`
- Source safety tests: `tests/test_provision_crm_dedicated_logins.py`
- Auth and tenant routing regressions: existing `tests/test_revenue_crm_pilot_activation.py` and `tests/test_revenue_crm_signed_auth.py`

Once the *real* roles and session binding are verified, use existing first-party invitation provisioning and a valid private signing key; only afterward enable the separate **loopback** CRM pilot on port 8783. Don't install public Cloudflare ingress as part of this database role task. No outreach or marketing permission arises from CRM authentication.
