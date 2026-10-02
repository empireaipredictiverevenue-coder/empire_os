# Commercial Exchange Verified Market Price Projection v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Commercial Exchange / Commercial Evidence

## Purpose
Extend the existing EmpireDB-backed Commercial Exchange read model with verified
market-level `per_lead` price evidence from `public.commercial_evidence_registry`.

No new service or truth store is created. The existing
`empire-commercial-exchange.service` remains the bounded read-model materializer.

## Diagram

```text
commercial_evidence_registry
  WHERE evidence_kind='price'
    AND status='verified'
    AND unit='per_lead'
    AND currency='USD'
        |
        v
Commercial Exchange refresh
        |
        +--> validate niche + metro
        +--> validate verified_at
        +--> reject expired evidence
        +--> preserve evidence id/source reference
        |
        v
runtime/commercial_exchange/latest.json
  .verified_market_prices[]
        |
        v
Revenue Exchange Observation Planner
```

## Eligible evidence
A row is eligible only when:
- `evidence_kind == price`;
- `status == verified`;
- `unit == per_lead`;
- `currency == USD`;
- `amount_cents > 0`;
- niche is non-empty;
- metro is non-empty;
- `verified_at` is present;
- `valid_until` is null or later than snapshot time;
- source type is one already allowed by the canonical registry schema.

## Explicit non-sources
The following MUST NOT become verified Revenue Exchange price:
- `buyer_seats[].observed_rate`;
- buyer `per_lead_rate` or `base_payout` by themselves;
- monthly/report/audit/flat catalog prices;
- forecast/JEV expected values;
- auction bids;
- unverified/pending commercial evidence;
- expired evidence.

## Output fields
Commercial Exchange snapshot adds:
- `verified_market_prices`;
- `verified_market_price_count`;
- `verified_market_price_market_count`;
- `commercial_price_source=canonical_empiredb_commercial_evidence_registry`.

Each price row contains only:
- evidence_id;
- niche;
- metro;
- amount_cents;
- currency;
- unit;
- source_type;
- source_reference;
- observed_at;
- valid_until;
- verified_at;
- evidence_ref=`commercial_evidence:<id>`.

## Revenue Exchange integration
The Observation Planner may convert these rows into `MarketPriceEvidence` only.
It must continue deriving inventory/capacity from the separate Commercial Exchange
supply/seat projections.

A market proposal is ready only if inventory evidence, active-capacity evidence and
at least one verified market price all exist for the same normalized market.

Zero active capacity is a valid observed capacity value; it does not imply allocation
readiness.

## Authority
Always read-only:
- no commercial evidence verification;
- no terms approval;
- no price mutation;
- no allocation execution;
- no outbound;
- no payment/settlement;
- no revenue recognition.

## Files
- `scripts/refresh_commercial_exchange.py`
- `empire_os/revenue_exchange_observation_planner.py`
- focused tests

## Completion
Complete only when:
1. pending/unverified/expired/non-per-lead evidence is excluded;
2. verified evidence retains market and source lineage;
3. observed buyer rates remain excluded;
4. Revenue Exchange planner consumes only `verified_market_prices`;
5. independent verification passes;
6. scheduled LIVE VERIFY reports the true verified-price count.
