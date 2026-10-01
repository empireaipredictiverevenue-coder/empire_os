# Demand-First Crawling Architecture Delta

Date: 2026-10-01
Status: CONTRACT LOCKED / IMPLEMENTATION PENDING

## Diagram

Review-ready demand plan
+ explicit source capability evidence
+ explicit market/niche target
+ optional operator approval evidence
-> Demand-First Crawl Planner
-> bounded crawler-run request
-> existing crawler_runner execution boundary

The planner never executes the crawler.

## Owner

New planning owner:
- empire_os/demand_first_crawl_planner.py

Execution owner remains:
- empire_os/crawler_runner.py

## Contract

A crawl proposal requires:
- plan_id;
- source;
- niche and/or metro/country target;
- max_candidates >= 1;
- demand evidence refs;
- source capability evidence refs.

Without approval evidence:
- state=REVIEW_REQUIRED;
- dispatch_ready=false.

With explicit approval evidence:
- state=READY_FOR_CRAWLER_DISPATCH;
- emit deterministic crawler CLI arguments;
- execution_authority remains none.

The planner may not infer a source, geography or demand claim.

## Safety

No outbound, paid acquisition, provider activation, commercial terms, payment or
revenue authority.

Crawler canonical-ingest behavior remains unchanged and fail-closed.

## Verification

- no approval -> no dispatch readiness;
- explicit approval -> deterministic safe CLI args;
- invalid/unknown source blocks;
- missing target/evidence blocks;
- max-candidate bound preserved;
- planner never invokes crawler_runner.
