# Empire Opportunity Auction Architecture Delta

Date: 2026-10-01
Status: IMPLEMENTATION IN PROGRESS

## Diagram

Qualified opportunity / inventory
+ verified buyer-stated bids
+ reserve evidence
+ buyer capacity / territory / exclusivity evidence
-> Opportunity Auction preview
-> recommended highest verified bid + alternates
-> operator review
-> existing commercial terms / allocation / settlement boundaries

The auction never settles, allocates, accepts terms or moves funds.

## Canonical owner

New recommendation owner:
- empire_os/opportunity_auction.py

Existing owners remain authoritative:
- Revenue Router: expected-value routing recommendations;
- Revenue Exchange proposal review: buyer/inventory eligibility;
- Buyer Allocation: allocation execution boundary;
- commercial terms/payment/settlement systems: binding economics.

## Bid contract

Each active bid contains:
- unique bid id;
- opportunity id;
- buyer id;
- buyer-stated bid amount and currency;
- bid evidence ref;
- buyer capacity remaining and evidence ref;
- territory eligibility and evidence ref;
- exclusivity clearance and evidence ref;
- observed timestamp;
- optional expiry.

The bid amount is buyer-stated commercial evidence. It is NOT Predictive Revenue
expected value and must never substitute for expected_value_cents.

## Auction contract

One preview requires:
- one opportunity id;
- one currency;
- explicit reserve floor;
- reserve evidence ref;
- one active bid per buyer.

Eligibility:
- bid verified;
- amount >= reserve;
- capacity > 0;
- territory eligible=true;
- exclusivity clear=true;
- not expired at as_of;
- required evidence refs present.

## Clearing preview

Rule: HIGHEST_VERIFIED_BID.

Tie-break:
1. highest bid amount;
2. earliest observed bid;
3. buyer id for deterministic replay.

Output:
- recommended bid;
- eligible alternates in ranked order;
- blocked bids and reasons;
- reserve floor;
- recommendation_only=true.

The recommended bid is not binding terms and is not an allocation.

## Positive example

Reserve is $100. Three verified eligible buyers bid $120, $150 and $140.
The preview recommends the $150 buyer and retains the $140/$120 buyers as
alternates.

## Negative examples

- A $200 bid with no capacity evidence is blocked.
- A $180 expired bid is blocked.
- Two active bids from the same buyer are blocked pending reconciliation.
- A $150 bid does not become $150 expected value in Predictive Revenue.
- Winning the preview does not create a payment request or allocation.

## Verification

- reserve gate;
- evidence gate;
- capacity / territory / exclusivity gates;
- expiry gate;
- duplicate buyer bids fail closed;
- deterministic tie handling;
- no EV substitution;
- no allocation/terms/payment/settlement/revenue authority.

## Authority

Recommendation-only OBSERVE preview. No allocation execution, binding terms,
pricing mutation, payment request, settlement, fulfilment, revenue recognition,
migration, deployment or authority expansion.
