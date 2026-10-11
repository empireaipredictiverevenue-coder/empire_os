# Empire AI — Four-product BSC checkout conditional approval and fail-closed preflight

**Date:** 11 October 2026 (UK)
**Founder approval:** Explicitly approved activating **binding order creation and USDT-on-BSC payment requests** for exactly these previously verified products, **conditional on successful final system preflight and customer consent/terms**:
- `competitor_search_gap` — $199
- `search_opportunity_map` — $249
- `technical_search_audit` — $299
- `solar_opportunity_map_us` — $299

**Do not request the founder to approve this exact four-product scope again.** Approval is recorded; its conditions are not satisfied yet. Not approved: unrelated products, Stripe/cards, other chains, paid traffic, outbound, unverifiable fulfilment, migrations or role provisioning, automatic financial approval, or revenue recognition.

## Live production truth (read-only)

1. Checkout `empire-self-serve-checkout.service` active and healthy, canonical EmpireDB catalogue has exactly four eligible verified one-time products (prices above). Neither checkout activation flag has been enabled:
   - `EMPIRE_SELF_SERVE_BINDING_ORDERS_AUTHORIZED=OFF`
   - `EMPIRE_SELF_SERVE_PAYMENT_PROPOSAL_AUTHORIZED=OFF`
2. The existing checkout worker process has **no `BSC_RPC_URL` or `BSC_TREASURY_ADDRESS`**. The two canonical local deployment configuration files `/etc/empire_os.env` and `/etc/empiredb.env` also have no definitions for these. Therefore `BscUsdtConfig.from_env()` fails **before reading a mainnet block**, and no valid payment request can be constructed without inventing a treasury.
3. A read-only, explicitly non-mutating transaction against sovereign EmpireDB verified `get_commercial_product_catalog` and `propose_bsc_payment_request` callable by `empiredb_app_login`, but **not** `approve_bsc_payment_request` or `get_bsc_payment_request_review`. This is intended separation of financial authority.
4. The payment-role catalog shows both `empire_payment_approver` and `empire_bsc_verifier` **NOLOGIN/NOINHERIT, zero member login identities**. Their role-owned payment review/verification paths are **not operationally provisioned for independent approver/verifier execution**. No grant or credential was changed.
5. Current canonical live table counts: `fulfilment_orders=0`, `bsc_payment_requests=0`, `bsc_payment_evidence=0`. Orders/payments/revenue runtime observer (22:34 UTC) reports `current_transaction_row_count=0`, status `VERIFIED_RUNTIME`, mode `OBSERVE` — **this proves controls exist, not that payment settlement has occurred**.
6. Another pre-existing issue: the checkout returned treasury + "send USDT" wording for a payment request that may still have SQL status `pending`, before independent role approval. The same HTTP route previously created an accepted fulfilment order before checking whether on-chain anchoring would succeed.

## Completed narrow engineering fix (no new payment stack)

Existing checkout was enhanced only in the bounded release with:
- A safe, read-only BSC mainnet chain/head and canonical 18-decimal USDT precision preflight **before any buyer or order row can be written**. It rejects missing/invalid treasury, chain mismatch, RPC timeout and stale/future block.
- `/health` and catalogue report a redacted BSC config state; even if both operator switches are ON, missing/invalid BSC config keeps `binding_order_creation_authorized=false`.
- An existing-order idempotent replay returns the **original previously validated payer wallet** for payment-request retry; not a second order.
- Payment request `pending` no longer includes treasury address/amount instructions, and the website explicitly says **do not send funds** until separate approval. Only a dedicated `approved` request receives payment instructions.
- A one-shot first-party **read-only** task-monitor inspection script:
  `./.venv/bin/python -m scripts.inspect_self_serve_payment_activation`.
  Optional `--probe-chain` reads mainnet chain, block and token decimals once after approved node configuration; never sends funds, writes DB or creates orders.
- Existing catalogue, sales enquiry, Lead Exchange, Predictive Revenue and CRM paths remain separate and live. No new timer/daemon/CRM, database migration, third-party payment processor or synthetic financial event.

## Release-gate matrix

| Condition | Live evidence | Gate |
|---|---|---|
| 4 exact products, current price, verified catalogue | PASS | Permitted scope recorded |
| Founder conditional activation approval | PASS | Do not repeat approval |
| Explicit buyer terms/wallet input and idempotency | Code/tests verified | Per-buyer before order |
| Canonical BSC mainnet RPC endpoint | **MISSING** | HARD HOLD |
| Verified BSC treasury address | **MISSING** | HARD HOLD |
| Fresh chain block and 18-decimal canonical token | **NOT TESTABLE** without RPC | HARD HOLD |
| Independent payment approver/verifier role transport | **NOT PROVISIONED** (NOLOGIN + 0 login memberships) | HARD HOLD |
| Approved payment request and payable transfer instructions | No requests yet, pending must not be payable | HOLD |
| Actual USDT payment and fulfilment proof | Zero canonical rows | Never infer revenue |

**Final decision:** `FOUNDER_APPROVED_PRECONDITIONS_MISSING`; production payment switches remain OFF. This is a specific dependency hold, not a request to re-approve prices or rebuild sales.

