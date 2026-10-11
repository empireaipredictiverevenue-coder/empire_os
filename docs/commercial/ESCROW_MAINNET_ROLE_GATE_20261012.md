# EmpireOS — BSC escrow mainnet role and backing admission gate

**Date:** 12 October 2026, UK. **Scope:** extend the already-merged checkout-to-existing-escrow bridge; do not build a second escrow or payment runtime. The founder's conditional approval for the four verified one-time intelligence products remains recorded. No automatic or synthetic financial authority.

## Source-of-truth recovery

- Existing production checkout is `empire-self-serve-checkout.service` on 127.0.0.1:8098, currently **direct**, both binding-order and payment-proposal flags **OFF**, and explicit escrow mainnet opt-in **absent**.
- `contracts/escrow/contracts/EmpireBscUsdtEscrow.sol` on Solidity 0.8.34 and pinned OpenZeppelin 5.6.1; local `npm test` on 12 October produced **13 passing tests**; `npm audit --omit=dev --audit-level=high` produced zero runtime dependency vulnerability findings. Neither proves an independent smart-contract audit or production deployment.
- Compiled artifact: `contracts/escrow/artifacts/contracts/EmpireBscUsdtEscrow.sol/EmpireBscUsdtEscrow.json`. It contains constructor-specific immutable references. **The local deployedBytecode hash must not be represented as the on-chain deployment's runtime code fingerprint.** The canonical on-chain SHA-256 is still unavailable because no approved mainnet deployment has been proved.
- Existing EmpireDB role `empire_payment_approver` and `empire_escrow_verifier` are separately permissioned NOLOGIN roles, zero operative member logins in latest read-only catalog. Existing role transport and escrow verifier code are reused; payment credentials are not added to public checkout.
- Legacy payout wallet address remains a provenance-only candidate, not proof of beneficiary ownership, deployed contract, contract administrator, arbiter, pauser or requester.

## New one-hit production admission checks

`empire_os/escrow_mainnet_role_readiness.py` reads only the already deployed contract through the configured first-party BSC JSON-RPC. It supplements, never replaces, `verify_escrow_checkout_contract` (chain 56, canonical USDT, current block, pinned runtime code SHA-256, beneficiary, token contract and unpaused state).

A founder-controlled, independently reviewed deployment record must bind the following public role-holder addresses in the existing governed environment (never private keys or mnemonic):
- `BSC_ESCROW_ADMIN_ADDRESS`
- `BSC_ESCROW_REQUESTER_ADDRESS`
- `BSC_ESCROW_ARBITER_ADDRESS`
- `BSC_ESCROW_PAUSER_ADDRESS`
- `BSC_ESCROW_DECISION_DELAY_SECONDS` (minimum 3600, maximum 604800; exact approved hours must match the contract).

The four role holders must be syntactically valid, nonzero, **pairwise distinct**, and on-chain `hasRole(bytes32,address)` must independently return true for default admin, requester, arbiter, pauser. Read-only `decisionDelay()` must equal the reviewed production policy, and `escrowBacking()` must report a USDT balance no smaller than escrow liabilities. The selectors and role hashes were generated from the existing Hardhat Solidity ABI via ethers.id; they are pinned in the first-party module.

**Important limitation:** `hasRole` verifies these four *expected* holders. It does **not** prove there are no other role-grant recipients. Before BSC mainnet activation an independent review of role grants/revocations and contract event history is required; the inspector explicitly reports `all_role_holders_exclusivity_verified=false` and `role_grant_history_independently_audited=false`.

The existing `/v1/orders` escrow-mode admission now requires: explicit existing dual checkout flags + escrow mainnet approval flag, valid deployed contract configuration, complete holder/delay policy configuration, verified read-only existing contract/token/fresh block/pause proof, verified read-only on-chain role/delay/solvency proof, and independently provisioned sovereign EmpireDB operator memberships, **all before** the first buyer/accepted order write. Any unknown/invalid result yields a redacted 503 and no order, buyer, payment or token transfer.

The existing one-shot `./.venv/bin/python -m scripts.inspect_self_serve_payment_activation` reports which prerequisite failed and whether roles, backing, operator memberships and deployment have been independently verified. Optional `--probe-chain` only performs JSON-RPC reads when approved configuration is present. No additional scheduling system, cron or payment runtime.

## Mainnet release remains independently held

1. A professional external security audit for the exact Solidity source/compiled implementation with explicit accepted findings and supply-chain review is **NOT VERIFIED**.
2. Formal founder-approved mainnet deployment parameters — approved beneficiary custody, four independently controlled role signers, agreed decision delay and contract runtime code hash — are **NOT VERIFIED**.
3. First-party BSC mainnet JSON-RPC, mainnet contract address/bytecode fingerprint, on-chain grant history and an auditor-reviewed production deployment receipt are **NOT VERIFIED**.
4. Dedicated approver/verifier operational login identities, least-privilege role transports and security evidence are **NOT PROVISIONED**.
5. Signed chain create/fund/refund/release rehearsal and bounded monitoring of escrow solvency, pauses, disputes and role changes have **NOT OCCURRED**.

**No mainnet deployment, contract call, token transfer, role grant, wallet change, DB migration, synthetic order or switch activation is authorised by this code release.** Continue collecting genuine buyer-initiated sales enquiries through the already-live public /commercial page. Do not reopen Lead Smart, pricing or the escrow implementation.

To promote mainnet settlement later, the reviewer must supply evidence for each of these exact checks, then execute a separately authorised deployment with rollback/incident plan and perform an independent readback. This document does not constitute an external smart-contract security audit.
