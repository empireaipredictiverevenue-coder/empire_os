# Empire AI — authenticated direct-USDT buyer payment-status handoff
13 October 2026 · SECURITY RELEASE CANDIDATE · NO ACTIVATION

## Verified facts

- Production checkout is DIRECT BSC USDT, online, configured for a validated
  BSC RPC and approved public treasury address. Four catalog products active
  as metadata; order and payment proposal switches OFF.
- Existing `bsc_payment_requests` contains order/buyer, settlement mode,
  treasury, amount, terms SHA-256, approval actor/time, status, request expiry.
  Existing `bsc_payment_evidence` contains one unique request, one unique
  fulfilment order, transaction hash, token, chain, beneficiary and >=12
  confirmation evidence. Both tables are in sovereign EmpireDB.
- Public /buy presently receives a pending response, and there is no
  authenticated later-payment approval retrieval API. An order UUID,
  payment request UUID, email address or payer wallet is NOT authentication.

## Code completed, tested offline

`empire_os/direct_bsc_buyer_status.py` implements a narrow *pure security
contract*, not a public route or a database writer:

1. One-time random 256-bit buyer capability with `ecs1_` prefix. It contains
   no order, buyer, payment or wallet identity and is never intended for URLs.
2. Persist only HMAC-SHA256 capability fingerprint with a separate root-only
   >=256-bit key, issued/expiry times and order binding, max 48-hour lifetime.
   This is not passwordless email login or recoverable via a guessed UUID.
3. Exact constant-time token-digest comparison, revocation, expiry and order
   binding before status evaluation.
4. A payment request must match the persisted request binding, order, buyer,
   direct settlement mode, treasury, the original payer wallet, the exact
   order-cent value expressed as USDT, and immutable terms fingerprint.
5. Pending/cancelled/expired statuses NEVER reveal transfer amount or wallet.
   An approved request additionally needs a non-future recorded human approver,
   approved timestamp within the offer window, and valid USDT amount.
6. Recorded evidence must match request+order, canonical BSC token, chain 56,
   treasury, commercial terms, and at least 12 confirmations. This is a
   projection of canonical recorded evidence, NOT an independent live chain
   reorg/finality proof.
7. Generic denial `payment_status_unavailable`. No payment capture, secret
   exposure, order creation or runtime switch change.

Offline regression: 96 passed across buyer access, public order ingress,
existing self-serve payment API/readiness, public predictive interest admission,
and separated role transport. These tests DO NOT prove a live payment.

## Must exist before deploying any public status endpoint

The following are **a schema / permission proposal, not migration approval**:

- A new minimal canonical EmpireDB binding table with UNIQUE
  `token_fingerprint`, exactly one `fulfilment_order_id`, nullable single
  `bsc_payment_request_id`, `issued_at`, `expires_at`, `revoked_at`.
  Hard FK constraints; enforce one active capability per order and disallow
  changing the order after issuance.
- A dedicated least-privilege PRIVATE status-reader contract. Verify the
  authenticated token fingerprint BEFORE querying order/payment/evidence.
  Enforce exact row-bounded SELECT and no money-mutation grants. Do not
  expose existing broad app permissions, schema tables or HMAC key to JS.
- Atomic binding issuance WITH order creation and request association, or
  fail closed; handle idempotent retries without ever returning somebody
  else's token or issuing two concurrent active capabilities.
- Token delivery exactly once via same-origin private POST response, never
  query params, referrers, analytics, error logs or localStorage. Keep in
  memory during the open checkout session. For lost session use separate
  verified first-party professional mailbox identity recovery, not customer
  personal data in a GET URL.
- Status retrieval via first-party `POST` with token in JSON body, exact
  Origin/fetch-site validation, no-store headers, very tight request size,
  rate limiting behind Cloudflare Tunnel, no sensitive response on error.
  Do not deliver wallet to browser if request is not HUMAN APPROVED.
- Independently verify public reverse proxy has loaded the previously
  committed ingress hardening (`dc4238ff`); it is NOT currently verified
  deployed. Confirm ingress client identity and practical rate limits.
- Payment correctness remains independently gated by the actual BSC
  transaction receipt, 12 confirmations, atomic unique tx-hash reservation,
  replay denial, refund/expiry policy, audit trail and human operator identity.
- Security/recovery exercise must cover HMAC key rotation, lost bearer tokens,
  revocation, service outage, malicious replay, DB compromise simulation,
  privacy retention and customer support.

## Release authority

No database migration, checkout/frontend changes, public gateway restart,
new login, new credentials, live buyer transaction, USDT, payment approval,
or activation switch is part of this isolated code change.

Existing founder approval for direct BSC RPC deployment and verifier identity
is not permission to apply new schema, launch a new public endpoint, or
enable binding payment orders. Production gates remain OFF.

Next engineering step: inspect canonical schema and design the smallest
bounded migration/reader with independent access-control tests. Then obtain
specific founder approval before any migration or service restart.
