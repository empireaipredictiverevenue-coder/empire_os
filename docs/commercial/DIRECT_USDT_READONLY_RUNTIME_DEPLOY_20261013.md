# Direct USDT runtime configuration — reviewed, bounded deployment
13 October 2026 — EmpireOS, production checkout.

## Context already completed (do not repeat)

Founder approved the one direct-verifier HBA SCRAM rule and the one restricted
SQL LOGIN. Founder terminal proof: exact HBA backup and success; globals backup;
real SCRAM authentication and denial of cross-role escalation PASS; final catalog:
DIRECT_VERIFIER_CATALOG_READY_AUTHENTICATION_TEST_REQUIRED.
Payment approver and escrow verifier were already separately provisioned.
No more database identity or grant work is needed for this step.

The checkout service remains online in DIRECT mode but currently reports
BSC_CONFIG_MISSING. `/buy` exposes only prepayment catalogue and lead-interest
paths. Both order and proposal runtime flags are OFF.

Live, no-write direct mainnet preflight with the first-party verifier using
the public BNB Chain RPC passed: BSC 56, canonical USDT with 18 decimals,
fresh block, 12 required confirmations configured. Wallet public address:
`0x1339b487046B0ad924a10c20b1791608EA8595a8`.
Signing proof does not independently establish Empire AI corporate beneficiary.

## Reviewed staged configuration and operator

- `deploy/systemd/30-direct-bsc-readonly.conf` is an uninstalled exact
  add-on to the existing systemd checkout unit; no secrets or private keys.
- `scripts/deploy_direct_bsc_readonly_checkout.py` performs single-shot,
  fail-closed deployment with a distinct exact founder restart approval flag.
- --preflight executes only read-only inspections and live public BSC RPC
  calls. It rejects unexpected existing drop-ins, stale/incomplete verifier
  catalog, unsafe financial flags, non-DIRECT mode, altered source, unhealthy
  checkout and BSC chain errors.
- --apply retains a root-only, SHA-256 verified backup of existing checkout
  unit and 20-empiredb-reader.conf, installs exactly one new drop-in,
  executes systemctl daemon-reload and restarts **only** the checkout service,
  then verifies runtime health, DIRECT mode, both financial flags OFF,
  fresh BSC RPC and token precision. Attempts rollback if verification fails.
- It does NOT mutate EmpireDB, create buyers/orders, send wallet transactions,
  enable collection, approve finance requests, run migrations, activate escrow,
  or touch unrelated services.

## Execution gates

Production writes/restart NOT authorised by the earlier HBA/login approval.
The founder must separately authorise the exact read-only config installation
and checkout-only service restart.

Read-only first, from server terminal:

```bash
cd /srv/empire_os
sudo -n ./.venv/bin/python -m scripts.deploy_direct_bsc_readonly_checkout --preflight
```

After explicit separate founder approval of the config install AND checkout
restart, exact apply command:

```bash
cd /srv/empire_os
sudo -n ./.venv/bin/python -m scripts.deploy_direct_bsc_readonly_checkout \
  --apply --approved-direct-bsc-readonly-config-and-checkout-restart
```

On failure STOP, inspect backup and service; do not blindly retry.
Expected successful readback:
`DIRECT_BSC_RUNTIME_STATUS=READONLY_CONFIG_INSTALLED_PAYMENT_FLAGS_OFF`.
Then inspect `/health`, `/v1/catalog` and the read-only mainnet chain.
No payment flags ON by this release.

## Remaining activation work

After deployment: operator human assignment and secure DSN transport for
the dedicated approver/verifier roles; account/treasury beneficiary decision;
specific guarded payment and binding-order activation permission; genuine
buyer-approved order, human-approved payment request, matching canonical
receipt with >=12 confirmations, fail-closed replay/idempotency, fulfilment
and economic memory evidence.

Neither unit configuration nor a good BSC preflight counts as customer payment
collection. No money or revenue should be claimed.
