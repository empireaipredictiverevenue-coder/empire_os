# EmpireOS — Governed first-party checkout to existing BSC USDT escrow bridge

**Engineering date:** 12 October 2026 (UK).
**Scope:** four existing verified fixed-price intelligence products only. Founder previously approved their conditional BSC USDT payment activation; **no repeated founder pricing or checkout approval required**. This is an implementation of the *existing* 17 September escrow system, not a replacement payment/escrow platform.

## Production truth / contracts inspected

- Live checkout catalog has exactly four eligible one-time product codes: `competitor_search_gap` ($199), `search_opportunity_map` ($249), `technical_search_audit` ($299) and `solar_opportunity_map_us` ($299).
- Existing BSC escrow contract `contracts/escrow/contracts/EmpireBscUsdtEscrow.sol` is built and locally tested; existing `empire_os/bsc_escrow_verifier.py` checks on-chain creation/funding/release/refund events, runtime code SHA-256, escrow ID, amount and token transfer provenance.
- Existing `empire_os/payment_governance.py` already exposes **`build_escrow_proposal`**, **`submit_payment_proposal`** and SQL RPC **`propose_bsc_escrow_request`**. Existing sovereign EmpireDB schemas have `bsc_escrow_agreements`, `bsc_escrow_evidence`, `bsc_payment_requests` and `bsc_payment_evidence`. No schema migration was necessary.
- `empire_os/payment_role_transport.py` and `scripts/escrow_verifier.py` already implement independent payment approver / escrow verifier transports. DO NOT put their DSNs in the public checkout service.
- Current live roles `empire_payment_approver` and `empire_escrow_verifier` are NOLOGIN and have **zero member login identities**; the new read-only gate independently reproduced `escrow_operator_roles_unprovisioned`. Role creation is **not** missing: operational provisioning is.
- `docs/BSC_ESCROW.md` explicitly says **no BSC mainnet escrow deployment**. No approved contract address, beneficiary fingerprint, third-party smart-contract security audit, source/explorer verification, operator roles or mainnet create/fund/refund/release proof has been established.
- The historic legacy receiving-wallet default `0x1339b487046B0ad924a10c20b1791608EA8595a8` is **not** a verified production escrow beneficiary, contract address, signer, operator identity or runtime config. Its source and limitations were recorded in the previous treasury provenance packet.

## Integration implemented — reuse instead of rebuilding

The checkout now supports **server-selected** `EMPIRE_SELF_SERVE_SETTLEMENT_MODE` equal to `direct` (previous behaviour, default) or **`escrow`** (new explicit opt-in). It does not let the customer choose an unapproved mode. Invalid mode fails closed.

A buyer's accepted terms hash and the canonical fulfilment order's `commercial_payload` now bind the selected settlement mode, preventing replay of an escrow order as a direct payment or vice versa.

When escrow mode is explicitly configured, the existing checkout must pass all these controls **before the first buyer or accepted order database write**:

1. Both existing `EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=ON` and `EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=ON` approvals, plus distinct explicit `EMPIRE_SELF_SERVE_ESCROW_MAINNET_APPROVED=ON`; unset/OFF remains held.
2. Explicit, non-zero, valid `BSC_RPC_URL`, `BSC_ESCROW_CONTRACT`, `BSC_ESCROW_BENEFICIARY`, pinned `BSC_ESCROW_RUNTIME_SHA256`, canonical BSC USDT contract, and at least 12 confirmations for later evidence.
3. **Read-only BSC chain proof**: chain ID 56; fresh canonical block; 18-decimal canonical USDT; deployed escrow code matches pinned SHA-256; existing contract's `beneficiary()` matches configured beneficiary; `token()` matches canonical BSC USDT; `paused()` is false. These selectors were computed from the existing contract ABI. No contract is deployed, called with mutation, signed or funded by this proof.
4. **Read-only sovereign EmpireDB role proof**: both `empire_payment_approver` and `empire_escrow_verifier` are present as segregated NOLOGIN/NOINHERIT permission roles, each with at least one member login identity. This read uses the existing ordinary app DSN and never accesses the dedicated financial operator credentials.
5. Existing `prepare_checkout_order` verifies catalogue price, acquisition/fulfilment cost bases, margin, explicit terms and payer wallet, and creates an idempotent, mode-bound order.
6. Existing `build_escrow_proposal` → `submit_payment_proposal` → **`propose_bsc_escrow_request`** creates a governed **pending** escrow-mode request with exact buyer/order/terms/beneficiary/baseline block/amount and an idempotency key. This is **not** an automatic on-chain escrow creation.
7. No customer payment or wallet instructions are returned for a `pending` escrow request. Even an independently `approved` escrow request returns `INDEPENDENT_ESCROW_CREATION_PROOF_REQUIRED`, no treasury address, no amount-to-send and `escrow_creation_verified=false`. The separate existing `EscrowCreated` verifier and record role remain the only route to funded escrow. Neither funding escrow nor a governance proposal is recognised revenue.
8. An existing-order retry never silently re-proposes a request with a new block anchor/expiry (those are immutable SQL terms); it returns `REVIEW_EXISTING_PAYMENT_REQUEST` with no money instructions. There are no synthetic customer/order rows.

