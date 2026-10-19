# Empire AI Data Brokerage — exact live-page premium UI integration

**19 October 2026 | Baseline-proven page update, not a flagship rebuild**

## First independent source-of-truth discovery

The **actual deployed** `/srv/empire_os/apps/empire-public-site/out/commercial.html`
has SHA256:

`7566e7711d46bbed84651db4967d47636e9c6cb13a096107d524d3bd73568d9c`.

It was found **byte-for-byte identical** to the archived output in
`/home/ubuntu/empire_worktrees/flagship_organic_collector_merged_20261018`,
clean worktree branch `review/flagship-organic-collector-merged-20261018`,
commit `d10fa037`. Unlike the stale page on canonical main, this
source already includes the original organic source attribution, offer
family selector, YouTube source fallback, location-specific sector
context and current copy. It is the correct exact live-page base.

The candidate created from a **new clean worktree at `d10fa037`**,
`feature/brokerage-premium-exact-live-site-20261019`, only:
- imports the previously built `BrokeragePremiumDiscovery` component;
- adds that component **beneath** the current founder form;
- includes its previously reviewed parsing library and Node tests.

Existing page logic was not rewritten and no legacy field was dropped.

## Actual produced build

An isolated `next build --webpack` succeeded, after TypeScript and
5 focused Node parser/security tests passed.

Compiled page SHA256:
`89e78031318d3a0a3cba2d9e23289bce52e9e3401fb90b1897dab8924d7f9567`.

The staged HTML and deployed HTML have:
- exactly **109 visible rendered text segments**, with exactly equal
  content and order;
- same current header, founder offers, explanations, TAM buyer-intent
  guidance and original attribution copy;
- a new built commercial page bundle containing the exact
  `/v1/checkout/brokerage/premium-discovery` path and the
  `Request an intelligence scope` component;
- **11 additional** hashed Next.js static assets (~304 KB), with
  **zero** collisions or changed contents for the 38 shared assets.

The premium component is client-only and remains **hidden** while the
public gateway endpoint is absent/404. It never advertises the unapproved
$1,250/$4,000 draft subscription prices.

## Surgical site release implementation

`scripts/release_brokerage_premium_commercial_assets_20261019.py`
supports only a byte-pinned `--preflight` or
`--apply-founder-approved-premium-commercial-page`.

Its preflight validates:
- **exact SHA256 of original served HTML**, rejecting any concurrent
  ASTRA/site change;
- **exact SHA256 of staged candidate**, rejecting post-review changes;
- all 109 existing visible text elements preserved without alteration;
- compiled page JS physically present with the premium endpoint and
  enquiry heading;
- static asset contents, size bound, **exact expected 11 new assets**,
  and no modification of shared named assets.

On apply, the script saves a separate mode-`0600` rollback snapshot,
copies **only missing** hashed static assets, then atomically swaps
**only `out/commercial.html`**. Other HTML routes, scripts, APIs,
database, mail, funds and source rights are untouched. A failed
post-atomic hash check restores the saved HTML.

A simulated release with a temporary copy of the actual site assets
passed; tests also reject live HTML drift and concurrent asset
collision without overwriting anything.

## Operational dependency remains independent

This optional site asset release does **not** activate the public API.
Private `/v1/brokerage/premium-discovery` is live and returned 200
with exactly two nonbinding, unpriced discovery options on 19 October.
Public `/v1/checkout/brokerage/premium-discovery` still returned 404.
The public gateway script still must reject activation if the
concurrently edited gateway/checkout source has not been reconciled.
The current owner's extra first-party and flagship routes must not
be dropped or silently included in a restart.

Even when the public GET eventually returns 200, the first
**real buyer-initiated opted-in POST** and its founder-CRM visibility
must be independently observed; no synthetic buyer insertion should
be used as a release canary. No payment, contract or revenue proof
is implied by this HTML or feature code.

## Commands

```bash
cd /home/ubuntu/empire_worktrees/brokerage_premium_exact_live_site_20261019
/srv/empire_os/.venv/bin/python -B scripts/release_brokerage_premium_commercial_assets_20261019.py --preflight
# After specific reviewed page-only release approval:
# /srv/empire_os/.venv/bin/python -B scripts/release_brokerage_premium_commercial_assets_20261019.py --apply-founder-approved-premium-commercial-page
```

This task preserves the existing flagship from the exact released
baseline; this is **not** a new template, new website, second CRM,
new paid marketing programme or blanket gateway deployment.
