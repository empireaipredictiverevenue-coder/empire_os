# Marketplace / Auction Readiness v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Sales / Revenue Intelligence

## Purpose
Create one read-only readiness packet that composes the existing canonical Revenue
Exchange allocation-readiness contract with the existing Opportunity Auction
preview contract. This is not a second marketplace, auction engine, allocation
engine, pricing engine or settlement path.

## Inputs
The caller MUST provide auction identity/economics explicitly:
- `opportunity_id`
- `currency`
- `reserve_floor_cents`
- `reserve_evidence_ref`
- auction bids

Market supply/demand evidence comes separately from:
- `ExchangeSnapshot`
- `ExchangeReconciliation`
- `assess_exchange_allocation_readiness(...)`

Never derive:
- opportunity identity from `snapshot.niche`;
- currency from `snapshot.metro`;
- reserve/floor from inventory counts;
- reserve evidence from price values;
- expected value from bid amount.

## Composition
1. Validate/preview auction using `preview_opportunity_auction(...)`.
2. Assess exchange allocation readiness using
   `assess_exchange_allocation_readiness(...)`.
3. Produce one deterministic read-only packet with:
   - market niche / metro;
   - qualified inventory count;
   - active buyer capacity;
   - verified price evidence;
   - auction status and recommended bid;
   - allocation review readiness;
   - combined blockers;
   - evidence refs;
   - freshness timestamp;
   - all consequential authority fields fixed to `none` / false.

## Truth boundaries
- Bid amount is not expected value.
- Auction recommendation is not allocation.
- Allocation readiness is not allocation authority.
- Price evidence is not pricing authority.
- A proposal is not commercial terms.
- No payment/settlement/revenue recognition authority.
- UNKNOWN remains UNKNOWN; required auction identity/economic fields fail closed.

## Authority
`mode=OBSERVE`
`execution_authority=none`
`allocation_authority=none`
`pricing_authority=none`
`settlement_authority=none`
`binding_terms_authority=none`
`payment_action=false`
`revenue_recognition=false`

## Files
- `empire_os/marketplace_auction_readiness.py`
- `tests/test_marketplace_auction_readiness.py`

## Verification
Focused tests plus regressions:
- `tests/test_opportunity_auction.py`
- `tests/test_revenue_exchange.py`
- `tests/test_revenue_exchange_allocation_readiness.py`

## Completion
The slice is complete only when explicit auction inputs and canonical exchange
readiness compose successfully, blockers are deterministic, and no execution
or commercial authority is created.
