# B2B Data Fabric V1 — Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Public benchmark reverse-engineered

BlitzAPI exposes a thin typed client over server-side B2B indexes and transforms:
- people/company search;
- employee finder and decision-maker waterfall;
- person/email/phone enrichment and reverse identity;
- domain <-> company-profile identity transforms;
- job search and company-job views;
- TAM by jobs and TAM by people;
- cursor/page pagination, per-endpoint rate limits and usage metering.

Empire will reproduce the useful capability shape from public interfaces only.
It will not copy proprietary datasets, private implementation, credentials or
undocumented internals.

## Diagram

```text
Empire Search Fabric / Registries / First Party / Commercial Providers
        -> Provider Capability Registry
        -> Bounded Query Router
        -> Evidence Normalization
        -> Identity + Contact Resolution
        -> Signal Fusion / TAM / Trigger Intelligence
        -> Opportunity Value / Predictive Revenue
        -> Buyer Capacity / Revenue Distribution
        -> Verified Outcome -> Supply Quality Twin / Economic Memory
```

## Canonical placement

Owner: Predictive Revenue / Lead Intelligence.
This is a routing/planning layer, not a data store.
EmpireDB remains canonical business truth.
Search Fabric remains the web-search owner.
Identity Resolver remains entity identity owner.
Contact Resolution remains contact-evidence owner.
Supply Quality Twin remains source/outcome quality owner.

## Differentiation

Empire adds capabilities not implied by the public Blitz SDK:
- multiple interchangeable providers instead of one vendor;
- source provenance and semantic truth class on every observation;
- freshness/TTL and contradiction handling;
- first-party/registry evidence preference where appropriate;
- bounded cost/record budgets across an entire waterfall;
- source-quality feedback from verified downstream outcomes;
- Predictive Revenue and buyer-demand inversion after enrichment.

Raw provider confidence never becomes Empire truth by itself.

## Provider capability contract

Each provider/capability observation declares:
- provider key and capability;
- source class;
- availability;
- maximum semantic class it can establish;
- person-bound and live-verification support;
- per-request, per-run and per-second limits;
- metering model and explicit record-cost units when metered;
- observed_at / expires_at;
- evidence refs.

Unknown limits or unknown metering fail closed for autonomous paid routing.

## Query contract

Each request declares:
- capability;
- desired max items;
- hard total-record budget;
- whether VERIFIED evidence is required;
- whether person-bound evidence is required;
- whether commercial providers are allowed.

The planner never executes a provider. It produces ordered conditional stages.
The sum of stage caps may not exceed the run budget.

## Routing principles

1. Reject stale/unavailable/unsupported provider capabilities.
2. Enforce semantic and person-binding requirements before confidence/cost.
3. Prefer owned, first-party and authoritative public sources when sufficient.
4. Use commercial providers as bounded coverage accelerators, never truth owners.
5. Stop the waterfall once sufficient usable evidence is obtained.
6. Preserve unknown rather than inventing a fallback value.

## Authority

Allowed:
- OBSERVE;
- deterministic query planning;
- internal recommendation artifacts.

Forbidden:
- live provider calls in the core planner;
- canonical prospect/person fabrication;
- direct identity mutation;
- live outreach or buyer approval;
- allocation, terms, payments, settlement or revenue recognition;
- authority expansion.

## Worker assignment

Initial implementation:
- empire_os/b2b_data_fabric.py
- tests/test_b2b_data_fabric.py

The dirty empire_os/signal_resolver.py remains out of scope.

## Verification

Required:
- stale provider rejection;
- unknown metering fail-closed;
- total record-budget enforcement;
- VERIFIED/person-bound requirement enforcement;
- deterministic provider ordering;
- commercial-provider opt-out;
- no external execution authority;
- adjacent Search Fabric / evidence-planner / Supply Quality regressions.

## Promotion

No API key, migration, service restart or outbound action is required for V1.
A later adapter may integrate Blitz or another provider only behind this contract
and only after a bounded live evaluation against Empire-owned benchmark records.


## Getlead benchmark shape

Public Getlead materials describe:
- a large cached B2B contact database;
- CSV / name+company / domain / LinkedIn identifier intake;
- sequential enrichment waterfall;
- email-pattern inference;
- live company/public-web crawl;
- SMTP verification before usable output;
- source scrapers plus cold-email sending, warm-up, CRM/reply handling and MCP;
- server-side read/write controls and sending ceilings.

Empire adopts the architectural lessons, not Getlead's proprietary data or code.

## Blitz benchmark shape

Public Blitz SDK/docs expose:
- people and company search;
- employee finder and ICP waterfall;
- work-email and phone enrichment;
- reverse email/phone -> person identity;
- domain <-> LinkedIn/company identity transforms;
- jobs search and company jobs;
- TAM by jobs / people;
- per-endpoint rate limiting, retries, response validation, usage metering;
- hard client-side max_items caps to prevent unbounded record spend.

## Empire enhancement target

The combined Empire capability MUST exceed either benchmark by adding:
1. provider-neutral routing instead of vendor lock-in;
2. evidence provenance on every observation;
3. freshness / TTL on every observation;
4. semantic truth classes: INFERRED / OBSERVED / VERIFIED;
5. conflict retention instead of silent overwrite;
6. adaptive provider ordering from verified source quality and cost;
7. bounded per-request, per-run and per-provider spend/record ceilings;
8. signal fusion from jobs, registries, permits, websites and public/authorized social evidence;
9. buyer-demand inversion: discover/enrich inventory because a buyer/product needs it;
10. downstream Expected Revenue Value / Predictive Revenue instead of reply-rate-only optimization;
11. closed-loop learning from reply, qualified conversation, commercial terms, payment and fulfilment outcomes;
12. OBSERVE / PROPOSE / ACT separation with founder gates for consequential actions.

## Canonical waterfall target

Fresh EmpireDB evidence
-> first-party company evidence
-> authoritative registries
-> owned Search / Signal Fabric
-> licensed/commercial search providers
-> pattern inference (INFERRED only)
-> public-web corroboration
-> contact resolution
-> mailbox/phone verification
-> conflict + freshness gate
-> ICP / trigger / intent fusion
-> Predictive Revenue / buyer-product match.

No single provider is allowed to become canonical truth merely because it returned a value.
