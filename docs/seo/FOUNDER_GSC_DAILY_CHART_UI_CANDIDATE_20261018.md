# Empire AI — First-party GSC daily charts for the existing private SEO console
18 October 2026 | Candidate only, no production activation

## Founder-requested design trajectory
Premium branded search analytics should use the real Empire AI globe
identity, deep navy, electric blue, warm gold and polished graphing.
This iteration adds a restrained first chart panel to the existing
read-only SEO dashboard. The full cinematic logo/visual design remains
an ASTRA-coordinated, founder-reviewed subsequent enhancement. Do NOT
use the default Next.js globe.svg as an Empire brand asset.

## Working source
- Existing page: apps/search-command-centre/src/app/department/page.tsx
- Existing typed server-only client: apps/search-command-centre/src/lib/search-api.ts
- Additive local server component:
  apps/search-command-centre/src/app/department/observed-trend.tsx
- Chromium QA:
  tests/search_department_daily_chart_browser_20261018.cjs

## Chart contract
The existing department API may now optionally include gsc_daily_chart
from the previously committed source empire_os.search_intelligence.gsc_daily_series.
This is an independently validated Google Search Console DATE dimension.
It is never summed with the GSC PAGE dimension sample.

The new section displays:
- cyan bars = reported impressions for ACTUALLY OBSERVED daily rows;
- gold line and point markers = reported clicks for those same dates;
- provenance, exact date-window and observed/missing day counts;
- detailed, accessible source values in a disclosure table;
- held-state for unactivated API or daily-source availability problems.

No zero traffic is synthesized for missing days; if any dates are
unreported, the line/bars are withheld to avoid falsely joining data
across missing dates. It always keeps independent Google keyword ranks,
verified buyer enquiries, and realised revenue unverified. No paid API,
CRM write, web analytics cookie, page publishing or outbound message.
No direct client-browser data requests; Next.js server-side GET only.

Example 4–16 October 2026:
13 observed days, date-dimension 55 impressions / 1 click.
Page-dimension 76 impressions / 1 click is a DIFFERENT sample and
must not be summed with the daily chart.

## Tests and controlled promotion
Feature branch: feature/search-daily-visual-panel-20261018
Existing original private founder build remains active and unchanged.
Source is to be cherry-picked/scoped into canonical first, then staged
against the actually active frozen Founder Console; do not overwrite
its historical mailbox or commercial pipeline files.

Next.js 16.3.5 webpack production build/typecheck passed in the feature
worktree. Disposable :8871 Search Intelligence API using updated
source served validated real GSC rows, and disposable :3197 Next app
passed Chromium at 390 and 1440 pixels, checking real values,
13 source bars, click-line SVG, table rows, mobile overflow, noindex,
no POST/external calls.

Release prerequisites:
1. Explicitly approved controlled restart of existing Search
   Intelligence API, then verify that private
   /v1/search/department/review contains validated gsc_daily_chart.
2. Build a new frozen Next.js candidate on top of the exact currently
   active Founder Console; verify all existing routes still render.
3. Explicit founder approval for that precise private-only app release.
4. Verify public /department remains 404, rollback preserved. Do not
   claim authentication in the private frontend until application-level
   founder identity is independently verified.
