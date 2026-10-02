# Commercial Exchange Supply Candidate Selection v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Commercial Exchange / Revenue Intelligence

## Problem
The EmpireDB Commercial Exchange refresh currently selects the newest raw prospects
first and only then checks qualification/identity. A recovered or mature qualified
prospect can therefore be absent from the bounded recency window even though it is
commercial supply-ready.

Observed on 2026-10-02:
- qualification recovery promoted a real prospect from 0.45 to 0.60 confidence;
- it became `hot` and identity-resolved;
- Commercial Exchange still reported all latest 200 prospects below confidence because
  the promoted prospect was outside the latest-prospect recency cohort.

## Correct candidate driver
Commercial Exchange supply projection must be qualification-driven, not raw-prospect
recency-driven.

Canonical candidate selection:
1. Query v2 qualifications with:
   - scoring_engine=`empire_os.lead_scoring`;
   - scoring_version=`v2`;
   - status=`scored`;
   - tier in (`hot`,`warm`);
   - evidence_confidence >= `MIN_DECISION_CONFIDENCE`.
2. Order by:
   - evidence_confidence descending;
   - scored_at descending;
   - prospect_id deterministic tie-break.
3. Bound to the configured Commercial Exchange limit.
4. Fetch those prospects by id.
5. Fetch active identity links for the same prospect ids.
6. Reuse existing `project_inventory()` / `build_exchange_snapshot()` gates unchanged.

## v1 compatibility
V1 qualifications may be considered only as a bounded fallback after v2 candidates,
using existing allocation semantics. A prospect with a v2 row must never fall back to
v1 merely because the v2 row is insufficient.

## Truth boundaries
- Qualification readiness selects candidates; it does not guarantee inventory readiness.
- Active identity link remains mandatory.
- Existing fulfilment allocation exclusion remains mandatory.
- Buyer capacity remains separate and can still be zero.
- Observed buyer rates remain non-binding price observations.
- No allocation, outbound, pricing, payment or revenue authority is added.

## Output diagnostics
Add explicit fields:
- `candidate_selection=qualification_driven`;
- `qualified_candidates_selected`;
- `qualified_v2_candidates_selected`;
- `qualified_v1_fallback_candidates_selected`.

## Files
- `scripts/refresh_commercial_exchange.py`
- `tests/test_refresh_commercial_exchange_empiredb.py`

## Completion
The slice is complete when a canonical qualified prospect outside the newest raw-prospect
window can appear in Commercial Exchange supply projection, while all existing identity,
allocation and authority gates remain unchanged.
