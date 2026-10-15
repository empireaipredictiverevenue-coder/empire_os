# Empire AI — Original TAM buyer guide publicly released

**15 October 2026 · production source `0e073773` · Empire SEO Director / first-party organic commercial acquisition**

## Verified release and user value

The existing public page https://empire-ai.co.uk/commercial now contains an original, crawlable **"Which companies in your total addressable market are actually ready to buy?"** buyer-intent explanation. The four steps cover account/decision definition, distinguishing real buying requests from speculative business signals, verifiable buyer fit/capacity and evidence/consent/human decision discipline. Three FAQs explain what Google traffic, public triggers and buying-intent reports can and cannot prove.

This responds to a real historical topic seen in Google Search Console with **one disclosed impression and no disclosed click**, which is not evidence of demand volume, a current buyer or earned revenue. The old `/aeo/accounting/TAM/` URL was unverified and remains HTTP 404. This original guide is **not** an attempt to recreate the old copy or mass-publish AEO/location templates. Google's guidance supports original, useful content and genuine 404s when an old page has no equivalent replacement: https://developers.google.com/search/docs/fundamentals/creating-helpful-content and https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors.

## Public HTTPS and scope proof

- **`/commercial` HTTP 200**, exact SHA-256 new HTML prefix `a64b272749f2d84d`, **one H1**, section `#tam-buying-intent`, four visible evidence steps, three FAQ articles and functional same-page anchor to `#commercial-enquiry`.
- Existing first-party proposal form remains one form, one required consent checkbox, an explicit `/privacy` link and unchanged POST endpoint/data fields; its form still takes no payment or order.
- The previously approved, immutable five-section Astra `CommercialBuyerExplanation.tsx` remained unchanged. Existing site visual branding and CSP preserved.
- **9 noncolliding immutable Next assets** publicly fetched via HTTPS HTTP 200 with exact SHA-256 match.
- **9 protected static HTML files** SHA-verified unchanged: homepage, `/buy`, Predictive Revenue, consumer `/roofing`, roofing/solar/HVAC/property/legal industry pages. `/roofing` still has `noindex`; `/privacy` and `/terms` still serve their independently controlled legal pages.
- No gateway restart, Cloudflare/domain mutation, customer contact, EmpireDB write, lead transfer, payout, outbound, ad spend or new timer.

Private release custody and complete hashes:

`/srv/empire_os/runtime/public_website/seo_tam_answer_one_page_20261015_release_v1/release_receipt.json`

Backup of precisely the prior Commercial HTML is under its sibling `html/` directory. The release wrapper, from isolated worktree `feature/seo-tam-buyer-answer-20261015`, reuses SHA-pinned existing static operator `release_reviewed_seo_four_pages_20261015.py`. Its generic success label is `FOUR_PAGES_RELEASED_LOOPBACK_VERIFIED`, but the **actual receipt and source allowlist contain exactly one HTML file**, verified by strict preflight. The preceding Commercial page SHA matched the approved 15 October B2B copy release and no newer page was overwritten.

## SEO Director integration and operating truth

The read-only SEO Director report now accepts the **fourth exact scoped Commercial release receipt**, validating the new public page against its SHA. Actual live review returned:

- `seo_pages_verified_public=4`
- `original_tam_buyer_explainer_release_verified=true`
- `buyer_intent_search_metadata_release_verified=true`
- `gsc_sitewide={83 impressions, 1 organic click}` for 15 September–13 October, **before** today's website changes
- `post_release_gsc_days_in_window_max=0`
- `buyer_capacity_status=NO_VERIFIED_COMMERCIAL_CAPACITY`
- `publisher_pay_per_click_live=false`
- `www_host_redirect_review_needed=true`

**361 production regression tests passed** after publication (one existing Starlette/AnyIO deprecation warning). These are engineering checks, not traffic, enquiry, buyer, settlement or revenue proof.

Next owner priorities: correctly route the duplicate `www` homepage to the verified apex canonical through the existing gateway/Cloudflare owner; monitor real processed Google Search Console results after the release; secure one actual consented inbound business enquiry and an accepted downstream buyer contract. Do not republish old 404 paths just for keywords, claim false organic uplift or interpret a Search Console click as billable CPC.
