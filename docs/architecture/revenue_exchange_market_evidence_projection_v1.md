# Revenue Exchange Market Evidence Projection v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Revenue Exchange / Commercial Exchange

## Purpose
Project canonical market-level supply and active buyer capacity from the live
EmpireDB-backed Commercial Exchange snapshot into the existing dry-run Revenue
Exchange Observation Planner.

This is a read-model composition only. It does not write Revenue Exchange
observations and does not weaken the verified-price gate.

## Canonical source
`runtime/commercial_exchange/latest.json` is eligible only when:
- `source == canonical_empiredb_projection`;
- `candidate_selection == qualification_driven`;
- `execution_authority == none`;
- `actual_revenue == false`.

Any Supabase, legacy, inferred or synthetic projection is rejected.

## Supply aggregation
Only Commercial Exchange inventory rows that have already passed qualification
and identity gates count as qualified Revenue Exchange supply:
- `state == allocation_candidate`; or
- `state == overflow_no_capacity`.

Rows with:
- `blocked_missing_evidence`;
- `allocated`;
- missing niche/metro;
- missing/ambiguous identity
are not supply for a new exchange observation.

Aggregate by normalized `(niche_family, metro)`:
- `qualified_inventory_count = row count`;
- evidence refs include the Commercial Exchange snapshot identity plus contributing
  prospect ids / corridor keys as bounded lineage metadata.

## Active capacity aggregation
Use the same complete Commercial Exchange buyer-seat projection.

For each supply market:
- sum `remaining_capacity` only for seats with `seat_state == active_capacity` and
  matching `(niche_family, metro)`;
- blocked/inactive/test-held/not-commercially-activated seats contribute zero;
- absence of an active matching seat means observed active capacity is zero because
  the buyer-seat projection is complete for the refresh cohort.

This is active allocation capacity, not configured cap and not inferred demand.

## Price gate
Commercial Exchange `observed_rate` is explicitly **not** verified Revenue Exchange
price. It must never be copied into `verified_price_per_lead_cents`.

Until separate verified `per_lead` price evidence exists:
- market candidates may exist;
- `proposal_ready=false`;
- blocker=`verified_per_lead_price_missing`;
- no Revenue Exchange DB write occurs.

## Output expectation
The observation planner should move from:
- zero market candidates / no canonical inventory

to:
- one or more canonical market candidates;
- real qualified inventory counts;
- observed active buyer capacity (possibly zero);
- verified price still unavailable;
- `database_write=false`;
- `execution_authority=none`.

## Files
- `empire_os/revenue_exchange_observation_planner.py`
- `tests/test_revenue_exchange_observation_planner.py`

## Completion
Complete when:
1. tests prove only identity-ready supply is aggregated;
2. active capacity excludes blocked seats;
3. observed rates never become verified prices;
4. current live artifact produces real market candidates;
5. no write/authority occurs.