Direct USDT mode is preserved but never substituted when escrow was selected, and its prior binding-order/payment configuration gates remain in place. Four-product allowlist, max $299, no outbound, no payment processor, no new roles/timer/runtime, no migration.

## One-shot read-only operational inspection

`./.venv/bin/python -m scripts.inspect_self_serve_payment_activation`

The existing inspector now reports selected settlement mode, redacted configuration status, escrow deployment admission and last relevant network proof. Optional `--probe-chain` performs only BSC JSON-RPC **read** methods after actual mainnet config and authority exist. It **never enables checkout, creates orders, submits payment proposals, grants roles, signs transactions, or sends funds**.

## What is and is not live

The existing public **sales enquiry paths** remain live for customers to request founder proposals. The existing public checkout remains default **direct mode**, with binding-order and payment-proposal switches OFF. The new **escrow mode is code-complete behind independent mainnet deployment and role gates**; it has not been activated. Current first-party BSC RPC and verified live escrow deployment remain unavailable. No mainnet escrow address, bytecode attestation or beneficiary is invented.

**Remaining genuinely actionable dependencies:** external security audit and independently reviewed mainnet contract deployment; pinned runtime contract hash plus proof of beneficiary, role owners, constructor terms and paused state; first-party BSC RPC; provision separately governed approver/verifier role member logins and isolated operator DSNs; bounded on-chain create/fund/refund/release validation and monitoring; exact activation readback. These are *not* additional pricing approvals.

**Operator safety:** any failed gate returns a safe 503 **before accepted order creation**. No payment requests, funds or on-chain transactions have been created in this release. No product catalogue changes, new DB objects or Lead Smart changes. Preserve the live sales funnel while the escrow prerequisites are completed.


## Production activation readback — 12 October 2026 (UK)

**Released source:** `148a52a3`, fast-forward on `agent/data-cloud-wave4`, nine bounded files. Protected 146 other-agent files at promotion, zero overlaps, no Git conflicts; rollback ref `refs/heads/backup/pre-checkout-escrow-bridge-20261012`. Subsequent concurrent nonrelease file changes are separately owned.

- Final cross-business isolated regression: **284 passed** (one pre-existing Starlette/anyio deprecation warning). Postmerge production focused regression: **92 passed**. There were no failed tests.
- A single scoped restart of `empire-self-serve-checkout.service` loaded the guarded bridge, while both existing exact binding-order and payment-proposal systemd flags remained **OFF**. Service: `active/running`, `Result=success`, `NRestarts=0`. Public Gateway and Founder CRM remained active with no restart.
- Checkout HTTP health readback: `checkout_settlement_mode=direct` (existing default), `escrow_creation_automated=false`, `bsc_payment_configuration_status=BSC_CONFIG_MISSING`, `binding_order_creation_authorized=false`, `payment_proposal_authorized=false`, `payment_execution=false`, `revenue_recognition=false`.
- First-party, **read-only** sovereign EmpireDB role preflight from the new bridge returned `escrow_operator_roles_unprovisioned`. No login roles, memberships, secrets, payments or buyer records created.
- Public site `/`, `/buy`, `/commercial`, `/predictive-revenue` and `/roofing` all HTTP **200**. Public self-serve catalog retained exactly **4** verified products with $199/$249/$299/$299 prices, zero unavailable. Founder-led enquiry catalogue retained **10** nonbinding offers.
- Revised one-shot inspector `scripts.inspect_self_serve_payment_activation` returns schema `empire.self-serve-bsc-payment-activation-preflight.v2` and `BSC_PAYMENT_ACTIVATION_HELD`, reason `BSC_CONFIG_MISSING` for current default direct mode. It never activates funds or orders. Explicit escrow-mode readiness additionally demands a deployed runtime contract proof, unpaused canonical token/beneficiary and read-only approver/verifier role memberships.
- The **conditional four-product payment activation approval is still recorded**, never invalidated or repeated. **Escrow-mode production activation is NOT claimed**: no mainnet escrow contract deployment, verified beneficiary, dedicated operator logins or complete on-chain escrow lifecycle evidence. Payment flags remain OFF and sales enquiries remain live. The exact next independent work is mainnet deployment/security evidence plus least-privilege role provisioning, not another escrow build.
