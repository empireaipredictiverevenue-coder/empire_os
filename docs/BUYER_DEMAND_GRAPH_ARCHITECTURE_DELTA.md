# Buyer Demand Graph Architecture Delta

Date: 2026-10-01
Status: CONTRACT LOCKED / IMPLEMENTATION PENDING

## Diagram

Demand plan / readiness / outcome evidence
+ buyer identity / product / market evidence
+ verified buyer-capacity evidence
-> Buyer Demand Graph read model
-> Founder / Predictive Cloud context

No graph edge creates buyer intent, capacity, price, terms or execution authority.

## Owner

New read-model owner:
- empire_os/buyer_demand_graph.py

Existing truth owners remain:
- demand_genesis.py / demand_registry.py / demand_outcome.py;
- buyer capacity/readiness;
- product catalog;
- market identity.

## Graph contract

Node types:
- demand_plan;
- buyer;
- product;
- market.

Permitted edges:
- demand_plan -> product: TARGETS_PRODUCT;
- demand_plan -> market: TARGETS_MARKET;
- buyer -> product: BUYS_PRODUCT only with explicit buyer-demand evidence;
- buyer -> market: OPERATES_IN_MARKET only with explicit market evidence;
- buyer -> product+market capacity projection represented by a verified
  BUYER_CAPACITY edge carrying remaining capacity and its evidence ref.

Unknown identities or missing edge evidence create no edge.

Capacity=0 is a known value when explicitly evidenced.
Missing capacity is UNKNOWN, never zero.

## Output

Deterministic deduplicated nodes/edges, blockers, evidence refs, mode=OBSERVE,
execution_authority=none.

No generic graph score is introduced.

## Verification

- duplicate evidence dedupes;
- mismatched identities fail closed;
- missing capacity remains unknown;
- explicit zero capacity is preserved;
- plan evidence never becomes buyer intent;
- no write/send/payment/allocation authority.
