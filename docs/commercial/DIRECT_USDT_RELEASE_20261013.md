# EmpireOS direct USDT checkout release — 13 October 2026

Scope: four already conditionally approved USD-priced one-time products; settlement is
**DIRECT** BSC USDT, not the unreleased escrow smart contract. No other products.

## Evidence verified against LIVE EmpireOS

- EIP-191 address-control receipt privately stored for
  `0x1339b487046B0ad924a10c20b1791608EA8595a8`. This proves EOA
  control at signing time, not corporate beneficial ownership.
- Existing DB `empire_payment_approver_login` and
  `empire_escrow_verifier_login` received the exact two database CONNECT grants.
  Actual SCRAM and cross-role isolation PASS (founder terminal, 13 October).
- Real `scripts.inspect_self_serve_payment_activation --probe-chain`
  with ONLY ephemeral, public `BSC_RPC_URL` and verified public treasury address:
  `BSC_PREFLIGHT_PASS`, chain verified, fresh block, correct token decimals,
  0 DB writes. Official BNB Chain public RPC used only for chain reads.
- Existing checkout service healthy; live payment/order flags remain OFF.
  Systemd base unit AND the existing `20-empiredb-reader.conf` force the
  payment proposal gate OFF. Current live checkout is DIRECT, BSC_CONFIG_MISSING.
- No local node or extra storage required for read-only BSC JSON-RPC.
  Public endpoints are rate-limited and disable `eth_getLogs`; the
  direct receipt verifier uses `eth_getTransactionReceipt` instead.
- This staging worktree is NOT a live config deployment or role provisioning.

## New release artifact

`deploy/systemd/30-direct-bsc-readonly.conf` is STAGED ONLY, not installed.
It contains only a publicly verified wallet, official BNB public RPC and the
12-confirmation setting, with BOTH consequential order/payment flags OFF.
Do not replace the existing root-owned .env files or bypass unit override
precedence. Deploy only with a reviewed backup, daemon reload and service
readback, as a separately authorised bounded infrastructure change.

## Critical DIRECT-ONLY role gate

The existing two-operator release provisions a payment approver and ESCROW
verifier, NOT the separate `empire_bsc_verifier` required for DIRECT token
payment evidence. Earlier production inspections recorded zero login members
for `empire_bsc_verifier`; current state is NOT independently rechecked yet.

Run from this worktree as the server operator, **read-only**:

```bash
cd /var/tmp/empire_direct_usdt_release_20261013
sudo -n -u postgres /srv/empire_os/.venv/bin/python \
  -m scripts.inspect_direct_bsc_verifier_readiness --preflight
```

Its exact safe readout checks `pg_catalog` only: correct NOLOGIN function
role, app privilege isolation, exactly one noninheriting direct-verifier LOGIN
member, dedicated HBA SCRAM, database CONNECT-only privilege and no
unrecognised role memberships. No password or financial RPC is used.
If `DIRECT_VERIFIER_LOGIN_NOT_PROVISIONED`, require independently approved
least-privilege third login, dedicated protected passfile, actual password
authentication, role isolation and an assigned human verifier. Do not
borrow the escrow verifier or application login and do not auto-provision.

## Financial launch remains held

Before turning flags ON, independently prove fresh chain reads, production
operator identities and authentication, dedicated direct verifier, customer
terms/consent, human approver assignment, payment approval and genuine BSC
receipt verification. Keep payment instructions hidden while a request is
pending. No fake buyer/USDT transfer/settled order or claimed revenue.
No production restart, new role, wallet signing, SQL migration or switch
change is performed by this release.
