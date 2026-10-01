# Revenue Router Convergence Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Qualified inventory
-> allocation proposal review
-> verified routing candidate
-> Revenue Exchange optimization preview
-> operator review
-> existing atomic allocation execution boundary

The router is recommendation-only. Atomic allocation remains the execution owner.

## Canonical owners

Evidence / proposal owner:
- empire_os/revenue_exchange_allocation_proposal.py

Recommendation / optimization owner:
- empire_os/revenue_exchange_optimization_bridge.py

Execution owner remains:
- empire_os/buyer_allocation.py
- canonical atomic allocation RPC

## Defects being corrected

### Capacity evidence loss

The proposal review validates buyer_capacity_remaining but does not carry that
value in ExchangeAllocationProposalReview. Downstream optimization therefore
cannot consume the verified capacity from the review object.

Fix:
- preserve buyer_capacity_remaining in the review result;
- preserve its evidence reference;
- no new allocation authority.

### Price != expected value

The optimization bridge currently substitutes proposed_price_cents when
expected_value_cents is missing.

That is not economically valid:
- price is not expected contribution;
- price ignores acquisition, fulfilment, risk and probability;
- proposed price cannot silently become ERV.

Fix:
- expected_value_cents must be explicit;
- proposed price remains available as commercial-price evidence only;
- missing expected value blocks optimization and stays UNKNOWN.

### Conflicting capacity

Multiple proposals for the same buyer may carry different capacity values. The
current bridge takes max(capacity), which can manufacture capacity.

Fix:
- identical capacity observations may be reused;
- conflicting capacity values block that buyer from optimization;
- no max/min reconciliation by assumption.

## Output boundary

A Revenue Router candidate may include:
- inventory id;
- buyer id;
- verified buyer capacity remaining;
- proposed price;
- explicit expected value;
- evidence refs;
- eligibility blockers.

Recommendation output:
- recommendation_only=true;
- allocation_execution=false;
- pricing_mutation=false;
- terms_acceptance=false;
- payment_action=false;
- revenue_recognition=false;
- execution_authority=none.

## Positive example

Two inventory items are eligible for the same buyer. Both proposals carry the
same verified remaining capacity=1 and explicit expected values. Optimization
may recommend at most one item for that buyer.

## Negative examples

- Proposal has $120 price but no expected value -> blocked, not treated as $120 EV.
- Same buyer appears with capacity 1 and capacity 3 -> all options for that buyer
  are blocked until capacity is reconciled.
- Higher proposed price cannot bypass missing economics or eligibility.

## Verification

- proposal review preserves capacity;
- bridge requires explicit expected value;
- conflicting buyer capacity fails closed;
- duplicate assignment remains blocked;
- multi-buyer optimization still respects capacity;
- buyer allocation execution tests remain unchanged;
- no execution authority introduced.

## Authority

No live allocation, outbound, pricing mutation, terms acceptance, payment,
settlement, fulfilment, revenue recognition, migration or authority expansion.

## 2026-10-01 verification

Implemented:
- proposal review now preserves verified buyer capacity and optional expected value;
- optimization requires explicit expected value and never substitutes price;
- conflicting capacity observations for one buyer fail closed;
- API preview exposes expected value evidence;
- execution remains outside the router.

Verification:
- focused proposal / optimizer / allocation suite: 34 passed;
- independent adjacent suite: 56 passed;
- compilation and diff check passed;
- deterministic OBSERVE preview returned AVAILABLE with buyer capacity=1 and explicit EV;
- that preview used bounded verification input and is not claimed as a live canonical route;
- allocation_execution=false;
- pricing_mutation=false;
- payment_action=false;
- revenue_recognition=false;
- execution_authority=none.

Production-truth check:
- the current runtime/commercial_exchange/latest.json snapshot contains no
  allocation-ready live inventory;
- current inventory remains blocked by missing evidence, so a live canonical
  Revenue Router recommendation is not presently available;
- this is a live-data blocker, not a reason to fabricate an expected value,
  capacity, buyer route or revenue outcome.

Status:
ENGINEERING COMPLETE / DETERMINISTIC OBSERVE PREVIEW VERIFIED /
LIVE CANONICAL ROUTING BLOCKED BY CURRENT EVIDENCE.
Live canonical allocation remains separately governed by the existing atomic
allocation boundary.
