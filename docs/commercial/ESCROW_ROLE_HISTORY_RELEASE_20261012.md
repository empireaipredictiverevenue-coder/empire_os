# EmpireOS — Read-only BSC escrow deployment and role history proof

**12 October 2026. Existing escrow and checkout only.**

## Reused production contracts

- `EmpireBscUsdtEscrow.sol` and OpenZeppelin `AccessControlDefaultAdminRules` emit exact `RoleGranted`, `RoleRevoked`, `RoleAdminChanged`, default-admin transfer and default-admin delay schedule/cancellation events.
- Existing `BscEscrowConfig`, `EscrowRoleConfig`, `verify_escrow_checkout_contract`, `verify_escrow_runtime_roles_and_backing` already validate BSC mainnet, canonical USDT, runtime bytecode, beneficiary, pause, expected role holders, decision delay and escrow solvency. This release does **not** replace any of them.
- On 12 October 2026, the existing local Hardhat escrow suite still passed 13/13 tests and `npm audit --omit=dev --audit-level=high` reported no runtime dependency vulnerabilities. Neither is an independent external smart-contract audit or BSC mainnet deployment.
- The existing founder conditional approval for four fixed-price product checkout paths is preserved. Live binding orders and payment proposals remain OFF. No money, buyer record, crypto transaction or permission change is authorized by this inspector.

## Missing security coverage closed in code

Expected `hasRole(role, address)` checks cannot show whether an **extra unauthorized account** was given an administrator, requester, arbiter or pauser role. New first-party **`empire_os/escrow_role_history.py`** reconstructs the initial and subsequent AccessControl role state **from every relevant confirmed log** since an independently specified deployment transaction.

Preflight requires these public **deployment provenance fields**, not secret keys:

- `BSC_ESCROW_DEPLOY_TX_HASH` — reviewed transaction hash of the canonical creation transaction
- `BSC_ESCROW_DEPLOY_BLOCK` — reviewed block number containing creation

It also reuses previously required immutable contract address, runtime SHA-256, four distinct configured role-holder public addresses, approved decision delay, canonical token, beneficiary and first-party JSON-RPC. The deployment receipt must be successful, contract-creation-only, at the exact reviewed block/contract, with canonical matching block hash.

A 12-confirmation-or-greater chain anchor bounds the scanner. It verifies chain 56 and scans exactly contiguous inclusive block windows from deployment through the confirmed height, with a maximum of 100,000 blocks per invocation, 1,000 blocks per log query and bounded logs/query. Missing event ranges, provider error, duplicate/out-of-order events, invalid log ABI, removed logs, unknown grants, role revocations, extra recipients, administration changes or schedule/cancel events and changing chain anchor **fail closed**. It requires exactly four expected role grants made **inside the original contract-creation transaction**. It refuses deployment history that is too old to scan safely in one run; an independently designed archival audit is then required.

The result is explicitly scoped to **the confirmed chain height scanned**, not future grants or audit independence. It never signs transactions, runs ERC20 transfers, creates accepted orders or changes role memberships.

Run the new one-hit CLI:

`./.venv/bin/python -m scripts.inspect_escrow_role_history`

This is configuration-only and performs zero network requests. Only after approved deployment provenance/configuration exists:

`./.venv/bin/python -m scripts.inspect_escrow_role_history --verify-history`

The explicit option performs **read-only** BSC `eth_chainId`, `eth_blockNumber`, `eth_getBlockByNumber`, `eth_getTransactionReceipt`, `eth_getCode`, `eth_call` and `eth_getLogs`. It reuses existing contract code/beneficiary/token/pause and expected role/backing verifiers as prerequisites. It never returns private credentials or commercial contacts. If required configuration is missing it exits with a structured **held** result and makes no RPC request.

**No recurring chain scan on the customer checkout hot path**. A one-shot deployment-readiness receipt must later be independently reviewed, kept fresh, and paired with ongoing role-event monitoring before payments can open.

## Ground-truth remaining financial gates

- No external contract audit report or accepted findings.
- No independently reviewed deployed mainnet escrow contract/creation receipt, code fingerprint, beneficiary ownership, constructor signers or event history. Current checkout escrow configuration is missing.
- No validated independent approver/verifier login memberships and isolated operator transports.
- No completed mainnet create/fund/refund and create/fund/release proof or accounting evidence.
- First-party mainnet RPC unavailable; historic legacy public RPC and payout wallet fallback are **not** silently activated.
- Founder-approved four-product scope does **not** constitute authorization to make a new mainnet deployment, grant operator permissions or move customer funds.

**Release meaning:** Code complete, security-read-only proof available, NOT a mainnet deployment, NOT payment activation, NOT a replacement external security audit. Existing sales enquiries remain live.


## Production code-and-live-preflight proof — 12 October 2026

- Production code-only fast-forward: **2c45d8ff** on `agent/data-cloud-wave4`; exact four new escrow history files, no conflict with 146 concurrently owned uncommitted files, rollback ref `refs/heads/backup/pre-escrow-role-history-20261012`.
- Same-parent production integration regression **332 passed**, postmerge subset **99 passed**. The 16 initial cases were strengthened into **22 new scanner/inspector-focused tests**; the larger integration test numbers include these.
- Safe read-only inspection against live canonical environment: `ESCROW_ROLE_HISTORY_HELD`, reason `ESCROW_MAINNET_CONFIG_MISSING`. Neither a mainnet deployment receipt nor configured live operator addresses exist. This is a **missing-evidence hold**, not an assertion that any on-chain contract failed the checks.
- Checkout and public gateway services remain active; no restart was required because this is an explicit operator-invoked, read-only scanner, not a request or payment hot-path change. No inbound sales or catalogue routes changed.
- Immutable 0600 runtime record: `runtime/execution_plane/escrow_role_history_release_20261012.json`, source SHA-256 and readback verified, financial authority remains none and conditional four-product approval retained.
- **Next evidence required:** audited mainnet deployment receipt and approved role/beneficiary identities before using `--verify-history`. Independently reviewed contract audit and operational role credentials still remain external launch gates. Do not revisit pricing, checkout-to-escrow coding or repeat the role-history implementation.
