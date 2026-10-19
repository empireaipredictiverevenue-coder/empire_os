# Private Founder SEO GSC chart: Commercial Operations v2 reconciliation

19 October 2026 | Source-only owner handoff | NO production deployment

## Diagnosis

Founder's approved restart of only empire-search-intelligence-api.service
succeeded. Private /v1/search/department/review now returns
gsc_daily_chart with the expected strictly validated first-party DATE
dimension. The review reported 13 observed dates and 1 reported click.
GSC impressions for that historic window were 52 at inspection; these
figures are source values, not immutable fixtures.

The prior frontend preflight from 18 October correctly held because a
different owner had already deployed Commercial Operations v2, adding:
  /etc/systemd/system/empire-founder-console.service.d/97-commercial-operations-v2.conf
and selecting the immutable current working directory:
  /opt/empire-ai/founder-console-releases/commercial-ops-v2-49aba1fa

DO NOT revert or overwrite that owner's service or release.

## Reconciled frozen candidate

  /home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019

Copied the actually active Commercial Operations v2 frozen release,
preserved its commercial pipeline and
src/lib/commercial-operations-v2.ts byte-for-byte, and applied exactly:
- Updated src/app/department/page.tsx (adds observed trend section)
- Updated src/lib/search-api.ts (typed gsc_daily_chart contract)
- New src/app/department/observed-trend.tsx (real GSC bars and line)

The existing nine other private routes, including Founder Mail, CRM,
YouTube and Commercial Operations v2, remain unchanged. No files in the
active immutable release were edited.

Next.js 16.3.5 webpack production build succeeded; TypeScript passed.
Disposable 127.0.0.1:3197 preview checked all ten expected private
routes HTTP 200, plus Chromium at 390px and 1440px validated the daily
bars, separate click line, exact-value table, noindex, no horizontal
overflow, no browser external requests or POSTs. The browser test
used the now-live loopback SEO API on port 8771. No live frontend
restarts or deployment occurred.

Pinned frozen SHA256 values are in:
scripts/review_private_gsc_trend_commercial_v2_20261019.py

## Current read-only release gate

  cd /srv/empire_os
  ./.venv/bin/python -m scripts.review_private_gsc_trend_commercial_v2_20261019 --read-only

Expected when source and active owner have not changed:
FROZEN_CANDIDATE_BACKEND_READY_REQUIRES_FOUNDER_RELEASE_APPROVAL

The preflight fail-closes if: Commercial Ops v2 owner changes again;
the currently active six systemd drop-ins differ; the private routes
regress; public /department or API begins exposing data; the compiled
candidate hashes or three exact source files drift; or GSC daily data
cannot be attributed to its first-party source. It does not deploy,
restart, create an access bypass, read CRM buyers, pay for traffic,
send email, or mutate EmpireDB.

## Next approvals and exclusions

The founder explicitly approved the Search Intelligence API restart;
they have NOT separately approved changing the now-running Commercial
Operations v2 frontend. Do not infer that approval.

Once separately approved, prepare a new *owner-reconciled* drop-in
98-private-gsc-trend-release.conf that changes only the existing
empire-founder-console.service WorkingDirectory to the pinned new
candidate and preserves the existing server-only SEO API base setting.
Require exact live preflight immediately before the privileged switch,
perform post-activation validation of the ten existing routes,
no public exposure, chart evidence, and retain rollback to the
current Commercial Ops v2 immutable release.

The loopback console is not a verified application-level founder login;
do not open its private /department path publicly or claim that
independent founder authentication has been proven. GSC average
position remains different from independent, query-specific SERP rank;
no organic buyer or revenue evidence is certified by this dashboard.
