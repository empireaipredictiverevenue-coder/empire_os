# Empire AI — Search Console Lost-URL Revenue Triage

15 October 2026 | OBSERVE, read-only one-shot | SEO / ASTRA website coordination

## Actual live data — do not confuse GSC query/page coverage with totals

- Google Search Console property: `sc-domain:empire-ai.co.uk` (existing approved first-party Search Intelligence GET adapter at `127.0.0.1:8771/v1/search`).
- Query window 1–13 October 2026 (inclusive). 13 daily rows show site-wide **50 impressions and 1 click**. This is **not** qualified traffic, enquiry volume or sales.
- Google returned **9 query/page rows totalling 20 disclosed impressions**. Those rows are a partial disclosure, not the complete site-day count: Google may anonymise or suppress queries, so the remaining 30 impressions must NOT be apportioned to any page.
- Same-origin HTTP 200 observed for homepage query rows. Six exact URL paths from the other query/page rows returned HTTP **404** on a fresh live origin GET. They account for **11 disclosed impressions** and zero disclosed clicks. They are not proof of visits or forgone purchases.
- Search Intelligence `/v1/search/health` generic adapter status may report disabled despite the actual `/search-console/status` and real GSC GET rows showing approved ready. The latter + provider-returned data are authoritative; do not rotate or disable credentials.

## Page-level prioritisation (never auto-redirect)

| Previously displayed search URL | Disclosed impressions | Current origin HTTP | Revenue action |
| --- | ---: | ---: | --- |
| `/aeo/accounting/TAM/` | 1 | 404 | **P1 buyer-intent editorial review**. Historic search phrasing asks how to find which accounts in a TAM are ready to buy. Relates to buyer-intelligence/category problem; verify first-party source/evidence and genuine offering before recovering original page or adding a contextual answer to an existing product page. |
| `/aeo/antenna-install/EUG/` | 4 | 404 | P3 off-core topic; don't publish filler or redirect to business software. Preserve 404 unless substantively equivalent useful source material and publisher authority can be proven. |
| `/aeo/antenna-install/FAR/` | 3 | 404 | P3 same off-core subject, no broad speculative new index. |
| `/aeo/leak-detection/DAL/` | 1 | 404 | P3 service-specific / B2C query, not evidence of a Predictive Revenue software buyer. |
| `/aeo/bathroom-remodel/POR` | 1 | 404 | P3 service-specific query; separately review if part of a funded consumer lead programme. |
| `/aeo/kitchen-remodel/LON/` | 1 | 404 | P3 service-specific/ambiguous query; no automatic redirect. |

These six are exact observed GET statuses and partial Google disclosure; SEO must review the most commercially relevant surviving subject before creating anything. The legacy recovery register has 210 review-ready assets, but an exact `/aeo/accounting/TAM/` record was NOT located there on 15 October. The snapshot does not prove there is a lawful original article to restore. No indexing/publication authority has been granted to that register.

## Existing, priced products and lawful CTA fit

The active, nonbinding `/v1/checkout/commercial/offers` catalogue includes `search_opportunity_map` ($249), `competitor_search_gap` ($199), `technical_search_audit` ($299), and consultancy opportunity assessment (£2,500). The separate Predictive Revenue catalogue includes a diagnostic from $25,000. These are **offer policy**, not completed customer delivery, realised revenue, or a basis for claiming the old accounting/TAM query maps directly to a paid product. Exact product fit needs editorial and sales review.

Potential unique page angle (RESEARCH ONLY): `How to tell which companies in your total addressable market are showing real buying intent`. Avoid predicting named buyers without verified entity identity, observed consented intent and current evidence. Outline: decision criteria, public signals vs misleading proxies, evidence provenance, false positives, verified buyer capacity, review process, and a genuinely relevant first-party nonbinding proposal CTA. Do not copy unknown historic /aeo text, publish a near-duplicate city template, or promise a measured propensity model absent model proof.

## One-shot operator installed in existing EmpireOS runtime

`scripts/review_live_search_404_revenue_readonly.py`: reads ONLY the already-live Search Intelligence Search Console **status, daily and query/page GET** routes (no new provider auth), validates exact `sc-domain` identity, limits historical date window and query/page payload, then checks only allowlisted same-origin public SEO routes via GET. Rejects untrusted external URL hosts, ports, query strings, encoded private paths, redirects, malformed counts and negative metrics. Raw search phrases and PII are never emitted. It does not write to the DB, touch sitemap/files, start a timer, post content, enable redirects, send mail or buy ads.

Verification status when last run: `OBSERVED_404_REVIEW_QUEUE`, 6 broken paths, 11 disclosed impressions, 1 identified revenue-topic *research hypothesis*, Search Console query/page coverage explicitly incomplete, zero publication and traffic authority.

**Repeat existing one-shot observation:** `cd /srv/empire_os && ./.venv/bin/python -m scripts.review_live_search_404_revenue_readonly` (unprivileged GET only; new results depend on Google reporting lag). Do not schedule duplicates of the existing SEO department. The output is *review*, never an auto-redirect instruction.

## Revenue owner actions

1. **SEO**: review the exact historic TAM/accounting question, first-party source availability and topical product fit. Prepare one differentiated buyer-intent problem/answer section, not more generic AEO doorway pages. Ranking/keyword volume, conversion rates and realised GP remain unknown.
2. **ASTRA website**: fold accepted answer into a relevant existing first-party commercial/intelligence page during the flagship redesign. Preserve approved `/commercial` form and working `/buy` catalogue. Add visible `/privacy` links at both consent forms as separately documented in `REVENUE_SEARCH_VISIBILITY_AND_FIRST_ENQUIRY_GATE_20261015.md`; site owner controls publication.
3. **SEO operations**: retain 404 for unrelated topics unless original content, intent match, rights and an appropriate equivalent destination are reviewed. Never redirect a page about antenna installation to a buyer-intelligence homepage solely to inflate traffic.
4. **Founder revenue**: validate a first legitimate opted-in proposal enquiry using canonical EmpireDB source receipt, person/company identity and tenant-scoped Founder CRM. Separate attribution from Google impression counts. No manufactured enquiries or inferred settlement.

**No changes:** public site, live CDN, Cloudflare, redirects, robots, sitemap, founder mailbox, consumer/affiliate intake, payments, named contacts, identity DB, other agents' code or credentials.
