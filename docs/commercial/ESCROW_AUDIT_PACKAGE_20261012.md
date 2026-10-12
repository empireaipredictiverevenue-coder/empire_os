# EmpireOS — Reproducible BSC Escrow Audit and Deployment Review Package

**Prepared:** 12 October 2026. **Production objective:** activate only the four previously approved fixed-price intelligence products on BSC after verification. **Status:** OFFLINE ARTIFACT PREPARATION COMPLETE; external audit, operator provisioning, mainnet deployment and actual settlement remain unverified.

## What is now completed

The existing `EmpireBscUsdtEscrow.sol` is reproducibly compiled **without deploying or signing anything**. `scripts/build_escrow_audit_package.py` generates a deterministic, mode-0600, immutable-on-create tar.gz review archive with:

- The original contract source, Solidity tests, Hardhat configuration, package.json and exact dependency lockfile.
- The actual Hardhat ABI, creation/runtime template bytecode, compiler input JSON and compiler output JSON, including OpenZeppelin dependency sources and settings.
- Pinned Solidity version **0.8.34+commit.80d5c536**, optimizer enabled / 200 runs, `evmVersion=cancun`, target BSC chain ID **56**, and canonical BSC USDT `0x55d398326f99059ff775485246999027b3197955`.
- The seven constructor arguments, in their **exact original ABI order**: token, beneficiary, initial administrator, requester, arbiter, pauser, decision delay.
- SHA-256 of every source, compiler input/output and bytecode, plus all 3 constructor immutable-reference slot groups.
- Explicit redacted authority summary: no external audit, no deployed contract, no verified role ownership, no approved funds, no payments or revenue.

The tool cross-checks current contract source against the *actual compiler input*; checks ABI and constructor signature; requires exact optimizer, compiler and EVM profile; requires artifact bytecode to match compiler output; refuses altered immutable slots; creates output with exclusive-create semantics and **refuses to overwrite an existing package**. Identical source+commit input produces byte-identical archives. Tests prohibit private-key, mnemonic, `.env`, or node_modules inclusions.

**Important immutable-bytecode distinction:** SHA-256 of the local *runtime template* is **not** the deployment's runtime fingerprint because constructor immutables modify on-chain deployed code. A legitimate mainnet release must independently fetch `eth_getCode` from the verified contract address *after the actual creation transaction* and bind its actual SHA-256 to the audited deployment. Do not pin this manifest's template hash as a deployed-contract hash.

## Observed real build evidence

- Local isolated compile using the existing pinned Hardhat/compiler: PASS. Compared to the existing production compile, the **Solidity source hash and creation-bytecode SHA-256 match**.
- Creation bytecode length **11,622 bytes** and SHA-256 **`a56ddb2315674ad3f88420122140435018ff05c7ce7e2bcd6b905b63d2b2d5d4`**.
- Local runtime bytecode template length **10,162 bytes**, SHA-256 **`43509ac22ad95a696f5bd98a09c7a2fbb9506c5b44bb48fb112f76315352cab1`**, **NOT** a mainnet runtime fingerprint.
- The immutable-reference map contains exactly **3 slot groups**.
- First verified immutable review archive on the server:
  `/var/tmp/empire_bsc_escrow_review_bundled_20261012.tar.gz`.
  Initial package SHA-256: `798117c5fdcf6cbafe180909ed641225b0edce71c8e3a40826348706c811305a`.
  Archive contains 9 entries and is approximately 283 KB compressed.
- New packaging regression: 9 passed. Previous escrow Solidity gauntlet: 13 passed. Prior cross-business escrow and sales regression: 332 passed. These are not an independent security assessment.

## Release commands and conditions

A future reviewer may run, in the existing EmpireOS repository after `npm run compile` in `contracts/escrow`:

`./.venv/bin/python -m scripts.build_escrow_audit_package --output /var/tmp/empire_bsc_escrow_review_fresh.tar.gz`

The archive is fixed and contain no passwords, keys or DSNs. Distribute only to the expressly approved security reviewer. Do **not** upload to a payment provider or share private operational config.

**Still required to launch safely:** independent, appropriately scoped Solidity smart-contract review and accepted findings; evidence of control of beneficiary, separate administrator/requester/arbiter/pauser public addresses and exact decision delay; a first-party BSC RPC and contract-creation transaction evidence; verified `eth_getCode`, role-grant history, non-paused and solvent escrow; separately provisioned independent operator logins; BNB gas for approved mainnet deployment/rehearsal; audited on-chain create/fund/refund/release proof and incident/rollback plan. Four-product founder commercial permission remains granted but **is not authority for these financial actions**.

Existing /commercial and /buy enquiry/catalogue availability continues. Neither payment flag nor escrow mainnet activation flag was enabled. No database mutation, customer record, money transfer, deployment, outbound or production service restart was performed as part of this package.

**Next owner:** Security/deployment reviewer and separately approved financial operator provisioning. Do not rebuild escrow, checkout, role-history replay, or this reproducible compilation step.
