# Empire AI — source-backed /buy → /commercial proposal conversion

**20 October 2026. Website & Growth source owner.** This work belongs
inside the existing Website & Growth stream (three-chat control), not a
new CRM, new agent or separate conversation.

## What was fixed

The live /buy static export contained a manually injected
`/_next/static/agency/selected-product-bridge-20261020.js`. The approved
checkout source did not reproduce that overlay. Replacing the live HTML
with the old October 13 pinned export would have removed newer site work.

The original first-party commercial offers API ALREADY lists all **four**
approved intelligence products, so a separate enquiry API or new
database schema is unnecessary. A buyer's own selected product can be
recorded through the existing consent-gated, founder-led commercial
interest flow; no wallet and no binding order are needed for that path.

Changes made in source:

- `apps/empire-public-site/src/lib/buyer-proposal-handoff.ts`:
  allowlists exactly the four verified intelligence codes for a
  nonbinding `/commercial?product=...#commercial-enquiry` deep link.
  Commercial preselection succeeds only when the current original
  `GET /v1/checkout/commercial/offers` lists the exact chosen code.
  Stale, forged, unknown or malformed URL parameters fail closed:
  the form asks the buyer to pick a currently approved offer.
- `src/app/buy/page.tsx`: retained the standard fixed-price and BSC
  checkout UI; added a native **REQUEST A PROPOSAL INSTEAD** anchor in
  the form and selected-product links for the nonbinding fallback
  experience. Clicking the link NEVER posts an order.
- `src/app/commercial/page.tsx`: reads the untrusted query only after
  the approved offers GET; selects only an exact verified offer;
  retains the original company, email, geography, desired outcome,
  consent, idempotency and required first-party submission controls.
  Does not silently switch a rejected requested product to
  consultancy, does not submit on page load, and cannot issue payment.
- `tests/buyer-proposal-handoff.test.mjs`: Node 22 native tests for
  all four approved products, missing/forged/stale codes, normal
  visitors and pure no-side-effect selection.

## Independent static-export evidence

Isolated worktree:
`/home/ubuntu/empire_worktrees/buy_page_current_build_reconciliation_20261020`

Executed clean Next.js 16.3.5 production build (`npm run build`):
19 static pages generated, TypeScript passed. Both `/buy` and
`/commercial` exported; their compiled JavaScript contains the
proposal link and rejected-product warning. The native staged export
does **not** contain the injected product-selection overlay.

The standalone read-only release-candidate auditor
`scripts/review_native_buyer_proposal_build_20261020.py` verifies source
hashes, both static HTML hashes, all directly referenced compiled
assets, the native proposal behaviour and the absent untracked overlay.
It deliberately does NOT rewrite the live site, approve the older
manifest, enable payments or issue a release credential.

Stage SHA receipts:
`docs/website/release_candidates/NATIVE_BUYER_PROPOSAL_STATIC_STAGE_20261020.json`.

Original test outcomes at checkpoint:
- 5 Node handoff tests passed.
- 76 Python native-source, privacy, existing first-party intake,
  checkout/API, site-consent and buyer-canary tests passed.
- Clean full-site Next production build passed. This is **build proof**,
  not founder visual acceptance or production rollout approval.
- Live /buy and /commercial HTML **both differ** from the isolated
  current-source stage; manifest explicitly reports both differences.

## Why the strict buyer checkout canary remains HELD

The existing 13 October static-export HTML and all its 36 pinned assets
still match their original approved manifest, but the live
`out/buy.html` is a later additive build, not that original HTML.

Critically, the latest live cinematic homepage is a custom owner
static-release from
`/home/ubuntu/empire_worktrees/flagship_final_creative_20261018`.
The canonical `src/app/page.tsx` does not yet reproduce that cinematic
homepage. Copying a full fresh `out/` tree from the current canonical
source would overwrite the approved premium homepage and potentially
other owner's live routes. **Do not full-site deploy this stage.**

This task therefore ships source and an independently hash-reviewed
stage, **NOT** a public buy/commercial HTML replacement and NOT a
rebaseline of `DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json`.

## Exact website-owner route to finish

1. Reconcile and commit the canonical ASTRA cinematic homepage source,
   its global styling, logo assets and other currently deployed
   owner-approved routes to the main website source. Preserve /roofing,
   privacy/consent and buyer routes.
2. Produce one fresh isolated reproducible Next export from that
   complete source. Run original website visual/mobile/source-policy QA.
3. Verify a new **versioned** site manifest against that exact build
   (including selected-product proposal code, checkout bundles and
   static HTML). Keep historical Oct13 receipt immutable.
4. Coordinate a backup/rollback and website-owner-approved release,
   compare served public HTML/chunk checksums to new manifest,
   check original 7 buyer checkout gates and first-party routes; only
   then clear `CHECKOUT_RELEASE_HTML_PROVENANCE_HOLD`.
5. Obtain a real opt-in first-party enquiry via the published site and
   reconcile its exact CRM tenant/source record. Do **NOT** POST a fake
   production lead to make counters green or infer a sale from GET/RPC.

Developer verification:

```bash
cd /srv/empire_os
node --test apps/empire-public-site/tests/buyer-proposal-handoff.test.mjs
PYTHONPATH=.:tests .venv/bin/python -B -m pytest -q \
  tests/test_review_native_buyer_proposal_build_20261020.py \
  tests/test_first_party_sales_interest.py \
  tests/test_self_serve_checkout_api.py \
  tests/test_site_consent_privacy_links.py

# Review only after ASTRA-reconciled current-source build is produced:
PYTHONPATH=. .venv/bin/python -B \
  -m scripts.review_native_buyer_proposal_build_20261020 \
  --read-only --project apps/empire-public-site
```

**Safety:** No real checkout POST, prospect email, buyer record,
canonical write, payment or new scheduler. Existing Ops and
first-sale source-health timer unchanged. Keep all unfinished tasks
in Website & Growth and Revenue & Buyers; native frontend build
engineering can be marked committed when merged, but release proof is
still OPEN.
