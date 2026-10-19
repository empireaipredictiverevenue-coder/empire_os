# Empire AI Analytics — evidence-first full platform revamp
19 October 2026 | Founder design + data infrastructure brief | Source-only candidate

## Mission
Convert the existing Search Command Centre into a genuine multi-source
measurement and predictive-revenue platform with GA-class navigation,
analysis, segmentation, conversion attribution and commercial linkage.
It is NOT a Google Analytics equivalent yet. Implement source truth
and real buyer/revenue evidence ahead of vanity displays.

## Brand
Reuse the currently published Empire AI official logo lockup (exact
SHA256 a89c4e6c179e6fdeb5ae1e5b140d1c6007a4f359d633f51390a9fc7a1f79a64c)
from apps/empire-public-site/out/brand/. No Vercel/Next logos or
generic invented mark. Dark navy/black, electric blue/cyan and warm
gold; 390/768/1440 responsive with accessible navigation/tables.
The user may approve a more recent globe-mark replacement through
the controlled visual review rather than editing ASTRA's flagship.

## Currently observed
- First-party Google Search Console DATE-dimension impressions,
  clicks, derived CTR and observed dates.
- Separate GSC PAGE-dimension sampled URLs/404 editorial categories.
  These two slices have different boundaries and are NOT additive.
- Search Fabric cache envelope freshness; diagnostic, NOT Google rank.
- Owned-site priority-page observations and bounded search quality.
- Existing founder CRM and commercial services, each subject to their
  OWN tenant/auth and receipt evidence authority.

## NOT currently verified as GA-type analytics
- Visitors, unique users, site sessions, engaged sessions, page_view
  events, device country cohorts and session duration.
- Consent-enabled first-party traffic source/medium/campaign reports.
- Buyer sessions linked to real leads and payment receipts.
- Sitewide Google indexing, independent SERP ranks, third-party
  AI citations and attributed realised organic revenue.
- Verified GA4 historic reports or GA4 property integration.

Unknown is presented as "Not connected" rather than 0. Search
impressions and clicks must NEVER be used as website visitor counts.

## Phase one — implemented safely in branch
- The /department page becomes an Empire-branded analytical workspace:
  sidebar with working anchor navigation; performance KPI cards;
  true GSC bars + clicks line and source-date-window; content-recovery
  distribution; page sample separately; acquisition-to-revenue path
  with unknown steps; Tag/Search source-quality status and open actions.
- /department/evidence preserves the original detailed SEO review.
- Server-only existing Search Intelligence API, no new frontend
  tracking script, worker, service, API key, DB write or paid vendor.
- Browser does not make third-party calls, POSTs or data mutation.
- Published site/ASTRA and other agents' founder files not touched.
- Private loopback URL and noindex do NOT prove application-level
  founder identity authentication. Public site must remain 404.

## Phase two — real analytics, reuse EmpireOS
1. Tag Intelligence: audit deployed page tags, missing/duplicate
   conversion events, ownership and consent-mode behavior. Observe
   only; never silently insert tags on ASTRA-owned production pages.
2. Consent-aware first-party event pipeline (inactive until founder
   and site owner approve exact deployment). Only allowlisted
   page_view, engagement, cta_click, form_start, form_submit_attempt;
   no raw IP, URL query strings, email, name, raw user agent,
   card info or free text. Bot/duplicate suppression and retention.
   Privacy review for UK PECR/GDPR and jurisdiction-specific rules.
3. Sessions, acquisition channels and funnels from real authorized
   event receipts; do not infer missing visitor sessions from GSC.
4. Server-accepted enquiry -> canonical EmpireDB CRM -> real offer ->
   actual buyer -> USDT BSC payment -> fulfilment -> realised revenue
   with tenant isolation and source-link receipts. A browser click
   or form-submit attempt does not prove a buyer.
5. True landing pages, device/geo segmentation, retention, cohort,
   funnel, source/medium/UTM, journey exploration, conversion rate,
   acquisition cost and ROAS WHEN each metric's source is available.
   Zero ad spend is a policy constraint, not a verified GA metric.
6. Predictive Revenue models with actual backtesting and calibrated
   uncertainty; avoid fake growth estimates or asserted rankings.

## Definitions
GSC impressions = search appearances, not visits.
GSC clicks = reported search clicks, not first-party sessions.
GSC CTR = clicks / impressions WITHIN the same date dimension.
GSC page samples are independent scoped URL rows.
Session = deduplicated first-party consent-qualified session receipt.
Lead = deduplicated canonical server-accepted enquiry.
Revenue = attributed, settled and realised financial proof only.
Conversion rate = verified conversions / eligible observed sessions
in the same time/property/tenant scope.
Rank = independent engine/query/locale/device/time evidence, not GSC
property-average position or a cached Search Fabric entry.

## Controlled release
Worktree: /home/ubuntu/empire_worktrees/empire_analytics_platform_revamp_20261019
Existing runtime retained. Private production console release must be
rebased/copy-merged on the actual active frozen owner, never installed
from the dirty canonical founder pages.

Initial tests: Next.js 16.3.5 webpack/TypeScript build passed,
disposable :3197 both /department and /department/evidence returned
200, Chromium 390/768/1440 passed branding, sources, missing-metric
truth, charts, logo, noindex, no horizontal overflow and no external
requests. Preserve all existing live ten routes and rollback on
future release; get separate founder visual approval.

Priority follow-up: real traffic instrumentation readiness, consent,
then actual acquisition-to-CRM revenue joins. Reuse Tag Intelligence,
the existing search service, EmpireDB and founder CRM; do not build a
duplicate parallel DB, CRM or paid analytics provider.
