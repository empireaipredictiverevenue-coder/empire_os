# Buyer Demand Graph Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Buyer evidence + Product evidence + Market evidence + Capacity evidence + Demand signals
-> Demand Lane Graph
-> read-only demand topology
-> Demand-First Crawling input (separate next architecture)

## Why a Demand Lane node

Commercial demand is buyer + product + market + evidence + capacity context.
The graph uses a LANE node as the explicit product/market corridor.

## Node types
- BUYER
- PRODUCT
- MARKET
- LANE
- SIGNAL

Every node requires evidence refs.

## Edge relations
- PRODUCT_DEFINES_LANE
- MARKET_DEFINES_LANE
- BUYER_DEMANDS_LANE
- BUYER_HAS_CAPACITY_FOR_LANE
- SIGNAL_SUPPORTS_LANE

Every edge requires source/target nodes, relation, observed timestamp and evidence refs.
BUYER_HAS_CAPACITY_FOR_LANE additionally requires explicit nonnegative capacity_remaining.
BUYER_DEMANDS_LANE may carry demand_units; absent quantity stays unknown and is not zero.

## No inferred topology
The builder never creates edges from co-occurrence, scores, generic signals or defaults.
It never schedules crawling.

## Positive example
A buyer has explicit evidence that it buys Permit Intelligence in Austin and has capacity 10.
Product and market define lane permit_intelligence:austin; observed demand and capacity edges connect the buyer to that lane.

## Negative examples
- A roofing permit signal in Austin does not automatically create a buyer edge.
- A buyer with no capacity evidence does not get a capacity edge.
- A missing demand quantity remains unknown.
- Conflicting duplicate IDs fail closed.
- Graph presence grants no outreach or crawler authority.

## Verification
- deterministic replay;
- relation source/target type validation;
- explicit capacity required;
- missing demand quantity preserved;
- duplicate/conflicting IDs fail closed;
- API preview OBSERVE-only;
- existing Demand Genesis/registry/outcome tests remain green.

## Authority
Read-only projection. No crawler scheduling, outbound, ad spend, provider activation, allocation, payment, revenue recognition, migration or authority expansion.

## 2026-10-01 implementation and verification

Implemented:
- deterministic BUYER / PRODUCT / MARKET / LANE / SIGNAL read model;
- evidence-required node and edge contracts;
- explicit buyer demand and capacity lane edges;
- Demand API OBSERVE preview;
- no inferred topology or crawler authority.

Verification:
- graph + Demand Genesis/Registry/Outcome + capacity readiness + Demand API: 33 passed;
- deterministic API preview returned HTTP 200;
- explicit capacity_remaining=0 remained known zero;
- missing demand_units remained unknown;
- inferred_edge_count=0;
- crawler_scheduling_enabled=false;
- execution_authority=none.

Status:
ENGINEERING COMPLETE / DETERMINISTIC API PREVIEW VERIFIED /
LIVE CANONICAL GRAPH DEPTH DEPENDS ON REAL DEMAND/CAPACITY EVIDENCE.
