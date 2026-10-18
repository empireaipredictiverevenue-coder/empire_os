# Empire AI Search Command Centre — branded charts and first-party daily evidence

18 October 2026 | SEO measurement build | Design pass deferred to ASTRA review

## Founder direction (not yet a website/UI release)

Use the **actual Empire AI globe brand identity**, not a stock or invented
logo. Visual language: deep black/navy, electric-blue illumination with
subtle warm-gold highlights, sophisticated typography, polished controls,
cinematic depth and mobile-quality parity. Maintain current live
functionality; enhance incrementally, never reset the flagship visual
project. The visual brand system should be coordinated with ASTRA, the
flagship's current design owner.

Founder specifically requested **bars and graphs on the dashboard pages**,
making the views more attractive and actionable. Implementation is a
subsequent controlled UI design pass; this commit supplies verified data
instead. A visual theme does not confer rank/revenue authority.

## Today's backend: first-party chart-ready GSC time series

Reuse the EXISTING Search Intelligence loopback
/v1/search/search-console/daily?start_date=...&end_date=...&limit=... endpoint,
which already reads Google's Search Analytics DATE dimension. No new Google
credentials, paid keyword API, unsanctioned scraping, Supabase or service.

New safe reader:
  empire_os/search_intelligence/gsc_daily_series.py
New operator:
  scripts/review_gsc_daily_chart_readonly_20261018.py
Existing integrated department runner now emits an optional:
  gsc_daily_chart
Existing Founder Console aggregate API snapshot validates and allowlists
that optional series before rendering. No route or web UI changed.

Run directly:
  cd /srv/empire_os
  ./.venv/bin/python -m scripts.review_gsc_daily_chart_readonly_20261018 --read-only

Source example on 18 October 2026 (4–16 October window):
  date-dimension rows observed = 13
  reported clicks = 1
  reported impressions = 55
  missing dates = none

CRITICAL: **These figures are not added to or reconciled as if identical
to the already existing GSC page-dimension sample**. That sample
returned 34 page rows, one click and 76 impressions. Different GSC
dimensions, caps and reporting semantics can yield different totals.
Neither source alone proves a buyer, traffic quality, Google indexing,
or revenue. GSC's average-property position cannot be repurposed as
a verified independent SERP rank for a specific query/engine/location.
No daily dates are synthesized and unavailable dates are marked
unreported rather than filled with zero. The existing daily GSC API
does NOT report dataState=final; no final-data claim is made for these
date observations.

Potential graphs once visual release is approved:
1. **Observed organic trend** — bars for date-dimension impressions,
   an independent line for daily GSC clicks. Never stack or sum these
   against page-dimension results. Chart label explicitly says GSC
   reported date dimension, not validated unique visitors.
2. **Legacy recovery portfolio** — four-category grouped bar chart
   with product topics, roofing, buyer-intent, and retained-off-core.
   Not a bar chart of recovered Google visits; zero redirects yet.
3. **Search Fabric source health** — fresh, stale and invalid cache
   envelope bars or compact visual, NOT keyword rankings.
4. **Evidence + revenue chain** — clear sequential statuses for
   observed SERP, AI citations, qualified enquiries, actual buyer
   confirmations and canonical realised revenue. Unknown stays unknown.

Use purposeful, accessible charts with semantic axes, keyboard-visible
explanations, time labels, real source provenance and an equivalent
text/table view. Handle 0 clicks and very small numbers without
exaggerating scale. No fabricated growth percentages, trend forecasts,
marketing audience counts or green 'rank #1' badges.

## Safeguards and next work

- One bounded GET to 127.0.0.1:8771 per report execution, 31 days max.
  On unavailable/invalid source return HELD, never zero sessions.
- Only exact site_url=sc-domain:empire-ai.co.uk with dimensions=['date'].
  Strict dates/CTR/position/clicks/impression envelope checks. Reject
  duplicate or out-of-window dates and false claims of verified ranks.
- No raw keywords, buyer data, external links, cookies or credentials
  in the chart output. No DB writes, outbound, payments, ads, changes to
  the public site, Search Fabric or systemd.
- The code is staged for the **existing** Search Intelligence API source
  and is not effective in its already-running process until separately
  approved controlled restart. Next.js current deployed version is also
  unchanged by this release. ASTRA visual release requires its own
  review, source compatibility checks and founder publication approval.
- Next SEO objective: real engine-attributed live rank observations
  and independently reproducible AI answer/citation captures. Do not
  equate GSC average positions to those independent signals.
