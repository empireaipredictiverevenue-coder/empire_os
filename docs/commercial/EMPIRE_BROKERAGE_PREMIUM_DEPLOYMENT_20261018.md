# Empire AI — Premium Data Brokerage integration release checkpoint

**18 October 2026 | Founder request: finish the public integration | Source verified, privileged release pending**

## What the operator actually implemented

1. **Existing checkout preserved:** `empire_os/data_brokerage_premium_private_service.py` imports the canonical `empire_os.self_serve_checkout_api:app`, then mounts the previously tested private `/v1/brokerage/premium-discovery` GET/POST **only** when its exact deployment flag is `ON`. Uses the existing `LIMITER.allow`; no new DB login, table, grant, API server, payment config or transport.
2. **Existing gateway preserved:** `empire_os/data_brokerage_premium_public_service.py` wraps `empire_os.public_gateway:app`; requires public release and two separately verified facts (private active, ASTRA QA) before mounting the unpriced `/v1/checkout/brokerage/premium-discovery` routes. Their first-party origin, rate limit, consent and receipt guards are reused from the existing feature.
3. **Minimal source UI integration:** the existing `apps/empire-public-site/src/app/commercial/page.tsx` gains one import and one `<BrokeragePremiumDiscovery />` tag below the existing founder proposal. No existing form, checkout price, SEO or flagship component removed. This feature returns `null` until the corresponding public GET catalogue is verified.
4. **Real-route tests:** isolated FastAPI HTTP tests checked that the wrappers expose no new route by default, correctly mount only with exact flags, preserve original enquiry GETs and reject unauthorized POSTs. This also verifies the deferred router representation in this FastAPI version; direct top-level route introspection alone is not authoritative.
5. **Site build:** TypeScript passed, and an isolated **Webpack production build** for `/commercial` succeeded. Turbopack initially refused the isolated worktree's external `node_modules` symlink; Webpack is the supported successful path.
6. **Narrow root deployment operator:** `scripts/deploy_brokerage_premium_discovery_20261018.sh` only deploys the private checkout wrapper by adding its own uniquely named systemd drop-in and restarting **only** `empire-self-serve-checkout.service`. On failed health it removes its drop-in and restarts the original service. Existing payment/binding configs are explicitly retained. It does not restart the public gateway, serve a new website build or send a CRM POST.

## Important live website difference: do not overwrite ASTRA

The current production static
`apps/empire-public-site/out/commercial.html` is **32,930 bytes**.
The isolated full site build from current source generated
`out/commercial.html` at **27,371 bytes**.

That size/asset mismatch is significant: other ASTRA/flagship output
has apparently been deployed or staged outside the current source
snapshot. Wholesale replacement with the isolated output may regress
legitimate website design, content or previous releases. Therefore
**the isolated site build is not copied to the live `out/` tree**, and
the root release operator explicitly refuses to touch site files.

The public GET/POST premium route is **not enabled** until ASTRA reviews
the current live asset baseline and the new component's desktop/mobile
rendering. The source integration is committed; a future controlled
public release will need precise site asset reconciliation and separate
public gateway deployment under the existing owner.

## Reproducible rootless preflight

```bash
cd /srv/empire_os
bash scripts/deploy_brokerage_premium_discovery_20261018.sh --preflight
```

This checks the original existing checkout/catalogue availability,
the add-only module custody, service health, no existing conflicting
drop-in and the targeted safety tests. No service restart.

## Founder-approved exact private release (requires systemd/root)

```bash
cd /srv/empire_os
sudo bash scripts/deploy_brokerage_premium_discovery_20261018.sh \
  --apply-founder-approved-private-premium-enquiry
```

Expected receipt:
`BROKERAGE_PRIVATE_RELEASE_PREFLIGHT_PASS` then
`PRIVATE_BROKERAGE_DISCOVERY_LIVE_LOOPBACK_GET_VERIFIED`.

This is **internal API activation only**. It does not authorise public
website publication or third-party marketing sends. No synthetic
buyer events, order, payment, BSC transfer, revenue recognition or
newsletter subscription are created by the deployment.

## Optional root rollback of only our private wrapper

```bash
sudo rm -f /etc/systemd/system/empire-self-serve-checkout.service.d/95-empire-brokerage-premium-discovery-private.conf
sudo systemctl daemon-reload
sudo systemctl restart empire-self-serve-checkout.service
```

These three commands remove the exact additive drop-in and restore
the original module. They are not executed in this source-only task.

## Required remaining work to claim a full live release

- Independently verify live private GET status after the root-owned
  release; this is not established by source or test results.
- Integrate the reviewed public gateway wrapper with the original
  `empire-public-gateway` service only after private release proof
  and ASTRA site output reconciliation; first-party CSRF/origin and
  abuse controls must remain in place.
- Reconcile ASTRA's actual live commercial page and static JS assets
  without replacing newer live content with older source.
- Test a real visitor's consentful submission once available, and
  check the existing founder CRM review sees that exact genuine
  enquiry. Do not manufacture fake production prospects.
- Independently verify accepted scope, capacity, source-use
  permission, fulfilment and money before booking any brokerage
  revenue. $1,250/month and $4,000/month are still **hypotheses**,
  never binding public prices or contracts.

The existing $199 Competitor Search Gap founder enquiry remains
unchanged in the production checkout catalogue.

**Release classification:** additive source/code prepared and tested;
live private deployment requires the founder terminal command above;
public commercial page/API integration not yet verified in production.
