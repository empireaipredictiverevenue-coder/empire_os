# Empire AI — first controlled organic SEO public-site pilot

**22 October 2026 · REVIEW AND STAGED BUILD ONLY · no public release approval**

## Objective
Use the real Jev/GSC investigation as editorial research prioritisation. Create substantive improvements on **two existing canonical pages**, not restore the historical 30 URL paths or generate doorway pages. These are original explanatory improvements, not evidence of customer results.

- Source evidence: 30 first-party GSC legacy-404 page observations, 44 historical sampled impressions, zero observed clicks, Jev recommending SOURCE_AUDIT for 30 cases. 15 potentially relevant topics / 19 impressions; 15 off-core / 25 impressions. These numbers do **not** establish future SEO demand or a buyer.
- Existing flagship /predictive-revenue and B2B /industries/roofing return HTTP 200 and have an established customer-review route at /commercial. No first-party buyer opportunity, ranking uplift or paid event has been established by this pilot.

## Candidate changes (additive; four site source files)
1. `apps/empire-public-site/src/components/PredictiveRevenueBuyerExplanation.tsx`: one new plain-language answer to **How do you test a revenue forecast against actual results?** Requires dated snapshot and cohort, independent opportunity/order/payment outcomes, cancellations and missing states. Does not promise forecasting performance, invent customer testimonials or change product pricing.
2. `apps/empire-public-site/src/app/predictive-revenue/layout.tsx`: tighter B2B forecasting title/description. **Canonical was already correct and is preserved** as https://empire-ai.co.uk/predictive-revenue. No generic homepage canonical override required.
3. `apps/empire-public-site/src/lib/industry-buying-editorial.ts`: one new B2B roofing buyer checklist: distinguish tracked visitor, attempted call, independently observed buyer connection, written accepted event and settlement. The existing sector CTA remains /commercial. Does NOT activate Ringba, buyer route, homeowner transfer, national coverage, payout or real call routing.

4. `apps/empire-public-site/src/app/predictive-revenue/page.tsx`: one-line responsive header change (`flex-wrap` and mobile gap). The original 320px Chromium preview exposed a 357px document scroll width caused by the navigation badge. Rebuilt candidate Chromium diagnostic measured 320px after the fix; no form submission, pricing, attribution or payment logic changed.

No changes to `/roofing` consumer acquisition, the two homeowner guides (including their existing robots policies), site hero, animations, company forms, privacy, payment APIs, outbound, contact suppression, redirects, static sitemap or other industry pages.

## Build evidence
- Next.js 16.3.5 `next build --webpack` compiled and completed TypeScript and static generation for all 19 pages in the isolated worktree.
- This is a **static export**, so testing with `next start` is incorrect. Validation uses actual `out/*.html` and `scripts/verify_public_seo_pilot_candidate_20261022.py --export-dir .../out`.
- Static HTML gate verifies self-canonical, single H1/main, unique title/description, original copy in prerendered HTML, nonbinding B2B form, opt-in and privacy links, no new tel/insecure links, existing solar and consumer educational disclaimers, consumer guide noindex and no legacy AEO restoration.
- Chromium evidence: the initial candidate failed at 320px (357px scroll width) and remains held for audit. After the one-line responsive fix, the corrected **653-file private overlay** passed eight route checks at 320/390/820/1440, two commercial-navigation checks, zero missing local assets, zero browser page errors and zero GETs outside the private localhost origin. This is automated viewport QA, not a full WCAG, keyboard, Core Web Vitals or independent visual sign-off.
- No actual buyer enquiry is submitted as a test; the endpoint's end-to-end successful lead receipt is **not** asserted.

## Two-page-only deployment package — privately built and browser-tested

**Source commit:** `79dd421bb`. Corrected static export: `/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/candidate-79dd421bb/export`, pinned manifest SHA-256 `22aec3e4aaf3e85e38c6e8a614e940e76088f680a55ef99aa2a858c12019aaef`.

**Private combined release candidate:** `/home/ubuntu/empire_releases/seo_predictive_roofing_public_pilot_20261022/overlay-79dd421bb/out`. It preserves **all 645 current public site files**, replaces only four page/navigation files (`predictive-revenue.html`, `predictive-revenue.txt`, `industries/roofing.html`, `industries/roofing.txt`) and adds **eight collision-free hashed assets**, producing **653 files**. No direct wholesale 154-file export release; it would lose mixed-generation public pages/assets. Combined release receipt SHA-256 `2f33238d06878150d908663b1ec3415a415db62ad7266254f2438a0899edc62a`.

**Private browser receipt:** `overlay-79dd421bb/BROWSER_CANDIDATE_QA.json`, SHA-256 `8565d384217bfa4674195e4990db9a0b4f75e8f0b1589b449513f49bbeba919f`. Automated Chromium checks passed on both changed pages and at mobile widths, and existing `/commercial` navigation worked. Private 390px screenshot evidence exists for both pages. Forms were never submitted and real service GETs were stubbed rather than contacting buyers.

Two nonpublishing checks are available:

`python -B -m scripts.prepare_predictive_roofing_mobile_overlay_20261022 --verify-private`

`node scripts/review_predictive_roofing_mobile_overlay_browser_20261022.cjs` (one-time evidence creation; an existing receipt deliberately prevents rerun)

## Before release
1. Inspect original modified sections and branding; founder confirms exact copy and visually verifies desktop/mobile at 375px and 768px, including the existing form and top navigation.
2. Confirm current live release and Cloudflare target, preserving any website agent modifications made since the candidate commit. Production sources are multi-agent; never overwrite dirty files or a newer public release blindly.
3. Approve an exact public-site build, immutable artifact hash, self-canonical/noindex checks, footer/consent, rollback and publish gate. Approval of the private Founder Console is **not** approval to publish public copy.
4. Release only the existing two pages' improvements through the website's actual production deployment owner; do not restore any of the 30 /aeo legacy routes.
5. Postrelease verify public HTTP 200, canonical, rendered copy, mobile parity, form route/consent, absence of new phone/affiliate links and the prior static site integrity. If any regression occurs, restore the previous public artifact.

## Honest measurement
Record **separate** windows of final GSC *page-dimension* impressions, clicks and CTR for /predictive-revenue and /industries/roofing, noting reporting lag and changes in windows. Search query dimension is a separate measurement, never added to page totals. Track approved first-party enquiry receipts, verified company/customer scope, accepted deals and later economic settlements distinctly. No invented clicks, conversions, ROI or revenue. The historical legacy-404 observations are the *research input*, not the direct baseline for the two live pages.

**Prepublication page-level GSC check (read-only, 22 October):** existing first-party page-only reader returned 32 page rows for 7–19 October 2026, and both `/predictive-revenue` and `/industries/roofing` are `NO_PAGE_IN_RETURNED_GSC_ROWS`. This is **not** a claim that the pages are unindexed, had zero actual views or cannot rank; we have no evidenced page-specific clicks/impressions baseline for that window. Post-publication comparisons must use new matching page-only GSC windows, separately from submitted first-party enquiries and actual commercial acceptance.

The immediate output is a small, tested, original-content **candidate for controlled deployment**, not a live traffic or revenue claim.
