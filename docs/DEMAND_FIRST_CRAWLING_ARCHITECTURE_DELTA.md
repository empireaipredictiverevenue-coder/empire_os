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

## 2026-10-01 implementation and verification

Implemented:
- pure DemandRegistryRecord -> crawler request planner;
- explicit real-source allowlist matching the registered real crawler adapters;
- explicit niche/metro/country target;
- explicit source-capability and demand evidence;
- approval evidence required before dispatch_ready;
- guarded acquisition max_candidates bound 1..25;
- deterministic crawler CLI argument tokens only;
- no crawler import or invocation.

Verification:
- planner + Demand Genesis/Registry + crawler runner suite: 61 passed;
- source allowlist checked against live registered source names;
- biz_search remains excluded because it is registered as a stub;
- no deployed /v1/demand/* runtime surface was found on current internal ports;
- no readable dedicated demand-registry DSN is exposed to the ubuntu MCP worker;
- therefore no live canonical demand plan or crawl dispatch is claimed.

Status:
ENGINEERING COMPLETE / DETERMINISTIC PLANNER VERIFIED /
LIVE CANONICAL DEMAND-PLAN FEED NOT CURRENTLY AVAILABLE TO THIS RUNTIME SURFACE.
