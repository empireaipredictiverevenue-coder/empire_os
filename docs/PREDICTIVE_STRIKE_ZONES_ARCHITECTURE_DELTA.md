# Predictive Strike Zones Architecture Delta

Date: 2026-10-01
Status: CONTRACT LOCKED / IMPLEMENTATION PENDING

## Diagram

Observed market / opportunity evidence
+ explicit Predictive Revenue ERV evidence
+ commercial Opportunity Decay state
+ verified buyer capacity
-> Predictive Strike Zone projection
-> ranked recommendation-only markets/opportunities

No new probability model or generic score is introduced.

## Owner

New read-model owner:
- empire_os/predictive_strike_zones.py

Existing owners remain:
- market_sweep_revenue_gps.py for market evidence;
- predictive_revenue_formula.py for ERV;
- commercial_opportunity_decay.py for temporal/commercial decay;
- buyer capacity systems for verified capacity.

Legacy root storm_strike.py is not a canonical owner.

## Candidate contract

Required for a ranked STRIKE_CANDIDATE:
- stable opportunity/market identity;
- explicit positive expected_revenue_value_cents with evidence ref;
- decay state not EXPIRED/STALE/UNKNOWN;
- verified buyer capacity > 0 with evidence ref;
- market/opportunity evidence refs.

Otherwise emit BLOCKED or UNKNOWN with explicit blockers.

Ranking uses explicit expected revenue value only.
No inferred buyer intent, market share, close probability or revenue.

## Authority

Recommendation only:
- execution_authority=none;
- crawler_execution=false;
- outbound=false;
- ad_spend=false;
- allocation=false;
- revenue_recognition=false.

## Verification

- missing EV remains UNKNOWN;
- price never substitutes for EV;
- zero capacity blocks;
- stale/expired decay blocks;
- deterministic EV ranking;
- duplicate identity fails closed;
- no execution authority.

## 2026-10-01 implementation and verification

Implemented:
- pure OBSERVE strike-zone projection;
- explicit positive expected_revenue_value_cents + evidence required;
- ACTIVE decay required;
- explicit positive buyer_capacity_remaining + evidence required;
- ranking by explicit EV only;
- price/scores/probabilities cannot substitute for EV;
- zero execution, crawler, outbound, spend, allocation or revenue authority.

Verification:
- Strike Zones + Market Sweep + Predictive Revenue + Opportunity Decay: 76 passed;
- production Radar projection used 22 current real candidates;
- strike_candidates=0;
- all 22 remained UNKNOWN because explicit ERV, decay and remaining-capacity
  evidence is currently absent;
- no fake ranking or inferred economics were produced;
- execution_authority=none; outbound=false; allocation=false;
  revenue_recognition=false.

Status:
ENGINEERING COMPLETE / LIVE READ-ONLY PROJECTION VERIFIED /
CURRENT CANONICAL STRIKE EVIDENCE DEPTH INSUFFICIENT FOR A RANKED CANDIDATE.
