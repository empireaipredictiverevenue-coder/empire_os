# Empire AI — live organic discovery → genuine buyer enquiry audit

24 October 2026 | Original SEO + Website & Growth + original GTM | GET-only, no publication authority.

## Verified live observations

A same-host, bounded, 100% GET-only website audit checked the existing `https://empire-ai.co.uk/sitemap.xml` and `robots.txt`, 22 listed public URLs, their self-canonical HTML responses, meta/header noindex signals and direct internal links to the two existing commercial destinations. This checked **discovery health**, not Google index inclusion.

**Findings:** 22/22 sitemap URLs served 200; 0 duplicate sitemap entries; 0 self-canonical or observable noindex blockers; the sitemap includes all eight priority commercial/industry buyer routes. The site's separately served robots resource allows ordinary crawling and points to the proper sitemap. Existing commercial offer GET returned 10 approved offers; Predictive Revenue products GET returned 5 products. The backend routes are the existing `/v1/checkout/commercial/offers` and `/v1/checkout/predictive-revenue/products`, with **no** POST, identity access, CRM mutation or payment.

**Direct-buyer-link review queue:** Nine indexable sitemap pages expose no direct HTML `a[href]` to `/commercial` or `/predictive-revenue`: the top-level `/roofing` landing page, the five existing `/research/campaign_*` pages, and three `/aeo/` micro-pages (general contractor NYC, HVAC DFW, roofing DFW). This is **not** evidence of traffic, lost sales, absent indirect paths, or a defect requiring automatic edits. The exact pages are in the private JSON below. In particular, AEO/research pages may legitimately have an informational or homeowner intent instead of enterprise buyer intent.

**Canonical intake:** At 2026-10-24T13:06:28.667064+00:00 the original GTM observer reported `CANONICAL_COMMERCIAL_SALES_INTAKE_ZERO_OBSERVED` with source-count verification and zero both product-family enquiries. No real buyer is counted and no SEO revenue is attributed. A future GTM `HELD_*` receipt must be treated as **unknown**, not zero.

**Google ranking/indexing:** Google Search Console has not yet returned a validated post-22-October page-row comparison for the targeted live Predictive Revenue/roofing pages. Indexing, ranking lift, organic clicks and sourced enquiries remain unproven. The already-existing weekly observer states that the first complete post-release period is 23–29 October, with final analysis no earlier than 2 November 2026.

## Reproducible evidence & owner actions

- Existing one-shot read-only script: `python -B -m scripts.review_live_organic_buyer_journey_20261024`. It uses local Host-bound GETs; caps routes and response sizes; refuses offsite sitemap URLs and malformed crawl instructions; never creates another service, timer, buyer identity, contact or database user.
- New tests: `tests/test_review_live_organic_buyer_journey_20261024.py`; fail closed on off-domain locations, noindex, missing catalogue and non-authoritative CRM counts. Targeted combined original website-owner suite **34/34 passed**.
- Immutable private evidence: `/home/ubuntu/empire_releases/seo_live_organic_buyer_audit_20261024/SITE_ORGANIC_BUYER_READONLY_SNAPSHOT.json`; SHA-256 `86b6f65e00ecb0fba041e0099cbe1c308dee807561ddb6a8d0680f515e7eed7f` (owner mode 0600).
- Priority 1: finish the **separately founder-approved** existing SaaS 659→662 guarded release, then independently verify served HTML, consent and authentic buyer submission route. The earlier V2 release approval is not SaaS approval.
- Priority 2: original SEO/Website owner reviews the intent and destination of the existing top-level `/roofing` page. If an enterprise buyer CTA is appropriate, propose a *new*, narrow, owner-approved content update with rollback evidence; never conflate it with the held SaaS five-file release.
- Priority 3: assess the five research pages and three AEO pages with their actual audiences, ownership and traffic evidence before editing. Only link to live, relevant existing Empire AI services. Avoid indiscriminate CTAs, false traffic figures or made-up buyer identity.
- Priority 4: wait for finalised Search Console rows and reconcile the first **authentic** opted-in enquiry through canonical EmpireDB and tenant-bound Smart CRM. Browser clicks and page impressions are not consent, customer conversations or realised revenue.

No paid advertising, editorial spend, site or sitemap changes, automated outreach, CRM rows, payments or production scheduling were authorised or performed.

## 24 October follow-through: intent-aware internal paths and a private HVAC candidate

The original nine no-direct-B2B-link observations do NOT establish nine missing buyer journeys. The bounded SEO observer now follows only first-party anchors among the 22 already-checked sitemap pages, for at most three clicks. Live results: 8 research/AEO pages already have a route to the existing Commercial form in two clicks; the remaining /roofing page is a separately governed homeowner ZIP guidance page, not a B2B offer. No enterprise-oriented sitemap page lacks a bounded path. These are possible links, NOT proven visits or intent.

New owner-only graph receipt: /home/ubuntu/empire_releases/seo_live_organic_buyer_audit_20261024/SITE_ORGANIC_BUYER_GRAPH_20261024.json; SHA-256 070f4912e1715e783f0a9cdde8339cedcbc4f547f8a67611de88edc12a8742ab. The original immutable snapshot remains unchanged. The newest GTM canonical source is HELD_CANONICAL_ACQUISITION_OWNER_OPS_RECEIPT_REQUIRED: count UNKNOWN, not zero.

One owner-scoped HVAC improvement was staged PRIVATE ONLY from the existing AEO source scripts/_aeo_pages/hvac/DFW/index.html. Source and served live SHA-256 both 0d92d609dfec44ea53405a60ecb99716acd5d53b65af3c7879192ac3cfe0ddce. Candidate adds exactly one secondary link, Explore HVAC demand intelligence, targeting the already live /industries/hvac explanation. All existing links, original home link and canonical remain unchanged. Private candidate /home/ubuntu/empire_releases/aeo_hvac_dfw_vertical_bridge_20261024/index.html. Proposal receipt SHA-256 ee4dfe445c8236a3d1209c1b2eadd602c5f2535ad70dddece918336f79ed3ce3.

Private GET-only Chromium confirmed at 390px and 1440px that users CAN navigate /aeo/hvac/DFW/ -> /industries/hvac -> the existing /commercial#commercial-enquiry form, with a required unchecked consent box and required email field. No form submissions, external requests, asset errors or public mutation. Private browser QA SHA-256 f530f32ba09a81277b86f3ceb719ed34b6c9cc4a88aeb32dac8190197c7415ee.

This AEO candidate is NOT published or approved. The original AEO owner must independently review scope, audience, performance evidence, source rights and route-level rollback before its own separate founder approval/release. Do not bundle it into the existing SaaS 659->662 held five-file release. Existing homeowner call-admission restrictions remain untouched. Combined original website and SEO tests: 38 passed.
