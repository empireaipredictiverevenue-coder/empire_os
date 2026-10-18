# Empire AI SEO Command Centre: first-party department evidence UI
18 October 2026 | Existing Search Intelligence | OBSERVE-only

## Feature and branch
Feature branch: feature/search-department-dashboard-review-20261018
Existing canonical repository: /srv/empire_os
Staged app: apps/search-command-centre
Staged route: /department
No client-side telemetry, user form, API key, cookie, email, payment,
website mutation or new worker/timer. Existing founder-dashboard files
(apps/search-command-centre/src/app/founder/page.tsx and founder-api.ts)
were explicitly NOT changed because another agent edits them.

## Exact improvements
- Adds /v1/search/department/review to the EXISTING loopback Search
  Intelligence FastAPI router, not a new service or public site.
- New department_snapshot.py calls the existing
  empire_os.search_intelligence.department_integration_review.run.
  It produces an intentionally allowlisted aggregate-only response.
  There are no raw search queries, SERP result positions, customer
  identifiers, credentials, URLs, snippets, or buyer records.
- Per-process 15 minute TTL, lock to avoid concurrent GSC fan-out,
  finite concurrency wait, fail-closed generic 503 on missing source,
  malformed report or source outage. Never returns stale cached counts
  after an expired cache and failed refresh.
- Search Command Centre's existing server-side search-api.ts client
  gains one typed read-only method. The new /department Next.js route
  is server-rendered on demand and noindex/nofollow.
- Adds a distinct link to /department in the *existing* Command Centre
  homepage. Neither ASTRA flagship website nor its publish operator
  is touched. The global dashboard navigation is otherwise unchanged.

## Founder evidence presented
Google Search Console FINAL page-dimension window + returned URL rows,
sample impressions and sample clicks. This must not be confused with
sitewide traffic, indexing, conversions or ranking observations.
Legacy AEO 404 editorial categories with exact core-topic vs off-core
retirement decisions; no mass redirect authorizations.
Fresh/stale/invalid local Search Fabric cache evidence, separately
labelled NOT an independently verified Google rank.
Four-page semantic review, specific copy quality gaps, existing eight
specialist desks and nine unpublished research campaigns.
Independent SERP and AI citation observations, organic buyer enquiries
and revenue explicitly remain Not verified; detailed original open
evidence gates are shown.

## Verified staging checks
- Search API snapshot against real first-party sources:
  34 GSC rows, 1 reported click in returned rows; 31 historical 404;
  84 recent cached provider envelopes; 9 currently open evidence
  gates; no verified independent ranking, enquiry or revenue.
  These are time-bounded examples, not hard-coded report metrics.
- Focused API, snapshot, Search Console, Search Fabric and department
  regression tests: 123 passed with a single pre-existing anyio
  deprecation warning.
- Existing Next.js 16.3.5 full production build PASSED; /department is
  a dynamic route, not a static snapshot.
- Full site TypeScript noEmit check PASSED.
- Temporary LOCAL-only staged FastAPI :8871 and Next :3197 booted.
  HTTP GET on the staged /v1/search/department/review returned the
  expected source truth with none of the requested execution authority.
- Headless Chromium rendered /department at 390px and 1440px;
  checked key sections, GSC rows, historic 404, Search Fabric cache,
  displayed evidence holds, noindex metadata and no horizontal overflow.
  No external browser requests or POST requests.
- Preview processes closed; existing production Search Intelligence
  remains healthy on its original loopback :8771. No service restart,
  live deploy, traffic spend or customer mutation executed.

## Promotion plan for the existing owners
1. Integrate this exact scoped branch into canonical EmpireOS only after
   checking all six source paths for active concurrent edits.
2. Re-run Python and TypeScript tests on canonical, preserving the
   working founder UI and ASTRA flagship changes.
3. Separately coordinate a bounded rebuild/restart of the EXISTING
   Search Intelligence API to register the new GET route.
4. Use the EXISTING Search Command Centre app release process to
   publish /department; check server-only EMPIRE_SEARCH_API_BASE_URL.
5. Perform live founder-browser and safe availability checks without
   creating a fake buyer, redirect, SERP position or Google conversion.

Successful source integration alone does NOT mean /department is live.
The new route is a measured, reviewable candidate until the owner
accepts and deploys it.
