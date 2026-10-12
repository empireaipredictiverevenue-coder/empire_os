# EmpireOS — BSC Financial Operator Exact Database CONNECT Recovery

**Date:** 13 October 2026 (UK), production `agent/data-cloud-wave4`. **Purpose:** repair the last independently discovered PostgreSQL authentication prerequisite for the existing, separately governed BSC financial operators. Reuse existing EmpireDB, role transport, payment governance, escrow engine and first-party mailbox. No platform rebuild, third-party payment processor, SQL migration, live outreach or payment activation.

## Source-of-truth findings

1. Treasury EIP-191 wallet-address control proof for `0x1339b487046B0ad924a10c20b1791608EA8595a8` was previously verified and stored privately.
2. The exact existing NOLOGIN permission roles `empire_payment_approver` and `empire_escrow_verifier` have six required existing SQL RPC permissions. Public `empiredb_app_login` does **not** have direct financial SQL execute rights.
3. Both dedicated LOGIN roles `empire_payment_approver_login` and `empire_escrow_verifier_login` **now exist** with the intended NOINHERIT/non-admin attributes, distinct `SET TRUE, INHERIT FALSE` membership, exact first-match SCRAM HBA rules, and two separate root-only 0600 `.pgpass` files under the root-owned `/var/lib/empire-bsc-payment-operators/` (0700).
4. The previous inspector falsely labelled the role catalog `OPERATOR_IDENTITIES_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED` because it had not checked the database's explicit **CONNECT** ACL. An independent attempt to authenticate as `empire_payment_approver_login` with its actual vaulted credential failed before SQL login with **FATAL: permission denied for database "empiredb"; User does not have CONNECT privilege**.
5. Read-only live `pg_database.datacl` and `has_database_privilege` confirmed the canonical first-party EmpireDB revokes `CONNECT` from PUBLIC, and **neither financial login nor its permission group has CONNECT**, CREATE or TEMPORARY. No PostgreSQL defect or network error: this is an omitted grant in our provisioning transaction.
6. Public checkout `empire-self-serve-checkout.service` remains healthy with binding orders OFF, payment proposals OFF, and no escrow funding/settlement enabled. This recovery cannot enable checkout by itself.

## Exact bounded fix, no guessing

The first-party `empire_os/bsc_payment_operator_readiness.py` now evaluates for each financial login: `has_database_privilege(LOGIN,'empiredb','CONNECT')`, `CREATE` and `TEMP`. It rejects unknown ACL evidence, partial CONNECT grants, unintended database creation/temp rights and unexpected role/HBA privileges.

The original future-login provisioning transaction now also grants the exact needed `CONNECT` on `empiredb` to each newly created login **inside the same transaction** as its independent role/membership creation. This fixes the original omission without creating any additional system or expanding financial RPC rights.

For the **two already-provisioned production logins**, a dedicated recovery CLI `scripts/repair_bsc_financial_operator_db_connect.py` performs a read-only preflight by default. Its sole optional database mutation, with a distinct explicit founder authorisation, is exactly:

```sql
GRANT CONNECT ON DATABASE empiredb TO empire_payment_approver_login;
GRANT CONNECT ON DATABASE empiredb TO empire_escrow_verifier_login;
```

The two grants execute atomically in one PostgreSQL transaction using the existing canonical local 5432 socket. No `CREATE`, `TEMPORARY`, schema, table, financial SQL function, SUPERUSER, role inheritance, password, HBA, service or customer order privilege is added. It does not collect, transfer, approve, verify, release or refund funds.

The recovery requires:
- Correct first-party sovereign EmpireDB (not Supabase), exact role/member/HBA catalog and six SQL permissions, both operator logins **currently lacking CONNECT**, no partial grants, and two existing separate root-owned private passfiles.
- The reviewed repair script must already be committed unmodified to the active repository. A root-only lock prevents duplicate repair runs.
- An independently verified root-only backup of the **original database ACL** under `/var/backups/empiredb/bsc-two-operator-connect/` before modification. Vault secrets never enter logs or backup evidence.
- Exact privileged `GRANT CONNECT` statements, checked catalog after transaction, then two **real PostgreSQL SCRAM password-authenticated sessions**, each exercising only `SET LOCAL ROLE` for its assigned existing financial role and confirming cross-role escalation fails. No financial SQL RPC is invoked.
- If anything fails, return a held state, without blind retries or broad privilege reconfiguration. A database connection privilege grant can later be reversed specifically with `REVOKE CONNECT ON DATABASE empiredb FROM <the exact two login roles>`, after independent catalog reconciliation.

**Read-only production preflight:** from `cd /srv/empire_os`:

```bash
sudo -n ./.venv/bin/python -m scripts.repair_bsc_financial_operator_db_connect --preflight
```

Expected before correction:
`OPERATOR_IDENTITIES_REQUIRE_EXACT_TWO_DATABASE_CONNECT_GRANTS`, `exact_db_connect_grants=0`, status `READY_FOR_EXACT_TWO_CONNECT_GRANT_APPROVAL`. This was verified against current live Postgres without SQL writes.

**Distinct founder-gated actual grant command (NOT run just because the user said continue):**

```bash
sudo -n ./.venv/bin/python -m scripts.repair_bsc_financial_operator_db_connect --apply --approved-exact-two-bsc-db-connect-grants
```

Execute only after explicit founder approval for **these two exact database CONNECT privilege grants**. Previous commercial approval for four fixed-price products and the separately authorised preparation of two login identities does not by itself override this database-privilege gate.

## Independent engineering proof

- **63 focused unit tests** currently pass for role/HBA/DB ACL invariants, preflight-only operation, private credential handling, exact commands, and no cross-role permission widening.
- A fresh disposable PostgreSQL 18 `pg_virtualenv` cluster now explicitly **REVOKEs `CONNECT` from PUBLIC** like production: confirms each existing SCRAM financial login is blocked before the two grants, applies exactly those CONNECT grants, then authenticates both independent accounts successfully, confirms correct `SET LOCAL ROLE`, denies cross-role access, and denies incorrect passwords. Checks neither account receives database CREATE/TEMP rights.
- The ephemeral test never touches production port 5432, production HBA, passwords, memberships, orders or funds.
- The after-grant production authentication, operator assignment and mainnet escrow launch remain **unverified** until the approved grant is performed and independent readback succeeds.

## Unchanged final gates

Treasury address-control proof stays verified, four products/prices remain approved, and buyer-initiated sales enquiry pages continue live. Mainnet escrow contract remains not independently audited or deployed, dedicated human operator assignment not complete, and no on-chain create/fund/refund/release evidence exists. Payment flags stay OFF. This credential repair is **not** authority to enable live USDT checkout or deploy a contract.
