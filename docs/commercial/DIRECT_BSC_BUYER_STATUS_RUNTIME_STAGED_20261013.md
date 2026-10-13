# Empire AI — Direct BSC Buyer Status, Authenticated Runtime (STAGED)
13 October 2026 · production-truth-first continuation after successfully provisioned credentials

## Verified starting position

The founder executed the isolated login provisioner exactly once:

```text
{"buyer_status_endpoint_activated": false,
 "env_path": "/etc/empire_direct_bsc_buyer_status.env",
 "file_mode": "0600", "payment_execution": false,
 "role_memberships": "dedicated_only",
 "secrets_printed": false,
 "status": "two_login_connections_verified"}
BSC_STATUS_LOGINS_EXIT=0
```

This is evidence of **two distinct authenticated PostgreSQL logins**.
It is not proof of buyer token delivery or money received.

Canonical 047–050 migrated. Public orders/proposals were separately enabled
by the existing founder-approved four-product controlled-release drop-in.
No changes to that systemd config are made in this programme. The latest
observed checkout health still returned `BSC_CONFIGURED_CHAIN_UNVERIFIED`,
`payment_execution=false`, `revenue_recognition=false`.

## New tested code, not deployed

- `scripts/inspect_direct_bsc_status_logins_readonly.py`: root-only
  **READ ONLY** verification of root-owned mode 0600 secret file format,
  canonical local-only two DSNs, different passwords, actual PostgreSQL
  session/role/function isolation, and denial of a reserved unissued HMAC
  fingerprint through the 049 function. Never prints credentials or
  buyer records; creates no role/token/payment data.
- `empire_os/direct_bsc_buyer_status_runtime.py`: staged dependency
  assembly for the existing `create_private_buyer_status_router` and
  installed `PrivateBuyerStatusPostgresReader`. It refuses app/general
  DSNs or remote/noncanonical reader identities and refuses short HMAC keys
  or invalid treasury. The standalone app defaults to OFF unless BOTH
  explicit founder release and a *fresh independently verified* BSC chain
  callback return literal True. No process, port or public routes are started.
- Unit tests verify matching POST-body bearer only, denial of expired,
  mismatched or missing identity, chain-held response 503, unsafe DSNs,
  no buyer database calls when OFF, and absence from the running gateway
  and internal checkout service.
- Existing public gateway and self-serve checkout code are NOT modified.

## Next live verification (read only, not activation)

Run only the committed read-only audit as a root operator:

```bash
cd /srv/empire_os
set +e
sudo -n ./.venv/bin/python \
  -m scripts.inspect_direct_bsc_status_logins_readonly --verify-only
echo "STATUS_LOGIN_READBACK_EXIT=$?"
```

Success: `DEDICATED_STATUS_LOGINS_LIVE_READBACK_VERIFIED` and exit 0,
with neither passwords nor customer PII disclosed. An error must **not**
be fixed by rerunning login provisioning; inspect readonly metadata first.

## Release gates still missing / independently required

1. First-party HMAC key with at least 32 CSPRNG bytes, durable root-only
   custody. The issuer and reader must share EXACTLY the same key. No
   key is generated here; wrong key makes all issued status tokens invalid.
2. Genuine verified BSC mainnet chain ID 56, known USDT BEP-20 contract,
   approved treasury, current block anchor and verifiable token decimals.
   Configured != independently verified; approval alone != funds received.
3. Buyer identity authentication, exact one-order/one-request token
   issuance by the restricted issuer, secure one-time token delivery via
   authorised first-party mailbox, optional reissue/revocation workflow,
   recipient evidence and suppression checks. No outbound sends authorised.
4. Production request-rate limiting/abuse, origin and HTTPS controls for
   the web gateway. In-process rate limiting alone is not multi-instance
   protection. Gate proof must be independently verified before publishing.
5. Explicit founder authorisation for public customer-status route
   activation. This work installs no route, restart, or payment switch.
6. Independent payment approvals, on-chain 12+ confirmations,
   buyer/order/contract/amount/treasury evidence, verified fulfilment and
   realised-revenue accounting before representing a payment as received.

The two isolated PostgreSQL logins are already provisioned. Do NOT rerun
migration 049 or 050, or the credential provisioner.
