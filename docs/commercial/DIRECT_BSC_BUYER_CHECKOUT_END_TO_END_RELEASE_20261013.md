# Empire AI direct USDT/BSC checkout status — final release package
13 October 2026 — isolated checked-in implementation, awaiting exact operator rollout

## Production facts verified without modifying the live environment

- EmpireDB migrations 047, 048, 049 v2 and 050 committed; 049 12/12 and
  050 10/10 postcommit security checks previously passed.
- Founder-executed dedicated two-login provisioning completed with
  `two_login_connections_verified`; follow-up root-only catalog/connection
  and nonexistent-fingerprint verification returned
  `DEDICATED_STATUS_LOGINS_LIVE_READBACK_VERIFIED`, exit 0.
- The four-product checkout is online; founder-approved pending order and
  payment proposal gates are ON. Payment execution / realised revenue OFF.
- New independent READ-ONLY RPC check on 13 October to existing configured
  BSC endpoint verified chain ID 56, canonical USDT contract 18 decimals,
  block anchor fresh (<300 seconds). This is an instant-in-time result,
  **not** proof of a customer transfer or a permanent oracle guarantee.
- No order, customer payment, buyer token or external email was created by
  this integration work.

## What is now engineered

- `empire_os/direct_bsc_status_key_custody.py`: root-only 32-byte
  CSPRNG key, O_CREAT|O_EXCL, mode 0600, fsync, never logged or
  automatically rotated. Key shared via systemd LoadCredential instead
  of exposing it via public env or Git.
- `empire_os/direct_bsc_buyer_receipt_bridge.py`: only a NEW, already
  committed direct pending request can receive one browser bearer after
  the exact issuer SQL write commits. Existing/replayed orders, approved
  requests, expired/wrong bindings never get an additional token. A
  failed receipt must not trigger a second payment request or new order.
- `empire_os/direct_bsc_buyer_checkout_release.py`: explicitly
  released startup assembly uses the existing distinct restricted
  issuer/reader DB logins, systemd protected local
  LoadCredential files, canonical treasury and fresh chain verification.
  Default OFF, no permission additions, no third-party email.
- The existing `self_serve_checkout_api.py` optionally attaches this
  bearer to a fresh order response and mounts the private status route
  only under the exact release toggle and sound systemd credentials.
- The existing `public_gateway.py` has a constrained same-origin,
  no-store, rate-limited POST proxy for status. Does not accept token via
  URL or email, and never grants arbitrary order-ID status reads.
- `apps/empire-public-site/src/app/buy/page.tsx` adds a
  buyer-controlled Check Payment Status button after fresh issuance.
  Token remains in React memory only, no querystring/localStorage.
  Human-approval restrictions remain visible and status cannot
  fabricate on-chain funds or fulfilment.
- `scripts/deploy_direct_bsc_buyer_status_release.py`: founder-gated
  one-shot root operator verifies committed source, existing protected
  login credentials, original order admission and chain, generates
  HMAC key if absent, installs exactly one systemd credentials-only
  drop-in, restarts existing checkout and gateway and independently
  tests both local POST status interfaces deny a reserved unknown token
  with uniform 404. On failure it removes the new drop-in and attempts
  service rollback without rotating/deleting keys.

## Not done by merely committing this package

- Production systemd key credential release: **not yet applied**.
- Public status endpoint in the current running gateway: **not yet
  restarted**. The buyer page in the running website may also require
  its existing independently approved website deployment.
- A real buyer must place an order and actually pay BSC USDT; the
  payment approver, independent blockchain transaction verification,
  12 confirmations, fulfilment, accounting, and genuine revenue are
  still separate processes. Neither an approved request nor fresh
  chain block anchor alone means a customer has paid.
- No unsolicited customer email or outreach is performed by this
  delivery method. Lost browser token requires identity-verified
  founder review; automatic reissue remains blocked.

## Production release (ONLY with explicit founder authorisation)

Once the source and all attached tests have been independently reviewed
and committed, root operator only:

```bash
cd /srv/empire_os
sudo -n ./.venv/bin/python \
  -m scripts.deploy_direct_bsc_buyer_status_release \
  --apply --approved-direct-bsc-buyer-status-release-only
```

A successful release returns
`DIRECT_BSC_PRIVATE_BUYER_STATUS_RELEASE_VERIFIED`;
`public_status_route_unknown_token_denied=true`,
`order_gate_unchanged=true`, `payment_execution=false`,
`revenue_recognition=false`. A failure returns a HOLD and may
perform rollback. NEVER rerun blindly after an uncertain result.

The existing `empire-self-serve-checkout` service uses one worker,
loopback port 8098; public gateway uses one worker, loopback port 80.
Secrets are supplied as systemd `LoadCredential` exclusively to the
checkout worker, *not* to the public gateway process.
