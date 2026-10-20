# EMPIRE AI — Real-data mining for founder-prompted B2B targeting
20 October 2026 | Branch: feature/a2a-commercial-signal-mining-20261020

## Correction: source mining was missing

Prior A2A work produced natural-language targeting profiles, a live hourly
research decision engine, six prepared owner pickup tickets and a signed
owner-response protocol. It did NOT mine and deduplicate individual public
business-domain evidence from the existing data sources. This iteration
adds that missing extraction stage.

**This is mining of actual existing owner-issued observations, not a live
new crawler or a verified prospect/enquiry list.** Real public source results
currently lack precise city and explicitly evidenced purchasing intent.

## Implemented

- empire_os/a2a_b2b_evidence_mining_v1.py:
  - Reads actual Buyer Scout public research seeds, current Buyer Scout
    research candidates, and the NYC three-agency permit report.
  - Validates required owner schemas, timestamp and observe-only authority.
  - Mines public business-domain evidence (no personal emails or phones),
    vertical/country annotations and source references.
  - Normalises and deduplicates repeated source domains across owner reports;
    source overlap is not proof of independent confirmation.
  - Retains preliminary intermediary/reseller caveats so brokers do not
    automatically become direct customers.
  - Joins only to founder-requested verticals. US nationwide evidence is
    explicitly NOT treated as Tampa / Little Rock city verification.
  - Aggregates NYC permit event-level diagnostics as construction MARKET
    CONTEXT, NOT an available consumer lead list or verified purchasers.
  - Refuses invalid source authority, claimed real buyer capacity, asserted
    unverified permits-as-buyers, invalid domain syntax or missing owner
    governance facts.
  - If owner report is unavailable or untrusted, generates a fresh structured
    hold: unknown mining coverage, not a misleading zero-demand claim.

- scripts/run_a2a_commercial_intelligence_cycle_v2_20261020.py:
  - The existing hourly user-level worker now refreshes
    runtime/a2a_commercial_signal_mining/targeted_business_evidence_mining_v1.json
  plus targeted_business_mining_history_v1.json
  - No extra scheduled research worker, no background scrapers, no new keys.
  - Reads existing owner snapshots as issued. Does not send messages, modify
    the canonical Buyer Scout, export customer data, spend, or request payment.

- empire_os/a2a_b2b_mining_history_v1.py:
  - Bounded 90-entry digest-based history of actual owner snapshot changes.
  - Stores source counts and market research coverage, not personal identities
    or full public-domain histories.
  - An unchanged research source does not become another new discovery.
  - Buyer Scout source rotation does not mean buyers have been won/lost.
- scripts/inspect_targeted_b2b_data_mining_20261020.py:
  - Selective, safe inspection of a founder-requested industry/city result,
    including public business domains and source annotation for existing owner
    review. Contact is NOT authorised.
  - Sample:
    PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
      -m scripts.inspect_targeted_b2b_data_mining_20261020 \
      --market "tampa, fl" --limit 10

## Actual runtime data, 20 October 2026

Real owner sources:
- Buyer Scout public research seeds: 20 rows. These include existing public
  corporate references, but ZERO newly verified buyer capacity, price, terms
  or outreach permission in the source.
- Buyer Scout snapshot is a ROTATING research window: 11 candidate rows
  in one inspected run and 1 row after the owner regenerated its report at
  2026-10-20T12:36:07Z. These are not cumulative customer records. Their
  disappearance from the latest window is NOT evidence of disappearing demand.
- After tightening domain filtering against social media asset/CDN domains,
  the latest combined owner snapshots contain 21 distinct business-domain
  research records (20 seeds + 1 Scout candidate, after deduplication).
- Existing NYC permits: 36 event rows in the derived three-agency report,
  NOT 36 unique commercial buying companies or verified buildings.

Founder-targeted extraction using existing source records:
- An earlier Buyer Scout snapshot produced 6 roofing, 4 HVAC and 3
  general-contractor-related research records before social media asset
  host exclusion and the refreshed rotating Scout window were applied.
- Latest corrected run: Tampa roofing 2 sector-related research domains,
  Little Rock HVAC 2, NYC construction-data 0 public-domain matches in
  the current window. All city-level buyer validation remains 0.
- Marketplace/directory references are explicitly marked as NOT direct
  local roofing operators. Example: a Reddit image host was removed entirely.
  No public-business record is automatically classified as a purchaser.

Counts may change with owner snapshots. A domain with nationwide or unknown
geography is not a verified local roofing/HVAC/construction buyer.

The public research seed report explicitly states:
  fresh_search_result_status:
    NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED
  search_provider_health_independently_verified: false

Therefore NO NEW WEB/REDDIT/META REQUESTS were performed here, and the worker
does NOT pretend it has just crawled search results. Social sources cannot be
used to scrape members or send bulk unsolicited DMs.

## Actual data-mining vs revenue readiness

The output includes proposed source review identifiers and a sanitized
business-domain evidence list. It does NOT contain contact names, private social
information, bought call leads, billable appointments, approved data licences,
project material estimates, or settled revenue.

Gaps to produce real customer-facing results:
1. Source/Buyer Scout owners accept the existing signed pickup contract.
2. Source owner runs permitted, *fresh* bounded market-specific search using
   existing Search Fabric or licensed public registry sources, records original
   URL, query, fetched time, privacy/rights and provenance.
3. Buyer Scout owner independently confirms specific operator company identity,
   local territory, current demand for leads/data and buying capacity; check
   canonical duplicate/existing relationship and no-repeat rules.
4. Data Brokerage owner verifies commercial reuse/fulfilment rights.
5. Marketing/campaign owners develop consent-based acquisition, subject to
   channel and founder approvals.
6. Finance OS confirms contract economics and authenticated delivered leads or
   payment events; only then train predictive models on real outcomes.

## Read-only verification

cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.inspect_targeted_b2b_data_mining_20261020 \
  --market "tampa, fl"

This is an integration within the A2A research worktree only. It has not been
merged into the busy production checkout or used to edit the Buyer Scout owner
worker. The installed isolated research timer may run this code from its
existing worktree, subject to source freshness and validation. Do not mistake
the presence of mined evidence for actual marketing or sales execution.
