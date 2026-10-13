# Direct BSC USDT checkout — third financial operator release
13 October 2026. Production truth first. Independent founder approval required before the two exact changes below.

## Verified production starting point

The read-only direct verifier inspector reports `DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED`.
The existing `empire_bsc_verifier` NOLOGIN permission role has the expected
`get_bsc_payment_request_review` and `record_bsc_payment_evidence` RPC grants.
The ordinary app login does not inherit payment-verifier or approval authority.

The existing independent `empire_payment_approver_login` and
`empire_escrow_verifier_login` have already been provisioned and their missing
database CONNECT grants were repaired, with actual SCRAM and cross-role
denial verified. **Do not repeat or alter those two identities.**

The existing direct checkout is LIVE as an interest/catalogue page only:
`/buy` HTTP 200 and /health online, with order and proposal flags OFF.
The separately approved four one-time product prices remain unchanged.

The read-only direct BSC payment preflight passed with an ephemeral environment
of `BSC_RPC_URL=https://bsc-dataseed.bnbchain.org`,
`BSC_TREASURY_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8`
and 12 confirmations. No extra blockchain storage is needed for chain reads.
These values are **not yet installed into the checkout service environment.**
Public RPC is external, rate-limited and not sovereign hosting.

## Bounded code release

`scripts/activate_direct_bsc_verifier_identity.py` reuses canonical PostgreSQL
18, SCRAM key derivation, the production-proven HBA writer/rollback and the
existing first-party credential vault. It operates only on missing
`empire_bsc_verifier_login`, not any escrow or approver login.

Run read-only preflight first:

```bash
cd /srv/empire_os
sudo -n ./.venv/bin/python -m scripts.activate_direct_bsc_verifier_identity --preflight
```

If the report is `DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED`, current HBA missing
and operator vault safe, the first separately authorised exact infrastructure
change is:

```bash
sudo -n ./.venv/bin/python -m scripts.activate_direct_bsc_verifier_identity \
  --apply-hba --approved-one-direct-verifier-scram-rule
```

It prepends exactly one `local empiredb empire_bsc_verifier_login scram-sha-256`
rule, hashes and backs up the original HBA, reloads PostgreSQL (no restart),
independently checks first-match SCRAM and rolls back if unsafe. No SQL role
or customer transaction is created. It requires **explicit founder consent
for this rule**; previous four-product approval is not this consent.

Only after HBA readback and distinct founder authorisation, the second exact
database/credential change is:

```bash
sudo -n ./.venv/bin/python -m scripts.activate_direct_bsc_verifier_identity \
  --apply-login --approved-one-direct-verifier-login
```

Creates one role with LOGIN NOINHERIT and no admin/CREATE/REPLICATION/BYPASSRLS,
grants exactly `empire_bsc_verifier` with INHERIT FALSE, SET TRUE, ADMIN FALSE
and one database CONNECT grant (no CREATE/TEMP). One new 48+-character random
secret is held only in a distinct root-only 0600 passfile under
`/var/lib/empire-bsc-payment-operators`, preserving both existing passfiles.
An independently SHA-256 checked root-only global-role backup precedes writes.
Actual SCRAM authentication, correct `SET LOCAL ROLE`, cross-role denial and
wrong-password denial must PASS. Any post-commit error HOLDS and must be
reconciled manually: never blindly retry, widen DB grants or remove a role.

**Neither command is pre-authorised by this document.** Source-hash commit
verification, a global lock, current canonical catalog and separated approval
flags are enforced. No escrow contract, chain transaction, USDT payment, order,
customer row, mail or service restart is involved.

## Engineering verification

- Independent pure invariants and denial tests for malformed HBA, duplicate
  rule, base-authority drift, operator mode guard, wrong identity flags.
- `scripts/test_direct_bsc_verifier_ephemeral.sh`: isolated PostgreSQL 18 on
  port !=5432. Proved HBA, SCRAM, no database CONNECT before grant, CONNECT-only
  afterwards, exact verifier role and rejection of other financial roles and
  wrong password. Disposable cluster removed. No production writes.
- Integration tests separately verify all existing payment/escrow contracts.

## Remaining payments-release controls

This step only provisions a verifier identity. Separate human-operator assignment,
a secure operator transport, live customer terms and approval audit, and guarded
configuration deployment still remain. Before activation verify approved requests
never leak transfer instructions while pending, the canonical BSC USDT receipt
matches payer/treasury/value with >=12 confirmations, replay prevention and
idempotency, fulfilment gating and rollback/incident readback.
Do not flip `EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED` or
`EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED` merely because role auth passes.
