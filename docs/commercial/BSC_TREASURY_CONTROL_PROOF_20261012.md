# Empire AI — existing BSC receiving-wallet control proof

**Date:** 12 October 2026. **Founder authorization:** proceed with the next escrow launch dependency. The exact four-product pricing/payment activation approval was already recorded. This is **not** a new authorisation to deploy escrow, provision financial operators, spend funds or enable checkout.

## Existing wallet discovery

- Source: `empire_os/payout.py` contains the historical `BSC_WALLET_ADDRESS` fallback `0x1339b487046B0ad924a10c20b1791608EA8595a8`.
- This is a public **wallet candidate**, not yet a proof of corporate treasury beneficial ownership, current ability to control it, or approved escrow beneficiary.
- The wallet address is not the BSC USDT contract, an escrow smart-contract address or a private key.

## First-party ownership challenge (EIP-191)

The founder can connect an EVM wallet to the self-hosted `https://empire-ai.co.uk/_next/treasury-proof.html` page. The page requires the **exact wallet already recorded**, shows the complete nonce/domain/chain-bound message, and requests only `personal_sign`. It performs **no** transaction, ERC20 approval, wallet switching, signature upload or server-side POST. No third-party API library is downloaded.

The backend-independent verifier `scripts/verify_bsc_treasury_control.mjs` uses the **existing pinned ethers package** from `contracts/escrow/node_modules` and recovers the EIP-191 public signer. It will accept **only** the existing candidate address and the exact `empire-ai.co.uk` signing message with a cryptographically random nonce, chain ID 56, issue timestamp and 48-hour expiry. Invalid, wrong-wallet, altered or expired signatures fail closed.

To issue an immutable, 0600 challenge:
```
node scripts/verify_bsc_treasury_control.mjs challenge /srv/empire_os/runtime/execution_plane/bsc_treasury_control_challenge_20261012.json
```
Render a public non-submitting page from that private challenge:
```
./.venv/bin/python -m scripts.render_bsc_treasury_proof_page --challenge /srv/empire_os/runtime/execution_plane/bsc_treasury_control_challenge_20261012.json --destination /srv/empire_os/apps/empire-public-site/out/treasury-proof.html
```
Once the founder signs, write **only the resulting signature** to a private 0600 file and run:
```
node scripts/verify_bsc_treasury_control.mjs verify /srv/empire_os/runtime/execution_plane/bsc_treasury_control_challenge_20261012.json PRIVATE_SIGNATURE_FILE PRIVATE_PROOF_RECEIPT
```
The signature is not a mnemonic, password or key. Do not print it into shell history or change live payment flags. No role grants, operator login provisioning, smart-contract deployment or funds movement is included.

**One-time challenge limits:** The nonce cannot be overwritten, and its proof expires after 48 hours. If unsigned by expiry, generate a new date-named challenge and replace the stale static signing page via the exact review/backup process, not through an unbounded agent loop.

**Limitation:** EIP-191 `verifyMessage` proves EOA private-key control at signing time only. It does **not** prove legal or corporate beneficial ownership or approval as the escrow beneficiary, nor does it support multisignature smart-contract wallets. ERC-1271 contract-wallet verification requires separate read-only on-chain evidence and an approved RPC.

## Production gateway publication readback (12 October 2026)

The public FastAPI gateway allows only explicit landing-page routes, so `/treasury-proof.html` returns **404** even when staged in `out/`. Do not circulate that unserved path. The already-existing `/_next` StaticFiles route supports external JavaScript and does not require a gateway restart.

The live, externally HTTP-200 verified first-party signing page is:

**`https://empire-ai.co.uk/_next/treasury-proof.html`**

It loads its one self-hosted JavaScript file `/_next/treasury-proof-signing-20261012.js` (HTTP 200) with no third-party SDK or signature submission. The gateway's actual CSP is `script-src 'self'`, so an inline script cannot execute; the staging HTML was deliberately repackaged with a same-origin external script. Content-type, CSP, page/JS hashes and no-payment flags were checked after publishing. This exact instance expires **2026-10-14T09:29:41.560Z**; the HTML must be regenerated through a distinct nonce/expiry review after that, never silently reused.

The challenge is at `runtime/execution_plane/bsc_treasury_control_challenge_20261012.json` (0600). The immutable launch evidence is at `runtime/execution_plane/bsc_treasury_control_signing_release_20261012.json` (0600). Its state is `AWAITING_FOUNDER_SIGNATURE` and **not** `EOA_CONTROL_VERIFIED`. Once the founder supplies a wallet-generated message signature, verify it via the existing `verify` CLI before marking any owner-control proof verified.

## Launch gates unaffected

Even a verified owner signature does not complete the external contract security review, reviewed BSC mainnet deployment, pinned runtime bytecode, administrator/requester/arbiter/pauser identities, segregated Postgres payment operators or actual escrow lifecycle proof. The live checkout's binding-order and payment-request flags remain OFF until those separate conditions pass.

**Engineering scope:** first-party wallet signing UI and verifier only, no unapproved outbound, wallet credentials, paid provider, web API submission, CRM migration or restart. Existing public commercial sales enquiries stay live.
