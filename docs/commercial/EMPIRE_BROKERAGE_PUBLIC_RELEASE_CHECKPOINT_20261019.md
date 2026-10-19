# Empire AI — Data Brokerage premium public release truth

**19 October 2026 | First-party commercial site / gateway / checkout | OBSERVE**

## Production facts verified live (not mocked)

The founder had previously approved continuing the unpriced premium enquiry
integration; source was committed on 18 October as `e5b2bf16`.
On 19 October, a fresh read-only GET checked the **running** services:

- `http://127.0.0.1:8098/v1/brokerage/premium-discovery`: **404**.
- `https://empire-ai.co.uk/v1/checkout/brokerage/premium-discovery`: **404**.
- The existing gateway and checkout were both **active**.
- The existing founder-led $199 enquiry/catalogue was still available.
- The proposed $1,250/month agency and $4,000/month enterprise prices
  remain unapproved private hypotheses, **not** public subscriptions.
- The checkout private systemd drop-in
  `95-empire-brokerage-premium-discovery-private.conf` was not present
  in the effective unit configuration.
- Two other agents' working-tree edits were still pending in
  `empire_os/public_gateway.py` and
  `empire_os/self_serve_checkout_api.py`; do not overwrite them.

This means **no live premium enquiry or customer-to-CRM funnel exists yet**.
Neither a historical successful unit test nor a committed route adapter
establishes live bookability, live intake or any money.

## Actual ASTRA build provenance difference

The server's current public site assets contain historical commercial-page
bundles but **none** had the premium route string
`/v1/checkout/brokerage/premium-discovery`.

The isolated Next.js Webpack build from the new commercial-page source
contains the premium component in
`out/_next/static/chunks/app/commercial/page-3fc4ac32a8248cae.js`.
The two generated `out/commercial.html` files differ; the live file
was **32,930 bytes**, the isolated source build **27,371 bytes**.
Never overwrite current ASTRA content with an older, narrower build.

The right migration is for ASTRA to merge the committed component
into its **latest flagship worktree**, produce a new reviewed build,
and update the live HTML **together with its exact referenced JS/CSS
chunks**. The source is already integrated additively; no extra landing
page, checkout or CRM infrastructure is necessary.

## New executable proof

`scripts/review_brokerage_premium_live_release_20261019.py` is a pure
read-only, 2-GET observer with exact loopback allowlist, 4-second
timeouts, 16k maximum responses, no redirects, strict two-unpriced
offer validation, SHA256 comparison of staged/current HTML and
working-tree conflict indicator. It reports no optimistic customer
ingestion, invoices, payments or ROI.

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_brokerage_premium_live_release_20261019 --read-only
```

Expected **right now**:
`BROKERAGE_PREMIUM_API_RELEASE_INCOMPLETE`,
private/public HTTP **404**, static output drift and concurrent edits.

The status can report two APIs responding even when the HTML is not
yet integrated; it **never** asserts that a customer-facing form
or a real buyer has been tested.

## Newly prepared exact public-gateway release guard

`scripts/deploy_brokerage_premium_public_gateway_20261019.sh`

The tool has three separate modes:

- `--source-preflight`: checks current gateway, original $199 offer
  and source/tests only, without enabling any route or changing files.
- `--preflight`: additionally requires an independently live
  original private endpoint, a live **currently referenced**
  commercial-page JS bundle that actually contains the reviewed
  premium component, and no uncommitted concurrent gateway/checkout
  edits. Fails closed if any requirement is missing.
- `--apply-founder-approved-unpriced-public-enquiry`:
  root-only release after all prior checks. Installs an exact, uniquely
  named systemd drop-in for the **existing**
  `empire-public-gateway.service`, restarts only that unit,
  verifies live public GET yields exactly two unpriced options and
  rolls back only that drop-in on failure.

The public source/gateway handler still validates buyer response-only
consent, same-origin request, rate limits and a bounded exact product
code, and returns no fabricated subscription or invoice. This script
does **not** submit a production enquiry, copy website assets, change
Stripe/USDT-BSC settings, modify CRM tables, or activate automatic send.

## Actual safe activation order

1. **Private route (requires founder terminal root):** only if its own
   preflight succeeds and shared source changes are independently
   reviewed. Existing command:

   ```bash
   cd /srv/empire_os
   sudo bash scripts/deploy_brokerage_premium_discovery_20261018.sh --apply-founder-approved-private-premium-enquiry
   ```

   Expected `PRIVATE_BROKERAGE_DISCOVERY_LIVE_LOOPBACK_GET_VERIFIED`.
   This changes only the checkout process, no public page or payments.
2. **ASTRA-owned live site:** merge new UI into latest checked flagship,
   visually review desktop/mobile, produce static bundle, check all
   referenced build assets and preserve live legal/SEO/hero design.
   Not completed by these read-only scripts.
3. **Original two shared owner files:** commit/reconcile the existing
   gateway and checkout edits before an unguarded process restart.
4. **Public gateway:** only when the full `--preflight` passes,
   perform the exact public API release with founder approval.
5. **Actual conversion proof:** after the approved form is live,
   one real opted-in buyer can submit; inspect one real canonical
   founder CRM item and independent payment/delivery evidence.
   No synthetic buyer/test purchase in production.

### Rollback if public release later activates

Only delete its own `95-empire-brokerage-premium-public.conf` unit
drop-in and restart **only** `empire-public-gateway.service`.
Never delete other agents' service overrides.

## Scope conclusion

The new guard and live observer materially close the gap between
**test passed** and **actually served**. The end-to-end public
commercial funnel is **not yet complete**: private root release, ASTRA
site bundle reconciliation, public gateway release and first real
buyer all remain separate, externally verifiable steps.
