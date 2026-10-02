# Recurring Competitive Intelligence Architecture V1

## Owner

The existing empire-opportunity-brief timer remains the single recurring owner
for competitive/account intelligence. It is upgraded from brief-only refresh to
a full evidence refresh chain rather than adding overlapping timers.

## Chain

1. Bounded market-scale competitor sweep.
2. Ecosystem, public-review and public-activity projections.
3. Search-presence refresh through public Search Fabric providers.
4. Combined competitor intelligence feed and market-opportunity projection.
5. Canonical competitor-audience refresh from EmpireDB.
6. Direct first-party/evidence re-observation with normalized content hashes.
7. Changed-page detection against the previous research snapshot.
8. Bounded extra account research for companies whose directly observed pages
   changed.
9. Claim-critic account brief and evidence-backed opportunity brief refresh.
10. Predictive Cloud status refresh for Founder-facing truth.

## Failure policy

Public-provider stages are fail-soft and retain last-good snapshots. Search
presence receives two bounded attempts and uses public-only provider rotation.
Canonical evidence and brief materialization failures are critical and make the
cycle unhealthy.

No failed stage may replace a last-good snapshot with fabricated empty truth.

## Freshness

The cycle publishes generated_at, expires_at and freshness state. The recurring
snapshot expires after two hours without a successful cycle. Ops Sentinel
monitors the timer and the cycle snapshot.

## Page changes

Direct first-party and known evidence pages receive a normalized content SHA256.
Only direct fetched content gets this hash; search snippets never impersonate
page content. A changed hash for the same entity + URL is a page change.

Changed entities may trigger one bounded deep-account research pass in that
cycle. Change research remains OBSERVE-only.

## Authority

The chain has no outreach, commercial terms, payment, allocation or revenue
authority. Competitive signals are not buyer intent or commercial intent.
