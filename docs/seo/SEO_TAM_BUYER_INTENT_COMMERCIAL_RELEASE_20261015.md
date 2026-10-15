# Empire AI SEO Director — original TAM buying-intent answer

**15 October 2026 · first-party Search Intelligence + existing flagship website · release type: one B2B page only**

## Grounded demand and editorial decision

An actual, bounded Google Search Console query/page observation on the authorised `sc-domain:empire-ai.co.uk` property referenced the older `/aeo/accounting/TAM/` URL with **one disclosed search impression**, zero disclosed clicks and HTTP **404** today. The private research review in `docs/commercial/LIVE_GSC_LEGACY_404_REVENUE_TRIAGE_20261015.md` identified the topic — distinguishing companies that might fit a total addressable market from companies actually making a buying decision. The original historic AEO article **was not verified** and must not be recreated from imagination or redirected automatically.

Instead, the existing `/commercial` page now gets an original, user-facing guide answering **“Which companies in your total addressable market are actually ready to buy?”**. It provides a clear four-stage assessment:

1. Define the account, geography and business decision
2. Distinguish a relevant observed buying request from a weaker business signal
3. Verify fit, buyer service capacity and contract-level acceptance criteria
4. Preserve source provenance, consent, human review and realised-revenue evidence

Three original FAQs explain TAM account research, false intent inference from website clicks and what belongs in a useful report. The copy explicitly states that a Google click is not an identified buyer, consent, commission or settled revenue. No claimed customer case study, arbitrary prospect identity, payout, conversion-rate figure or hidden 404 redirect is inserted. The content links to the pre-existing `#commercial-enquiry` form section and does not create a new form, API or affiliate clickout.

## Source and build scope

- New `apps/empire-public-site/src/components/TamBuyingIntentEvidenceGuide.tsx`, styled with the already-established premium dark navy, cyan and emerald design tokens
- One import, one existing form anchor and one component insertion into `apps/empire-public-site/src/app/commercial/page.tsx`
- Original 14 October `CommercialBuyerExplanation.tsx` and `PredictiveRevenueBuyerExplanation.tsx` retain their proven SHA-256 unchanged
- Existing `seo_publication_impact_review.py` and one-shot observer updated for **optional, exact fourth release receipt scoped only to `commercial.html`**; any changed live page without a matching release receipt still fails closed
- New unit/static HTML tests check 4 evidence steps, 3 FAQs, semantic H1/H2, original five section IDs, original required consent and privacy, no new form/callback/click redirect and original buyer route noindex

A clean **Next.js 16.3.5 Webpack static build of all 17 routes** passed with TypeScript checking. Built `/commercial` HTML has one H1 and original form; the TAM guide adds four numbered steps and three original FAQs; the other existing pages remain semantically unchanged. The candidate build contained **nine new immutable versioned assets** with no existing asset-content collisions.

Google guidance: create original, useful content for people rather than mass-generated thin SEO pages; retain proper 404/410 on old URLs with no equivalent live replacement. Primary technical documentation: https://developers.google.com/search/docs/fundamentals/creating-helpful-content and https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors. No claim of improved ranking, traffic, indexed keywords, conversion or realised revenue is justified by this release.

## Publication and evidence gates

This content is intended for the **existing `/commercial` page only** with a private one-shot rollout receipt, previous pre-release SHA match, locked git source/head and immutable asset hashes. Do not alter active public gateway or Cloudflare configuration; its legal publication work belongs to another owner. Protect `/predictive-revenue`, `/industries/roofing`, `/industries/solar`, consumer `/roofing` (`noindex`), `/buy`, homepage and unrelated industry routes. Deploy only after exact live HTTP and rollback checks.

Keep all existing SEO timers, EmpireDB authority and Founder CRM unchanged. The Search Console baseline of 83 sitewide impressions/1 click is **pre-publication** and cannot prove this page attracts paid buyers. Sitewide GSC data and visible query+page rows remain different scopes; no source-to-revenue attribution is claimed. Paid PPC, pay-per-lead, pay-per-call and automated outbound remain fail-closed pending actual buyer agreements and consent.
