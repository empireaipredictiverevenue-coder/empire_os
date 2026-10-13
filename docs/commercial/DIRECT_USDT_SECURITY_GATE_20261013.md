# EmpireOS — Direct USDT checkout security hardening, 13 October 2026

## Production truth

- Founder-approved *read-only* BSC RPC and public treasury systemd drop-in was
  installed with backup/readback, chain 56, canonical USDT decimals 18.
- Three distinct SQL financial identities exist (approver, escrow verifier,
  and direct USDT verifier). The direct verifier passed real password auth,
  membership isolation and cross-role denial.
- Checkout /health reports online DIRECT mode, with binding orders OFF,
  payment proposals OFF, payment execution false and revenue recognition false.
- Public /buy HTTP 200 and all four $199–$299 verified catalog items visible.
- The standalone inspect_self_serve_payment_activation script currently lacks
  the checkout *systemd-only* BSC environment when invoked from the operator
  shell; its BSC_CONFIG_MISSING does not override the live service readback.
  Use an ephemeral read-only environment or a dedicated safe service probe.
- Neither a good block read nor the three SQL identities proves that money can
  be safely accepted.

## Security issue found and fixed in source (not deployed)

`empire_os/public_gateway.py` previously forwarded
`POST /v1/checkout/orders` to the internal 8098 order-creation endpoint
without matching the same-origin/rate-limit abuse admission enforced for
adjacent public commercial/predictive requests. After financial gates turn
ON, this exposes the buyer/order write path to cross-site abuse and unbounded
submission volumes.

Bounded patch: fail closed on absent/foreign Origin, disallowed Sec-Fetch-Site,
non-JSON media type, existing shared five-per-minute enquiry limiter and
streamed payload >12,000 bytes. Require existing first-party route and
internal backend. Add Cache-Control no-store on all responses and generic
non-leaking gateway errors. External client-provided forwarded IP headers
are not trusted for rate buckets. Existing conservative reverse-proxy peer
handling still needs real ingress verification to avoid a shared 5/min bucket
unfairly throttling legitimate customers.

The patch uses the existing shared first-party limiter, not a new third-party
gateway, database, queue, scheduler or payment runtime. Existing backend
catalog/economics/chain/approval checks remain unchanged.

Tested using FastAPI TestClient with the internal HTTP destination **mocked**
and without customer/order/finance writes. Tests assert cross-origin denial,
fake JSON content type denial, rate limit, oversize, secret-safe error response,
Cache-Control, legitimate first-party JSON forwarding and response headers.

## Critical blockers BEFORE enabling payment proposals / binding orders

1. **Authenticated payment-status handoff:** public /buy currently shows
   pending approval immediately after request creation but has no follow-up
   retrieval for later human-approved payment instructions. Do NOT add a
   publicly readable `GET /orders/{id}` or `GET /requests/{id}`; UUIDs,
   payer wallet, email address and order ID are not authentication.
   Design a high-entropy buyer-bound checkout capability, persist only
   a keyed hash/fingerprint in sovereign EmpireDB, check strict expiry and
   revocation, bind to a single order/request and approved state, enforce
   constant-time verification, no-store/private cache policy, rate limiting,
   origin controls, and leak-free responses. Implement only after independent
   schema/API review and explicit migration authorization if needed.
2. **Operator separation:** approvals via `empire_payment_approver_login`
   and receipt evidence via `empire_bsc_verifier_login` must be assigned to
   distinct authorised human/privileged processes with root-only secret
   transport. Never expose SQL DSNs to checkout, site, JS or ordinary workers.
   Login exists but human/process assignment remains gated.
3. **Payment integrity:** verify chain ID 56, canonical USDT contract,
   payer/token/recipient/amount, >=12 confirmations, fresh canonical block
   and fixed terms; block tx hash replay, duplicate request, missing receipt,
   stale/reorg proofs and partial transfers. Verify atomic uniqueness and
   fulfilment trigger against the live schema, not mock assumptions.
4. **Internet ingress:** confirm the public gateway rate limiter is
   effective behind Cloudflare Tunnel and does not treat every buyer as one
   indistinguishable peer. Test deployed Origin/fetch checks, CSRF, request
   size, abuse limits, negative/positive smoke without production order writes.
5. **Business and wallet authority:** independently attest treasury is the
   authorised beneficiary, audit terms/refund/expiry disclosures and
   source/version/price/margin before any binding order.
6. **Incident readiness:** secret vault 0700/0600, minimal role privileges,
   tested recovery, monitoring, audit logs without PII/credentials, kill
   switches OFF by default, and operator-controlled rollback.

No funds, login grants, migrations, mainnet escrow, checkout or public gateway
restarts, flags, new schedules or live customer submissions are part of this
source-only change.

## Release status

CODE TESTED, NOT PRODUCTION LOADED. Public gateway service deployment and
restart require separate founder approval and dedicated postrestart proof.
The payment path remains DISABLED. Security gates above are release blockers;
passing this source-level ingress patch alone does not authorise live money.