**Required to complete:** (1) first-party, trusted BSC mainnet JSON-RPC endpoint/verified runtime binding; (2) founder-verified treasury wallet address (do not invent, log or echo private keys); (3) separately governed and verified approver/verifier login transport, least-privilege and restore evidence; (4) single bounded zero-write chain readback + approved role check; (5) flip two switches for four codes only, read-back, verify without creating a fake purchase. Actual customer-submitted order and verified settlement are subsequent independent events.

**Safety:** Any missing dependency keeps public order admission unavailable. No production funds moved, payment requests created, or accepted orders manufactured during this preflight. The existing public founder-led sales enquiry funnel remains live and independent of payment readiness.

## Production guard deployment and readback — 11 October 2026

- Production guarded-checkout commit: aab57c46. Rollback ref: refs/heads/backup/pre-bsc-selfserve-preflight-20261011. All 146 other-agent files preserved; master checklist unchanged.
- Existing checkout service restarted once, active/running, Result=success, NRestarts=0. Public gateway and founder CRM remain active/running. Both consequential payment switches remain OFF.
- Checkout health: BSC_CONFIG_MISSING, binding_order_creation_authorized=false, payment_proposal_authorized=false, payment_execution=false, revenue_recognition=false; founder-led interest remains enabled.
- Live public checkout catalog returns four exact verified product prices ($199, $249, $299, $299); public /buy, /commercial, /predictive-revenue and /roofing all returned HTTP 200.
- Narrow static export: 23 allowlisted buy/hashed asset paths checked, nine files promoted atomically with rollback manifest /var/tmp/empire_bsc_buy_site_backup_20261011/manifest.json. No other page families changed. Pending payment requests do not display funds-transfer instructions in the new buy UI.
- Tests: 187 cross-business passes and 31 post-merge passes. Next.js production static export with TypeScript compiled. No failures; one existing Starlette/anyio deprecation warning.
- Immutable mode-0600 runtime evidence receipt: runtime/execution_plane/self_serve_payment_activation_approved_held_20261011.json. Read-back verified. Founder reapproval required=false; payment activation state APPROVED_HELD_BY_VERIFIED_PRECONDITIONS; payment authority=none.
- Read-only EmpireDB transaction verified approver/verifier roles are NOLOGIN, each with zero login memberships. Canonical fulfilment orders, BSC payment requests and payment evidence: zero rows. No permissions, credentials, payment requests, treasury funds, or contracts changed.
- Next preconditions: verified first-party BSC mainnet RPC; founder-verified treasury address; separately governed dedicated approver/verifier identities; fresh chain/token/role proof. Only then enable exact two flags for four products. Do not fake buyer orders or repeat the price/activation approval.

## Found existing BSC receiving-wallet candidate — 11 October 2026

The founder confirmed a BSC USDT wallet address is **on file**, rather than requesting a new receiving wallet. A read-only repository and sovereign EmpireDB inspection found the following exact historical source:

- `empire_os/payout.py` at line 20 defines `BSC_WALLET = os.getenv("BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8")`. The file was restored in Git history on 15 September 2026, commit `ab9a9ce6`.
- This address is syntactically a valid nonzero 20-byte EVM address, and distinct from the canonical BSC USDT token contract. The old `pay_invoice` function returned it as a receiving wallet in a legacy `pending_reconciliation` invoice flow.
- **Crucial provenance limitation:** the literal is a *historical fallback default*, not an authenticated payment treasury configuration. Neither `BSC_WALLET_ADDRESS` nor `BSC_TREASURY_ADDRESS` is configured in `/etc/empire_os.env` or `/etc/empiredb.env`. Read-only EmpireDB payment/escrow treasury-address lookup yielded no exact match. Independent proof that the founder controls this address is not yet recorded.
- The legacy `payout.py` references a public Binance RPC fallback, but **this was not adopted** as an EmpireOS first-party service endpoint. No local BSC node or own JSON-RPC listener was observed in the checked service inventory. The 2 October BSC rail convergence policy explicitly prohibits legacy executables from poll/transaction/invoice payment activities; use only the canonical verifier.
- New immutable mode-0600 evidence receipt: `runtime/execution_plane/legacy_bsc_treasury_candidate_discovery_20261011.json`. It identifies the exact candidate and source SHA-256 while explicitly marking `founder_wallet_ownership_independently_verified=false`, `execution_authority=none`, and `funds_moved=false`.
- **Updated honest blocker wording:** "No wallet address exists" is false. **A historical candidate exists**, but the approved treasury identity has not yet been proved/loaded into canonical checkout configuration. The BSC RPC and independent role-operation gates remain separately unresolved. Do not ask the founder for the address again or auto-switch on payments based on this old default.
- Checkout HTTP health was reread after candidate capture: `BSC_CONFIG_MISSING`, `binding_order_creation_authorized=false`, `payment_proposal_authorized=false`. Public sales enquiries remain live. Zero DB or funds changes were made.

**Next proof:** verify founder control of the found candidate with a wallet-controlled signature or equivalent authoritative first-party wallet evidence, then place the verified public receiving address in governed runtime config, establish a first-party BSC mainnet read path and operational separate approver/verifier identities, and repeat the existing one-shot zero-write chain preflight before activating payment collection.
