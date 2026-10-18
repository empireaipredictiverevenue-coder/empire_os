# Empire AI Data Brokerage — ASTRA premium enquiry component handoff

**18 October 2026 | Flagship-safe additive UI | Not published or rendered in the current public page**

## Starting production truth

The founder executed
`scripts.review_data_brokerage_premium_gateway_20261018 --read-only`
and received `TWO_HOP_PREMIUM_GATEWAY_ADAPTER_READY_RELEASE_HELD`.
There are two unpriced private discovery options
(`brokerage_agency_discovery` and
`brokerage_enterprise_discovery`), with two-hop public gateway and
checkout candidate code written and isolated HTTP tested.

The public and private premium routes are **NOT mounted**, existing
`/commercial` **does not render** these choices, no production buyer
enquiry/CRM insert has been observed, and the existing approved $199
`competitor_search_gap` enquiry remains unchanged.

## Exact feature-only UI work

- `apps/empire-public-site/src/lib/brokerage-premium-interest.ts` defines
  the exact first-party public route contract, two premium product codes,
  strict unpriced catalogue parser and safe confirmation receipt parser.
  It refuses forged prices, paid SKUs, future subscriptions, arbitrary
  products, duplicate product codes, nonbinding-term drift, and fabricated
  financial confirmation.
- `apps/empire-public-site/src/components/BrokeragePremiumDiscovery.tsx`
  is an optional client-side premium inquiry section visually aligned to
  the existing deep navy/electric blue Empire AI design system. It
  previews two **Request a custom scope** options with business,
  work email, company domain, industry, territory, commercial decision
  question, explicit response-only consent, and a hidden honeypot.
  It reuses the already-proven
  `src/lib/commercial-interest-attempt.ts` secure UUID/idempotent retry
  helper. The native browser fetch uses the same-origin public path and
  preserves one request key for identical retries.
- The component **renders nothing on missing/unavailable/invalid
  first-party catalogue**. It does not display internal hypothesis
  prices ($1,250 or $4,000), £0 pricing or a dead form.
  It shows a success reference only when a checked, typed,
  matching, nonbinding founder-CRM confirmation is returned.
- `src/lib/brokerage-premium-interest.test.mjs` exercises strict
  catalogue and receipt parsing using Node's native test runner and
  TypeScript stripping. TypeScript full project compilation is checked
  against existing public-site dependencies.
- The current live
  `apps/empire-public-site/src/app/commercial/page.tsx`, project
  globals, current ASTRA flagship output and production gateway/
  checkout files are **not touched** in this feature.

## Exact ASTRA integration instructions (after founder review)

1. Verify the privately mounted checkout and public gateway routes
   using the separate `docs/commercial/EMPIRE_DATA_BROKERAGE_PREMIUM_GATEWAY_HANDOFF_20261018.md`
   and the existing rate-limiter/CSRF/origin security. Public page
   should not show a form before the GET route returns the reviewed
   two-unpriced-product schema. Do not publicly activate a priced plan
   from internal price hypotheses.
2. In ASTRA's existing `/commercial` page, add:
   `import BrokeragePremiumDiscovery from "@/components/BrokeragePremiumDiscovery";`
   then render `<BrokeragePremiumDiscovery />` below the existing
   founder-led proposal content. ASTRA decides final responsive
   layout and animation integration; **do not replace the current
   hero, cards, forms, first-party tracking, or existing design**.
3. Perform desktop/mobile, keyboard/screen-reader, reduced-motion,
   fast/slow network, CSRF/replay/rate-limit and no-price UX QA.
   The enquiry form must show exact response-only contact consent
   and a privacy link; no newsletter permissions or auto-send.
4. Only a real buyer-initiated accepted submission can verify
   the actual CRM handoff. Do not insert an artificial lead to make
   a canary pass. Confirm the real response enters the existing
   founder CRM prospect review, and no accidental duplicate row,
   newsletter subscription, order or payment is created.
5. Obtain explicit release approval before touching production app
   imports, deploying a new site build, mounting routes, or
   changing shared production service restart state.

## Reproducible feature test

```bash
cd /srv/empire_os/apps/empire-public-site
node --experimental-strip-types --test src/lib/brokerage-premium-interest.test.mjs
./node_modules/.bin/tsc --noEmit --incremental false --pretty false -p tsconfig.json

cd /srv/empire_os
./.venv/bin/python -B -m scripts.review_data_brokerage_premium_gateway_20261018 --read-only
```

**Current goal:** move from backend-ready to trustworthy premium
buyer-initiated enquiries, not to add another catalogue, payment switch,
database or speculative sales promises. This feature is prepared for
ASTRA review, not a website publication or realised-revenue receipt.
