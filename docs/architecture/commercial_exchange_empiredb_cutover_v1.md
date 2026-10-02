# Commercial Exchange EmpireDB Cutover v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Commercial Exchange / Data Cloud

## Purpose
Replace the remaining Supabase REST read transport in
`scripts/refresh_commercial_exchange.py` with the canonical
`CanonicalDataGateway` configured for EmpireDB.

The existing projection logic in `empire_os/commercial_exchange_inventory.py`
remains authoritative and unchanged.

## Diagram

EmpireDB
  -> CanonicalDataGateway (read only)
  -> prospects / prospect_qualifications / prospect_entity_links / buyers /
     fulfilment_orders
  -> existing build_exchange_snapshot(...)
  -> runtime/commercial_exchange/latest.json
  -> Buyer Acquisition / Revenue Exchange Observation Planner

## Non-goals
- no new database role;
- no schema change;
- no writes;
- no buyer allocation execution;
- no pricing mutation;
- no terms/payment/settlement authority;
- no change to qualification, identity or buyer activation rules;
- no fallback to Supabase.

## Canonical reads
Prospects:
- id
- business_name
- niche
- metro
- created_at
- status

Prospect qualifications:
- existing `BuyerAllocationDataRepository.QUALIFICATION_COLUMNS`
- `scoring_engine=empire_os.lead_scoring`
- version v2/v1 preference preserved.

Identity links:
- existing `BuyerAllocationDataRepository.IDENTITY_COLUMNS`
- active=true
- ambiguity remains fail-closed.

Buyers:
- existing `BuyerAllocationDataRepository.BUYER_COLUMNS`
- pagination unchanged.

Fulfilment orders:
- prospect_id
- state
- any non-rejected/non-cancelled order marks a prospect allocated.

## Output truth
The resulting runtime snapshot MUST declare:
- `source=canonical_empiredb_projection`;
- `execution_authority=none`;
- `automatic_external_delivery=false`;
- `actual_revenue=false`.

A successful EmpireDB cutover does not imply inventory, capacity or commercial
readiness. Empty/blocked inventory remains truthful.

Observed buyer `per_lead_rate` / `base_payout` remains only an observed rate in
Commercial Exchange and MUST NOT be promoted into verified Revenue Exchange price
without the separate verified-price evidence gate.

## Failure behavior
- Missing EmpireDB configuration fails closed.
- No legacy/Supabase fallback.
- Invalid query payloads fail closed.
- Existing runtime snapshot is not overwritten by a failed refresh.

## Files
- `scripts/refresh_commercial_exchange.py`
- focused tests for EmpireDB query transport
- existing Commercial Exchange inventory/systemd tests

## Verification
1. Focused unit tests for all five EmpireDB read surfaces.
2. Existing Commercial Exchange inventory regression tests.
3. Compile/diff check.
4. Independent verification from fresh worktree.
5. LIVE VERIFY under existing `empire-commercial-exchange.service`.
6. Confirm output source is `canonical_empiredb_projection`.
7. Confirm no write/execution authority.

## Completion
Cutover is complete only when the installed service produces the Commercial
Exchange snapshot from EmpireDB and no Supabase REST reader remains in the active
refresh path.
