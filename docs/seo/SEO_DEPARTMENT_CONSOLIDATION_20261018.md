# Empire AI — SEO / AEO / GEO / A2A department integration
18 October 2026 | Sovereign EmpireOS | £0 external spend | Existing marketing_growth

## Objective and ownership
Unify **previously completed but isolated** research and read-only SEO work
without restarting the search platform, creating more agents/timers, using
unapproved paid SERP feeds, or overwriting ASTRA's website.

Source base: /srv/empire_os canonical agent/data-cloud-wave4.
Integration branch: feature/seo-department-consolidation-20261018.
Owner of marketing decisions remains existing marketing_growth / marketing
director, coordinated with Search Intelligence and ASTRA's publisher.
Canonical DB remains EmpireDB PostgreSQL; there is no Supabase dependency.

## Existing code brought into one checked-out workspace

1. FOUR-SURFACE DISCOVERY: From
   feature/search-answer-agent-discovery-observer-20261016:
   - empire_os/search_intelligence/four_surface_discovery.py
   - scripts/review_four_surface_discovery_readonly.py
   - tests/test_four_surface_discovery_readonly.py and original source contract
   This reads exact owned public HTML, sitemap and public A2A capability JSON,
   without following redirects. It NEVER asserts real AI citations or hidden
   answer-engine rankings.

2. LIVE ORGANIC INTEGRITY: From
   review/organic-live-integrity-20261018:
   - empire_os/organic_live_release_integrity.py
   - scripts/review_organic_live_release_integrity_20261018.py
   - tests/test_organic_live_release_integrity_20261018.py
   - tests/test_solar_first_live_measurement_review_20261018.py
   - original integrity, solar, and explicitly UNAPPROVED draft evidence
   The verifier compares byte-exact live/static and release custody to
   rollback inventories. This does not grant campaign measurement authority.
   The existing live audit said LIVE_BYTES_VERIFIED, but the canonical
   source-commit provenance is still false and the industry campaign release
   registration is absent.

3. EXISTING MULTI-DESK GROWTH RESEARCH: From
   feature/search-growth-department-research-20261016:
   - scripts/review_search_growth_department_portfolio_20261016.py
   - scripts/review_search_editorial_quality_20261016.py
   - two source test modules and the ten original marketing research /
     editorial source documents, including the research portfolio manifest,
     authentic Empire service copy and first campaign article/brief.
   Eight specialist desks and nine research-only campaigns are available
   to the **existing** marketing department. Research priority scores
   are NOT live keyword ranks, click forecasts, campaign approvals, or sales.
   No content was published and no outreach sent.

4. SAME FIRST-PARTY SOURCES ALREADY IN CANONICAL:
   - Search Intelligence read-only API on loopback 8771.
   - First-party GSC page dimension reader.
   - Existing 404/legacy page audit (26 historical 404s from 28
     returned page rows in 8–17 October final GSC data).
   - Existing historic search, products, robots, sitemap, indexation,
     citation, competitor, technical and rank-history preview modules.
   - Existing organic recovery timer (no extra timer installed).
   No duplicate search engine, database, external AI service or crawler.

## New small integration contract
empire_os/search_intelligence/department_integration_review.py
scripts/review_seo_department_integrated_20261018.py
tests/test_search_department_integrated_20261018.py

Run once from EmpireOS:
  ./.venv/bin/python -m scripts.review_seo_department_integrated_20261018 --review-only --start-date 2026-10-08 --end-date 2026-10-17

For a rolling history window, omit both dates to use the most recent
previously final period. The command does exact allowlisted GETs / owned
release file reads and joins only compatible, bounded source envelopes.
Unknown or mismatched provenance returns HELD, not zero traffic.

**Latest integrated live observation**:
- Four owned SEO/AEO/A2A discovery routes/groups healthy; historic DFW
  answer page has contextual roofing link.
- 28 page-only GSC rows returned; this sample cannot certify sitewide
  clicks, keyword ranks or page indexation.
- 26 historic allowed AEO 404s, 37 page-dimension impressions and 0
  reported clicks in the historical returned rows; no redirects issued.
- Organic release bytes verified; source-commit and campaign measurement
  release gates still open.
- 8 specialist desks, 9 research-only campaigns; zero send/publish/spend.
- Real AI recommendations/citations, independent rank observations,
  real consumer conversions and paid settlements NOT proven.

## Registered work that remains genuinely unfinished
- Verify Search Fabric / independent rank-history observations, actual
  ownership and response dates; don't infer ranking from GSC impressions.
- Capture independent AI-answer citations or leave UNKNOWN.
- Review original historical AEO pages against current canonical industry
  content; don't mass redirect 404s or generate thin near-duplicates.
- Bring ASTRA's separately tested 18-page cinematic flagship sector-
  navigation release to founder review. No website mutation was attempted.
  The public Dental page still needs correct publication.
- Resolve precise original campaign release/provenance and independently
  validate organic event receipts before adding conversion counts.
- Complete SEO Command Centre owner UI, report/export and paid customer
  evidence once the corresponding read sources are approved.
- Verify a genuine consented customer request reaches the correct tenant
  CRM, with canonical EmpireDB receipt before recognizing revenue.
- Pending growth articles/pitches are drafts; normal founder editorial
  and communication approval applies.

## Integration proof and boundaries
Run regression suite:
  ./.venv/bin/python -m pytest -q \
    tests/test_search_department_integrated_20261018.py \
    tests/test_four_surface_discovery_readonly.py \
    tests/test_organic_live_release_integrity_20261018.py \
    tests/test_solar_first_live_measurement_review_20261018.py \
    tests/marketing/test_search_growth_department_portfolio_20261016.py \
    tests/marketing/test_search_editorial_quality_20261016.py

Result on staged integration: 78 passing tests. A real bounded integrated
live review returned DEPARTMENT_CONNECTED_EVIDENCE_GAPS_OPEN.
Unverified is NOT transformed into verified by adding report fields.
No production site, payment, outbound, database, systemd or source
credential changes occurred; no client/customer rows were disclosed.
