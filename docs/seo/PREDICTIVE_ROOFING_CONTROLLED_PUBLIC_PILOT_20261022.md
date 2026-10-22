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
- Responsive CSS classes and a real headless Chromium 320px width check are now verified using the existing first-party Puppeteer installation. The first pre-fix 320px preview failed with 37px horizontal overflow; the updated preview measured 320px with none. Full 320/390/820/1440 combined-overlay browser checks, accessibility inspection, keyboard QA and founder visual approval must be evaluated and recorded separately before public release.
- No actual buyer enquiry is submitted as a test; the endpoint's end-to-end successful lead receipt is **not** asserted.

## Before release
1. Inspect original modified sections and branding; founder confirms exact copy and visually verifies desktop/mobile at 375px and 768px, including the existing form and top navigation.
2. Confirm current live release and Cloudflare target, preserving any website agent modifications made since the candidate commit. Production sources are multi-agent; never overwrite dirty files or a newer public release blindly.
3. Approve an exact public-site build, immutable artifact hash, self-canonical/noindex checks, footer/consent, rollback and publish gate. Approval of the private Founder Console is **not** approval to publish public copy.
4. Release only the existing two pages' improvements through the website's actual production deployment owner; do not restore any of the 30 /aeo legacy routes.
5. Postrelease verify public HTTP 200, canonical, rendered copy, mobile parity, form route/consent, absence of new phone/affiliate links and the prior static site integrity. If any regression occurs, restore the previous public artifact.

## Honest measurement
Record **separate** windows of final GSC *page-dimension* impressions, clicks and CTR for /predictive-revenue and /industries/roofing, noting reporting lag and changes in windows. Search query dimension is a separate measurement, never added to page totals. Track approved first-party enquiry receipts, verified company/customer scope, accepted deals and later economic settlements distinctly. No invented clicks, conversions, ROI or revenue. The historical legacy-404 observations are the *research input*, not the direct baseline for the two live pages.

The immediate output is a small, tested, original-content **candidate for controlled deployment**, not a live traffic or revenue claim.
