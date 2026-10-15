# Empire AI — Revenue Search Visibility and First Genuine Enquiry Gate

Observed 15 October 2026 | Read-only production verification | Owner: SEO / ASTRA flagship site / Revenue
Status: ORGANIC_DISCOVERY_LOW; LEGITIMATE_ENQUIRY_EMPTY; LIVE_FORM_CONSENT_GUARD_VERIFIED

## Source-of-truth production findings

- **Live Google Search Console, site `sc-domain:empire-ai.co.uk`**: 1–13 October (inclusive), 13 returned daily rows, **50 impressions, 1 click**. Derived site-wide CTR 2.0%. Most recent returned day: 13 October (8 impressions and 0 clicks). This is not a traffic forecast, direct site analytics or total visits; Search Console may delay/revise search records.
- The separate query/page-dimension response yielded **9 displayed rows**, summing to only 20 impressions/0 clicks, with branded homepage searches (`empire ai`) and scattered legacy AEO informational pages. These rows are NOT exhaustive because anonymised query/page results are excluded or grouped by Google. Never infer 0 impressions for the sales routes solely from absence in those 9 rows.
- Three commerce routes `/commercial`, `/buy`, `/predictive-revenue` all returned origin HTTP 200 with separate titles and self-canonical links. `/robots.txt` returned 200 with sitemap declaration and no site-wide root Disallow. `/sitemap.xml` returned 200, 20 URL `<loc>` entries, including each of the three sales routes. Publication of a URL in a sitemap does not prove Google has indexed or ranked it.
- `/privacy` and `/terms` now both return origin HTTP 200, an improvement over the 12 October privacy-route 404 in prior archived baseline. HOWEVER the currently served `/commercial` and `/predictive-revenue` HTML contains enquiry forms and contact-consent checkboxes but **no `<a href="/privacy">` link** next to or elsewhere on either sales page. `/buy` also has no directly rendered privacy link. Site visitors should be able to review a first-party privacy notice when entering contact data.
- Both live same-origin POST routes `/v1/checkout/commercial/interests` and `/v1/checkout/predictive-revenue/interests` were tested with `contact_consent=false`, returning exactly HTTP 422 `specific_contact_consent_required`. The test did not create a prospect, payment or qualified lead. Inbound successful submission has not yet been independently exercised using genuine consented customer data.
- Separate privilege-gated EmpireDB aggregate reconciliation on 15 October returned `NO_CANONICAL_SALES_ACQUISITION_OBSERVED`: `commercial_acquisition_rows=0`, `predictive_acquisition_rows=0`, `sales_acquisition_rows=0`. Tenant-visible Founder CRM prospective sales records = 0. This means there is no existing sales acquisition to rescue from tenant visibility; it does NOT certify the real buyer submission-to-CRM projection.
- First-party Search Intelligence API `/v1/search/search-console/status` returns `available=true`, site property ready, and direct actual daily observations. Generic `/v1/search/health` still reports a stale disabled state from loaded service version. Do not change credentials, disable Search Console or trust the stale health summary over successfully retrieved signed-source Google data.
- Legacy organic search recovery is running its existing daily OBSERVE timer and returned 210 REVIEW_READY source records but `publishing_authority=false`. This is not proof of 210 indexable or conversion-effective published articles; no mass-publishing.

## ASTRA flagship website change request (DO NOT EDIT FROM THIS LANE)

Priority P0 — **Privacy at collection point**:
- On both `/commercial` and `/predictive-revenue` forms, insert a visible, keyboard-accessible same-origin link to `/privacy` immediately adjacent to the explicit-contact-consent copy. Preserve its existing `required` checkbox, unchanged consent language, honeypot, API route, idempotency key, pricing, and nonbinding terms. Do NOT use a pre-checked box or bundle unrelated marketing opt-in.
- Ensure the `/privacy` notice actually describes the collecting Empire AI legal entity, source, data categories, purposes, lawful bases, UK GDPR rights/retention and correct contact channel; refer substantive compliance interpretation to founder/legal review. Do not treat a status-200 placeholder as legal approval.
- Add a prominent navigable `/privacy` link in the common site footer, including `/buy`, without disturbing the site brand design and ASTRA's 3D/globe/page system.

Priority P1 — **Useful buyer journey, not generic hero noise**:
- Preserve the three reviewed product catalogue and enquiry components. Clarify one CTA per buyer objective: `/buy` = immediate product/price evaluation (no payment claim); `/commercial` = request an advisory proposal; `/predictive-revenue` = request a specific Predictive Revenue deployment conversation. Do not promise live checkout, proof of ROI or deployment capacity unless verified.
- Reuse existing product evidence, case references and verified metrics where available; no fabricated case studies, endorsement logos, live client counts or speculative revenue uplift. Keep link paths stable.
- Internal links: homepage / enterprise solution copy / related technical evidence content should point contextually to these three money routes; avoid SEO duplicate near-identical landing pages and noindex/index toggles without a Search Console assessment.

Priority P2 — **Organic demand experiment (zero paid traffic)**:
- Favour high-specificity, buyer-intent research on terms such as `AI revenue forecasting software`, `predictive revenue forecasting for businesses`, `AI sales pipeline forecasting`, `AI consultancy for revenue operations`, and `business revenue intelligence platform`; these are **candidate topics, not measured keyword volumes or proven rankings**.
- Validate each candidate with actual Search Console page/query evidence and first-party product relevance before creating one researched page or substantive section. Target UK/US where product terms and privacy/law allow; do not assume homeowner roofing and B2B SaaS share audiences.
- Compare equivalent Google Search Console daily windows after 12 October metadata release, accounting for reporting delay and page dimensions. A rise in impressions does not count as a lead; only independently verified organic session → consented acquisition receipt → tenant visibility → accepted commercial action can measure end-to-end conversion.

## Acceptance criteria for subsequent release

1. ASTRA-owned site commit includes two privacy-link changes and one shared-footer link, with a reviewed, actual notice at `/privacy`; no breaking changes to existing page appearance.
2. Verify live origin and public edge routes return 200, all three self-canonicals unchanged and money URLs remain in the published sitemap.
3. Accessibility checks find a readable privacy notice link adjacent to each form's required contact consent; controls remain accessible on keyboard/mobile.
4. Admission regression verifies same-origin+consent required, honeypot and rate limiting intact; rejected fixture never reaches `ingest_prospect_atomic`.
5. Record GSC real observations at T+7/T+14 using comparable date ranges. No fabricated impressions/clicks, no unrelated performance claims.
6. Founder CRM remains fail-closed for unverified identity/tenant bindings; do not create fake buyer, outbound, payment or provider redirect to manufacture a conversion.

## Engineering coordination and limits

This handoff intentionally does NOT modify `apps/empire-public-site` (ASTRA is the current owner). Do NOT run another SEO timer/agent, create a second Search Console integration, install a third-party analytics pixel or pay for traffic. Both Google Search Console and Search Intelligence are already available through the approved first-party runtime, and they should remain read-only. Publisher/affiliate exclusions and consumer PII lead supply stay on separate legal gates.

**Primary commercial priority:** actual targeted visibility → one genuinely initiated consented enquiry → founder review → negotiated payable acceptance. Zero acquisitions today is a demand/readiness issue, not evidence that an existing prospect was dropped.
