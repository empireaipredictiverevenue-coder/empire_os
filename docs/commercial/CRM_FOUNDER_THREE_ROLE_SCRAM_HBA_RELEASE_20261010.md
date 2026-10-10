# EmpireOS founder CRM — exact-role SCRAM HBA release

**Date:** 10 October 2026

**Status:** source prepared + disposable PG18 verified; **NOT deployed or approved for HBA mutation**

## Grounded production blocker

The founder ran `scripts/probe_crm_first_login_auth_readonly.sql` and obtained:

- `next_action=PREPARE_EXACT_LOCAL_SCRAM_AUTH_RULES`
- `canonical_database=true`, `writable_primary=true`
- `active_founder_owner_verified=true`
- `existing_identity_roles_staged=true`
- `tenant_reader_role_not_created=true`, `tenant_reader_binding_not_created=true`
- `hba_configuration_parses=true`
- `all_three_role_specific_scram_rules_effective=false`

Membership activation is COMPLETE. Never repeat it. Existing `NOLOGIN` role grants are ready. The login transport still needs a *separate* founder-approved production HBA amendment before activating database credentials.

## Exactly what the prepared patch does

Script: `scripts/deploy_crm_hba_three_roles.py`. The only HBA changes it proposes are these three prepended, local-socket, database-exact first-match lines:

```text
local   empiredb   empire_crm_auth_login             scram-sha-256
local   empiredb   empire_crm_membership_login       scram-sha-256
local   empiredb   empire_crm_tenant_708efd4b53b2   scram-sha-256
```

Every pre-existing HBA byte remains after the inserted block. It refuses unknown/duplicated/malformed input or a different PostgreSQL cluster. It verifies a root operator, exclusive lock, exact reviewed Git blob, expected current catalog status, HBA ownership, canonical cluster, SHA256 backup of the complete file and space for an atomic replacement, and a PostgreSQL configuration reload. It checks `pg_conf_load_time` and the existing authoritative CRM readiness SQL again. On a failed reload/readback it restores the original file and reloads, if no concurrent administrator has changed the file. It never creates a role, password, login credential, CRM membership, service, sender or public endpoint.

This is a change to **PostgreSQL authentication policy** and therefore needs explicit founder approval **distinct from approval to create the three roles**. Do not run its `--apply` path or make manual HBA edits from this document without that approval.

## Validation evidence

`bash scripts/test_crm_hba_three_roles_isolated.sh` — **PASS** with a throwaway PostgreSQL 18 database, including three successful first-party role password logins, wrong-password rejection for each role, and preservation of existing PostgreSQL socket authentication. The disposable cluster is deleted. No production HBA file or real EmpireDB role was touched.

`PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_deploy_crm_hba_three_roles.py tests/test_probe_crm_first_login_auth_readonly.py` verifies only strict additive scope, duplicate rejection, exact CLI approval, backup/rollback logic and read-only metadata contract.

## One-step rollout boundary

After independent approval of these three local SCRAM rules, operator first runs:

```bash
cd /srv/empire_os
sudo -n /srv/empire_os/.venv/bin/python \
  scripts/deploy_crm_hba_three_roles.py --preflight
```

**Only if** the preflight returns `CRM_HBA_RESULT=PREFLIGHT_READY_NO_CHANGE` (and founder specifically approves HBA mutation) may the separately gated `--apply --approved-exact-three-crm-hba-rules` path be used. The successful result is `CRM_HBA_RESULT=APPROVED_EXACT_RULES_ACTIVATED`. A blocked or uncertain outcome must be reconciled rather than blindly retried.

The next, separate database authority transaction (two staged LOGIN roles + one new tenant-bound reader) still requires a fully reviewed secure secret-vault and PostgreSQL role-provisioning operator. No HBA result creates roles or a first-party CRM login automatically. Do not activate the CRM HTTP pilot until these three actual logins, session_user tenant binding and a real founder invitation/login are verified.
