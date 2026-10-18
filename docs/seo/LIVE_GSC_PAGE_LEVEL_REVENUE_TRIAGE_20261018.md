# Empire AI: live page-level GSC after Search Intelligence activation
18 October 2026 | READ-ONLY observation | No website, CRM or financial changes

## Activation truth
The founder restarted empire-search-intelligence-api.service with an authorised
interactive command. Service status was active. The first immediate CLI read
returned GSC_PAGE_DIMENSION_NOT_YET_VERIFIED, but this generic failure did not
identify its cause. Rechecking the page-only API directly yielded HTTP 200,
source sc-domain:empire-ai.co.uk, dimensions [page], final data, count 28.
Re-running the same CLI succeeded. Do not claim a specific cause for the first
failed check; it is no longer reproducible. No further restart is required.

Canonical release commit: fa814771. Running read-only GET /health HTTP 200.

## Search Console measured page observations
Window: 2026-10-08 through 2026-10-17 (Google's final-data page dimension).
28 returned page rows. These rows carry 53 impressions and 0 clicks.
The number of returned rows and their totals are NOT proof of sitewide complete
traffic, a live rank at the time of this report, buyer identity or revenue.

One apex homepage URL: 13 impressions, 0 clicks, HTTP 200.
One www homepage URL: 3 impressions, 0 clicks, HTTP 308 to apex.
26 historical AEO URLs: 37 impressions, 0 clicks, HTTP 404 on independent
read-only GET. All 26 are absent from the present 21-URL sitemap.
  - 11 Empire-labelled AEO URLs: 14 disclosed impressions.
  - 3 historical roofing/roof-inspection URLs: 4 impressions.
  - 12 other older AEO URLs: 19 impressions.

The four priority commercial pages /industries/roofing, /industries/solar,
/industries/hvac and /predictive-revenue returned zero rows in this GSC
page-only result for this period. They are present in the live sitemap,
were HTTP 200 in the indexability probe, and have observed canonical/crawl
signals. This does NOT certify Google indexing or absence of all traffic.

## Prioritised site-ownership decisions
P0: Preserve the functioning www -> apex homepage redirect and current
commercial/proposal journeys. Do not mass-change DNS or service architecture.

P1: Review genuinely relevant historical URLs before any recovery decision.
Observed:
- /aeo/empire/ai_lead_gen/ : 2 impressions, HTTP 404
- /aeo/empire/empire_leads_engine/ : 2 impressions, HTTP 404
- /aeo/empire/empire_templates : 2 impressions, HTTP 404
- /aeo/empire/commercial_roofing/ : 1 impression, HTTP 404
- /aeo/roofing/PVD/ : 1 impression, HTTP 404
- /aeo/roof-repair/MIN/ : 2 impressions, HTTP 404
- /aeo/accounting/TAM/ : 1 impression, HTTP 404
A page's historic impressions do NOT prove its content rights, commercial
intent, traffic potential, qualified buyer or relevance to today's products.
Use the already-existing legacy 404 triage and original source/content checks.
Restore or make an exact appropriate redirect only with independently
verified replacement equivalence and website owner release.

P1: Prioritise original buyer-oriented content and internal navigation from
legitimate current pages, without thin locality duplication. Observed homepage
linked to /predictive-revenue and /commercial but lacked direct static
anchors to /industries/roofing, /industries/solar and /industries/hvac in its
HTML snapshot. ASTRA should inspect its current proposed flagship navigation
before adding the missing links, rather than override the flagship worktree.

P2: Recheck current page-only GSC metrics after processing delay; newer sector
pages were published around 15 October and a 17 October measurement cutoff is
short. Compare page dimension only with itself, never sum it with query/page
metrics. Indexability is distinct from indexed status or actual ranking.

P2: Existing SEO legacy 404 owner should decide individually whether 404 is
intentional. Unrelated antenna/install/repair locality queries can properly
stay 404; DON'T redirect them generically to products that aren't equivalent.

## Evidence limits / safety
All source HTTP requests were bounded and first-party or to the existing
loopback Search Intelligence read API; no publishing, redirects, CRM writes,
enquiry submissions, financial activation, email sends, or funds spent.
User's authorised restart was already done. No other service restart.
No new crawl service or competing agent implementation.
