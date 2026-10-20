# Empire AI — independent live buyer-checkout release gates

**20 October 2026 — code-only read-only canary enhancement, no financial action**

## Why this exists

The original `scripts.probe_direct_bsc_first_buyer_readonly` failed at
`published_asset_integrity` and skipped unrelated, useful GET/bearer/RPC
checks. The original *strict* release test is **unchanged** and still fails
until every gate is independently verified.

An additive opt-in mode now tests every stage independently, preserves a
failing overall result for any held stage, and reports only allowlisted stage
names and boolean results. It is owned by the existing checkout code, with
no worker, timer, background task, new database role, or authority change.

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m \
  scripts.probe_direct_bsc_first_buyer_readonly --independent-read-only
```

Exit 0 means all seven checks pass. Exit 2 means **HELD** and must not be
overridden; exit 3 rejects unsupported flags. The existing no-flag CLI
remains the original fail-fast release check.

The opt-in mode performs only GETs, two existing *reserved nonissued*
negative-status-token POSTs, and first-party **read-only** BSC JSON-RPC.
There is no actual token issuance, real order POST, personal data lookup,
payment approval, fund movement, settlement, email or revenue recognition.

## Genuine 20 October live results

| Independent gate | Live result |
|---|---|
| `/buy` HTML GET 200 | **PASS** |
| Original immutable HTML + asset checksum | **HELD** |
| Four-product self-serve catalog | **PASS** |
| Checkout health and pending-order admission flags | **PASS** |
| Private reserved nonissued buyer status bearer denied | **PASS** |
| Public reserved nonissued buyer status bearer denied | **PASS** |
| Fresh BSC mainnet chain (56), USDT decimals (18), age < 5 min | **PASS** |

Overall: **6/7 passed, `CHECKOUT_BUYER_READONLY_CANARY_HELD`**.
No accepted order or recognised revenue was proved.

## Original website release provenance investigation

- The checked-in October 13 manifest still perfectly verifies its original
  **14,612-byte** static-preview `buy.html` and all **36** pinned assets.
- The actual public page is the same bytes as live `out/buy.html`, which
  is a **20,342-byte** October 17 static export. It is neither the
  manifest's approved HTML nor the manifest's prior-live HTML.
- All 36 pinned assets remain present and digest-correct.
- The original checked-in `src/app/buy/page.tsx` still matches its
  recorded approved source SHA256, but the public page's global layout
  and compiled-chunk references differ from the original preview.
- An isolated Next.js 16.3.5 production rebuild from the current
  committed website source succeeded and produced a **different 15,477
  byte** `buy.html`; it also did not match the served page.
- Therefore we **cannot attest that the currently deployed HTML came
  from the current reviewed source**. Replacing the old manifest's
  SHA256 with a checksum of the current page would be circular and
  unsafe. Nor should we restore the older page over later website-owner
  edits without approved deployment/rollback coordination.

**Exact website-owner action:** locate and independently review the source
and static-export build corresponding to the currently served checkout.
Regenerate and review a dedicated *new-version* site release manifest
with source, export and chunk receipts, through the existing website
release controls, then perform safe staged promotion with rollback.
Do **not** weaken `_published_checkout_verified` or repin the 13 October
manifest just to force the canary green.

## No invented commerce

Canonical first-party commercial and Predictive Revenue sales enquiries:
**0** in the original founder-scoped read-only source at the previous
checkpoint. Canonical fulfilment orders, payment-evidence and outcomes
were also **0**. The live read-only BSC network probe is evidence of
chain connectivity, **not evidence of funds or a purchaser**.

The existing Ops Control's `first_sale_conversion_readiness` continues
to surface the checkout asset hold and remains change-driven. No new
monitoring schedule is added.

## Regression boundary

The original source-integrity integration test
`tests/test_promote_direct_bsc_buy_static_export.py::test_postpublished_manifest_matches_only_buy_page_and_hashed_assets`
is **expected to fail on the current 20 October server** because it asserts
the actual October 17 live HTML equals the October 13 pinned export digest.
This is an authentic release hold; it is not suppressed, modified, XFAIL-ed,
rebaseline-hashed or represented as passing.

The additive independent-canary tests and the remaining guarded checkout
regressions run separately without invoking this known historical deployment
assertion. An overall live release verification remains HELD until the
existing website owner produces independently reviewed current-build
provenance.
