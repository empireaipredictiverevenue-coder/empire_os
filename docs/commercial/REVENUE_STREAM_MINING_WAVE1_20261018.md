# Empire AI — Predictive Cloud / Predictive Revenue Stream Mining Wave 1

18 October 2026 | Original flagship mission | GBP £0 external spend
Branch: `feature/predictive-decision-control-20261018`

## Purpose

Move from passive data collection to **continuous intelligence grounded in
first-party source evidence**, without inventing buyer intent or price,
generating fictional probabilities, scraping personal contacts, or adding a
parallel CRM, data lake, agent network or task queue.

Canonical database: EmpireDB PostgreSQL. Search Fabric, Acquisition, Sensor
Mesh, Opportunity Radar, Source Intelligence, Quant Brain, Predictive Cloud
and Economic Memory remain the upstream/downstream authority.

This wave only adds a safe, bounded **stream mining bridge** over four existing
source projections, routes research gaps to existing department specialists and
shows their source evidence in the Founder Console after coordinated merge.

## Four stream adapters reused, not duplicated

| Canonical source | Read path | Department use | Truth and constraints |
|---|---|---|---|
| Acquisition Signal Inbox | `runtime/acquisition/signal_inbox.json` | Pre-identity source-quality mining | A signal or permit is NOT a resolved property owner, paying buyer or permission to send |
| Opportunity Factory Evidence Router | `runtime/opportunity_factory/evidence_routes_latest.json` | Public gap research and genuine commercial-evidence follow-up | Source blockers are evidence requests, not scores |
| Opportunity Factory Quant Review | `runtime/opportunity_factory/quant_review_latest.json` | Missing probability, unit economics and time-to-revenue source review | Unknown numeric values never become zero or extrapolated forecasts |
| Competitor Intelligence Feed | `runtime/competitive_intelligence/competitor_intelligence_feed_latest.json` | Marketing research source freshness | A stale roster is NOT current market share, buyer demand or a verified sale |

All files are read with bounded sizes, schema and/or record checks,
observation-only authority and UTC freshness checks. The outputs are
aggregated, allowlisted and free of raw name, email, phone, address,
customer-level records or source text. Tenant-scoped opportunity/Quant rows
are held out of the founder-global mining review rather than silently shared.

### Current observed counts (read-only, 18 October)

- Acquisition inbox: **64 distinct pre-identity signals**, of which **50
  are permit-family** and **14 are other-source** observations.
- Opportunity Factory: **8 existing candidates** with **8 public evidence
  questions**, **16 commercial-observation gaps**, and **56 separate internal
  analysis gaps**. These are blocker occurrences, NOT 80 independent leads.
- Quant: **8 evaluated candidates; none has all validated expected value,
  conversion, cost and uncertainty evidence**.
- Competitive intelligence: snapshot from September; **STALE**, not used as
  live competitor evidence.
- The rolling 24-hour count is display-only; it is removed from the stable
  fingerprint. Expiring time windows therefore don't create fake new work.
- The current counts will change as the existing upstream streams update.

## Department mining briefs

Existing `DepartmentWorkQueue` only. No additional task bus.

1. `business_development` — mine **genuine first-party** buyer requests,
   pricing and commercial terms; public search cannot establish these.
2. `data_quant` — find actual market and offer economics and calibrated
   probability inputs; do not turn search counts into conversion probabilities.
3. `market_intelligence` — research existing public opportunity evidence
   gaps through primary sources, with independent references.
4. `market_intelligence` — review 14 non-permit acquisition signals for
   source quality and useful vertical/regional research; avoid duplicating the
   existing specialist NYC permit review.
5. `marketing_growth` — competitor stream is held as stale pending refresh
   via the existing Marketing / Search Intelligence systems, not automatically
   enqueued by this release.

Queued tasks contain only source references, counts, stable fingerprints,
department ownership, `authority=observe` and explicit £0 requested
external spend. They do not create prospects, send messages, perform economic
transactions or publish content. They require the existing worker to complete
its analysis; a queued task is NOT a finished research report.

## Execution and replay

Read-only review:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -m \
  scripts.review_revenue_stream_mining_20261018 --review-only
```

Founder-authorised bounded internal handoff (not an external-source fetch):

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -m \
  scripts.review_revenue_stream_mining_20261018 --enqueue-internal --max-jobs 4
```

**Actual 18 October founder-directed one-time internal queue handoff:**
4 jobs newly accepted, 0 duplicates, with `observe` authority and 0 external
cost. A replay returned 0 new, 4 preexisting. Each was verified in the
canonical `runtime/departments/work/ready` folder. No new scheduler,
model service, database table, send, charge or scraper was installed.
Worker completion has **not** been independently observed.

For future recurring analysis, extend the EXISTING source-intelligence
cycle/department cadence via its owner after merging and source QA. Do NOT
create a new timer before coordination.

## Candidate additional public streams for Wave 2 (not yet running)

### England: official Planning Data API (beta/incomplete)
- Official: https://www.planning.data.gov.uk/docs
- Datasets include planning constraints and a developing
  `planning-application` dataset, with date/geography filters and pagination.
- API is beta. Local authorities do not universally publish planning
  applications to this standard. **No absence-of-application inference.**
- Adapter should use strict allowlisted origin, conservative limits and
  rate control; no applicant names, domestic addresses or personal contacts
  in automatic mining packets. Verify per-source licence and attribution.
- The existing permit/property Source Intelligence specialist remains the
  consuming department, not a new buyer CRM.

### United States: NYC DOB NOW permits (already implemented)
- Existing first-party ingestion: `empire_os/dobnow_incremental.py`.
- Official NYC Open Data guidance:
  https://www.nyc.gov/opendata/get-started/user-guides/open-data-apis
- Reuse the existing bounded keyset, day completeness/revision tracking and
  signal-inbox writer. Do not add a duplicate Socrata crawler.

### Search Intelligence: connected GSC (already implemented)
- The Search Analytics API supports click, impression, country, device and
  query/page observations subject to quota and result limits.
  https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- Reuse the established Google Search Console property and Search Fabric
  observer. Its partial query rows must not be treated as full search demand.
- Do not trigger paid traffic or transform ranks into sales predictions.

### Common Crawl historical domain graph (already reviewed)
- Historical graph observations are not live backlinks, buying intent, or
  consent to contact; continue existing `free_dataset_intelligence`.

## Tests, monitoring and exit criterion

- `tests/test_revenue_stream_mining.py` verifies absence of PII in outputs,
  validity/freshness, blocker semantics, source-drift rejection, tenant holds,
  replay dedup, £0 budgets and same-queue dispatch.
- Existing `tests/test_source_intelligence*.py` and Founder Console API
  integration tests remain in the regression suite.
- Before claiming new leads or predictive performance: confirm independently
  identified real buyer, legally reusable product/source data, offer and terms,
  record a time-safe original prediction, observe a verified terminal outcome
  and reconcile recognized revenue through Economic Memory.

No code in this wave authorizes new external source polling, publication,
outbound sales or financial actions. Production Founder Console has NOT been
restarted or deployed; only four bounded internal review tasks were enqueued
in the already operating department queue.
