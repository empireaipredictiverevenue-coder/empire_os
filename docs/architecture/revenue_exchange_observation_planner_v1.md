# Revenue Exchange Observation Planner v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Revenue Exchange / Sales Revenue

## Purpose
Build a deterministic dry-run planner for canonical Revenue Exchange observations.
The planner decides whether available production evidence is sufficient to propose
an append-only `record_revenue_exchange_observation` request.

It does not write EmpireDB and does not provision the ingest role.

## Required market evidence
A market observation is proposal-ready only when all three are independently
available for the same normalized `(niche, metro)` market:

1. **Qualified inventory**
   - EmpireDB-native source only;
   - explicit market key;
   - integer count >= 0;
   - evidence refs;
   - source must not be legacy recovery, Supabase projection, inferred, or synthetic.

2. **Verified buyer capacity**
   - EmpireDB-native source only;
   - capacity is market-specific, not a global aggregate;
   - verified commercial terms/capacity semantics preserved;
   - integer count >= 0;
   - evidence refs.

3. **Verified price-per-lead evidence**
   - unit must be exactly `per_lead`;
   - positive integer cents;
   - verified state;
   - same currency/market applicability;
   - evidence refs.

## Rejected evidence
The planner MUST reject:
- `canonical_supabase_projection` Commercial Exchange snapshots;
- legacy permit recovery rows with `canonical_inventory_claimed=false`;
- product catalog prices whose unit is monthly/report/map/audit/flat;
- configured buyer caps without `capacity_verified_at` semantics;
- aggregate buyer-capacity summaries as market-level capacity;
- inferred demand, JEV values, bid amounts, forecasts or policy scenarios as observed market truth.

## Current production expectation
On 2026-10-02 the planner is expected to produce no proposal-ready observations because:
- `runtime/commercial_exchange/latest.json` source is `canonical_supabase_projection`;
- `runtime/buyer_capacity_readiness/latest.json` is aggregate only and has `capacity_verified=0`;
- the ready commercial catalog currently has no `per_lead` verified price entries;
- legacy permit inventory is explicitly not canonical inventory.

This is a valid truthful result, not a failure.

## Output
`runtime/revenue_exchange/observation_plan_latest.json`

Fields:
- schema_version
- generated_at
- mode=OBSERVE
- proposal_ready_count
- market_candidate_count
- global_blockers
- rejected_sources
- candidates
- execution_authority=none
- database_write=false
- allocation_authority=none
- pricing_authority=none
- payment_action=false
- revenue_recognition=false

## Future activation
When all required evidence exists, a separate founder-gated slice may provision a
dedicated `empire_revenue_exchange_ingest_login` bound only to the existing
`empire_revenue_exchange_ingest` NOLOGIN capability and submit append-only
observations. This planner itself never performs that activation.

## Files
- `empire_os/revenue_exchange_observation_planner.py`
- `scripts/plan_revenue_exchange_observations.py`
- `tests/test_revenue_exchange_observation_planner.py`

## Completion
The planner is complete when it:
- refuses current noncanonical/insufficient production evidence;
- accepts only market-aligned EmpireDB-native inventory/capacity + verified per-lead price;
- produces deterministic proposal payloads without writing them;
- never invents price, capacity, inventory, demand or revenue.
