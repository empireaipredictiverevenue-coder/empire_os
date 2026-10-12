# Empire AI / EmpireOS — BSC escrow two-operator activation (one-shot)

**Date:** 12 October 2026. **Production branch:** `agent/data-cloud-wave4`. **Owner:** EmpireOS financial security / launch. **Status:** code and disposable auth test complete; production writes separately founder-gated.

## Source-of-truth recovery — no rebuilding payment services

The live treasury EIP-191 proof establishes control of the existing public BSC receiving address `0x1339b487046B0ad924a10c20b1791608EA8595a8`. The original approved four-product prices and conditional settlement authorisation remain recorded.

On live, sovereign `empiredb` (PostgreSQL 18), existing `empire_payment_approver` and `empire_escrow_verifier` are correct **NOLOGIN / NOINHERIT** permission roles. They already possess the **six exact expected functions** for reviewing, human-approving/cancelling and independently recording escrow creation/lifecycle evidence. The ordinary app login has **none of the financial write functions**. Both permission groups currently have **zero operational LOGIN members**. This is the actual operational gap, not a missing payment system or migration.

The existing HBA contains CRM and consultancy SCRAM-specific authentication rules and generic peer fallback. The two required payment/escrow LOGIN identities do not exist and have no exact matching SCRAM rules.

No mainnet escrow contract or independent smart-contract audit has been verified; approval of four product prices is not permission to deploy a contract or move funds.

## Exact one-shot operational design

New read-only `scripts/inspect_bsc_payment_operator_readiness.py` and `empire_os/bsc_payment_operator_readiness.py` inspect **only pg_catalog metadata**. They verify permission groups, absence of app financial authority, six exact functions, login security attributes, Postgres HBA first-match authentication, and absence of unexpected or inherited memberships. They never read customer/business rows or reveal credentials. On production now, their exact result is:

`PREPARE_EXACT_TWO_LOCAL_SCRAM_HBA_RULES`.

A bounded, independently authorisable **two-part activation** uses the existing first-party Postgres mechanisms:

**Part A — exact HBA rules only:** `scripts/prepare_bsc_operator_hba.py` adds exactly:

```text
local   empiredb   empire_payment_approver_login   scram-sha-256
local   empiredb   empire_escrow_verifier_login    scram-sha-256
```

Both rules are prepended ahead of generic peer auth; all original `pg_hba.conf` bytes are preserved. It reuses the earlier production-proven CRM HBA atomic writer, canonical cluster assertions and `pg_reload_conf()` (not a Postgres restart). It requires an isolated mode-0600 SHA-256 verified backup, checked-in source hash, concurrency lock, repeat catalog verification, and rollback if the new effective rules cannot be proved. **No roles, passwords, memberships, funds or public API changes** in this step.

Read-only command, already successful:

```bash
sudo -n /srv/empire_os/.venv/bin/python /srv/empire_os/scripts/prepare_bsc_operator_hba.py --preflight
```

The write command **requires its own exact approval marker**. Do not run without explicit founder permission:

```bash
sudo -n /srv/empire_os/.venv/bin/python /srv/empire_os/scripts/prepare_bsc_operator_hba.py --apply --approved-exact-two-bsc-financial-hba-rules
```

**Part B — two distinct PostgreSQL login identities, never checkout privileges:** `scripts/provision_bsc_financial_operator_logins.py` generates separate cryptographically random 48+ character secrets and the reusable first-party `scram_verifier()` from the established CRM login provisioning code. Under PostgreSQL's own operating user it creates exactly `empire_payment_approver_login` and `empire_escrow_verifier_login`, both **LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS**, and grants each precisely **one** respective existing permission role with `INHERIT FALSE, SET TRUE, ADMIN FALSE` in a single database transaction. A separate root-owned, mode-0700 directory holds two **separate mode-0600 secret passfiles**. No secrets in argv, logs, git, public gateways, chat messages, checkout service env or unprivileged Ubuntu files.

The script includes a root-only global-role rollback backup, source-hash check and lock. It verifies post-commit role attributes, exact membership isolation and **actual PostgreSQL SCRAM authentication + SET LOCAL ROLE** for both identities in read-only SQL transactions. It does not automatically log in as a human or automatically execute financial RPCs. Failed partial deployment is held for explicit reconciliation; the script does not loop or widen permissions.

Read-only command (currently correctly held until Part A):

```bash
sudo -n /srv/empire_os/.venv/bin/python /srv/empire_os/scripts/provision_bsc_financial_operator_logins.py --preflight
```

Separate, explicit founder-approved write command for Part B, **only after Part A fully verifies**:

```bash
sudo -n /srv/empire_os/.venv/bin/python /srv/empire_os/scripts/provision_bsc_financial_operator_logins.py --apply --approved-two-bsc-financial-operator-logins
```

These are internal financial SQL identities, not customer authentication credentials and not authorisation for anybody to approve a specific payment, record fabricated on-chain events, sign a contract or spend USDT.

## Evidence and test method

- Existing production live catalog: correct two NOLOGIN groups, six routine grants, no financial app privileges, zero financial LOGIN members, no exact local SCRAM rules. No migrations required.
- New pure rules and provisioning tests: reject HBA shadowing, app role escalation, role inheritance, unsafe PostgreSQL login flags, extra grants or reused credentials.
- HBA `--preflight` actually ran against canonical PostgreSQL 18 with all original HBA bytes intact. No write, reload, new roles or password generated in production.
- Full isolated PostgreSQL 18 `pg_virtualenv` proof in `scripts/test_bsc_two_operator_login_ephemeral.sh`: two separate SCRAM logins succeeded, exact `SET LOCAL ROLE` succeeded, cross-role escalation and wrong passwords rejected. Disposable isolated cluster used nonproduction port/data directory and deleted on exit. This is stronger than mock-only testing but **not** an activation of production financial identities.
- No new systemd agent/timer/runtime, no Supabase, Resend or payment provider.

## Founder-gated final activation

The entire **two-part HBA + dedicated login provisioning** can be authorised in **one explicit decision**. The decision is only to create these two exact Postgres authentication rules and two distinct login identities with the fixed groups above. Do not bundle this with on-chain contract deployment, financial transaction signing, live payment activation, outbound or migrations.

After Part A and Part B actually verify, production operator identities can be marked provisioned, but separate human operator assignment, external security review, audited on-chain deployment and lifecycle proof **must still pass** before customers receive escrow funding instructions. Current binding orders and payment proposals stay OFF.

**Rollback and incident:** Part A retains the exact original HBA bytes, SHA-256 proof and reload recovery. Part B captures root-only PostgreSQL role globals before any role creation and holds on anomalous grants or authentication mismatch; no blind retry or broad role deletion. Post-apply proof must be independently reviewed.

**Current commercial reality:** founder-led sales enquiries LIVE; four approved prices VERIFIED; treasury EOA control VERIFIED; operator logins NOT YET ACTIVATED; escrow mainnet contract NOT YET DEPLOYED; payment collection OFF; actual revenue not represented.
