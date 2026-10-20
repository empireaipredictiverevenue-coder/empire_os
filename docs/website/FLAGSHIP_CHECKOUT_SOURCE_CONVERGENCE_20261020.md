# Empire AI — ASTRA flagship + buyer proposal source convergence

**20 October 2026. Website & Growth existing owner. Source-only integration.**

This release reconciles a specific production provenance gap: the live public
homepage comes from ASTRA's independently reviewed premium cinematic release,
while canonical website source used a different older homepage; later
`/buy` and `/commercial` forms gained independently reviewed native
nonbinding product-proposal improvements that were not yet published.

## Exactly what has been assembled

Clean isolated candidate:
`/home/ubuntu/empire_worktrees/flagship_checkout_source_convergence_20261020`
from the latest canonical EmpireOS branch.

- ASTRA's reviewed source commitment `084f4e80`: cinematic flagship
  `page.tsx`, approved black/navy/blue/gold site chrome, shared 3D Earth,
  scene logic, layout, associated component CSS, source attributions,
  image assets and Satoshi font assets.
- Existing canonical current checkout and proposal files preserved
  byte-for-byte from commit `56817a08` and subsequent mainline changes:
  `src/app/buy/page.tsx`, `src/app/commercial/page.tsx`, and
  `src/lib/buyer-proposal-handoff.ts`.
- Existing industry, roofing, trust, privacy/consent, product, and
  Predictive Revenue routes retained; no full `out/` directory copied
  from the older ASTRA worktree, and no rollback to 13 October checkout.
- Existing site `package.json` dependency versions are compatible with
  ASTRA's approved React Three Fiber/Drei/Three.js and lucide components;
  no external script/CDN introduced.

## Current integration verification

- Clean isolated Next.js 16.3.5 `npm run build` succeeded with TypeScript
  and 19 static routes, including `/`, `/buy`, `/commercial`,
  trust, Predictive Revenue, supported industry and roofing pages.
- Source tests: 5 native product-proposal Node tests passed, reviewed ASTRA
  scroll-world director logic passed; 105 Python site/checkout/privacy and
  source-provenance tests passed.
- The existing native buyer proposal build auditor returned
  `STAGED_SOURCE_BUILD_VERIFIED_OWNER_RELEASE_REVIEW_REQUIRED`:
  all checked source, compiled assets, nonbinding proposal routing and
  rejected-product messages verified.
- `scripts/review_combined_flagship_checkout_stage_20261020.py`
  independently checks the **three pinned HTML pages**, associated reviewed
  source and **14 first-party hashed JS/CSS assets** against
  `docs/website/release_candidates/FLAGSHIP_CHECKOUT_COMBINED_STAGE_20261020.json`.
  It produces an explicit release HOLD when source, HTML, or assets drift.
- The original **13 October** BSC checkout manifest remains immutable.
  The existing strict seven-gate live checkout canary remains HELD at
  `published_asset_integrity` until current approved pages are deployed
  with separately accepted versioned receipts.
- ASTRA browser visual QA for 1440/820/390/320 widths should be run
  against the combined stage and results reviewed before any public static
  output is replaced. This handoff is not founder visual signoff.

## Safe operator checks

```bash
cd /home/ubuntu/empire_worktrees/flagship_checkout_source_convergence_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_combined_flagship_checkout_stage_20261020 \
  --read-only --project apps/empire-public-site

node --test apps/empire-public-site/tests/buyer-proposal-handoff.test.mjs
node apps/empire-public-site/scripts/test-scroll-world-director.mjs
```

The static build receipts refer to the isolated `out/` output; Git does not
publish that output, and checking out this source commit alone must **not**
cause an automatic public website promotion.

## Remaining release gates

1. Existing ASTRA website release owner reviews combined desktop/mobile
   visuals, image/3D fallback, keyboard access, source attributions, global
   header, consent pages and genuine checkout CTA behaviour. Do not infer
   approval from a successful TypeScript or SHA check.
2. Reconcile any visual differences with the deployed cinematic homepage
   without touching unrelated owner work. Source signoff comes before
   publication.
3. Produce a **new** versioned release receipt of the full intended
   static output, including homepage/checkout, canonical source commit,
   JS/CSS chunks, image assets and rollback snapshot. Keep Oct13 immutable.
4. Perform coordinated static promotion via the existing website owner.
   Verify public `/`, `/buy`, `/commercial`, form route behaviour and
   BSC first-buyer canary, then retire the historical pin check only through
   an approved new release contract.
5. Only a **real opted-in buyer** submitted through the existing site can
   validate the complete commercial form-to-CRM path. No fake production
   enquiries, wallet events, orders, settlement, claimed revenue or
   automatic outbound from this source convergence.

**No public files overwritten by this work. No money moved.**
Keep remaining website signoff and real first-buyer dependency in the
existing Website & Growth and Revenue & Buyers chats, respectively.

## Completed combined-stage browser verification

ASTRA's existing real Chromium/Puppeteer console reviewer ran against **the
combined isolated build**, not the older creative branch or the public server.
At 1440px, 820px, 390px and 320px the 3D scene reached its WebGL-ready state,
five console interactions were checked per viewport, and no horizontal overflow
was detected. The JSON report recorded **8/8 checks passing and 0 page
errors**, with separate screenshot captures for all four viewports.

Untracked visual screenshots and browser review JSON are retained under
`docs/evidence/flagship-console-final-20261020/` **in the clean candidate
worktree only**; they are not silently deployed or staged into production
Git. Browser verification is engineering evidence, not founder final visual
approval, real form POST proof, or a binding checkout release.

Production site is unchanged at this stage. Source-only commit and exact
path promotion can close the missing cinematic homepage *source code* gap,
but the immutable static output still requires a coordinated versioned
release and checksum/rollback validation before public launch.
