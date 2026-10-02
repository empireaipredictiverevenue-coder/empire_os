# Commercial Exchange Supply Selection v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Commercial Exchange / Qualification

## Problem
The EmpireDB cutover correctly replaced Supabase transport, but the refresh still
selected the newest N prospects first and only then inspected qualification state.
This can produce a false operational picture: a new weak cohort may be 100% below
the evidence floor while older canonical v2 prospects are already HOT/WARM,
identity-resolved and Omega-ready.

Commercial Exchange inventory must represent **qualified canonical supply**, not an
arbitrary recent-prospect sample.

## New read sequence

```text
EmpireDB prospect_qualifications
  WHERE scoring_engine='empire_os.lead_scoring'
    AND scoring_version='v2'
    AND status='scored'
    AND tier IN ('hot','warm')
    AND evidence_confidence >= MIN_DECISION_CONFIDENCE
  ORDER BY scored_at DESC, prospect_id ASC
  LIMIT N
      |
      v
fetch exact prospects by prospect_id
      |
      +--> fetch active prospect_entity_links
      +--> fetch active fulfilment-order allocation state
      +--> existing buyers projection
      |
      v
existing build_exchange_snapshot(...)
```

## Invariants
- `MIN_DECISION_CONFIDENCE` remains 0.50.
- No weak/insufficient qualification is promoted into exchange inventory.
- Active identity link is still required by existing `qualification_identity_decision`.
- Market/niche evidence rules remain unchanged.
- Buyer activation/capacity rules remain unchanged.
- No allocation is executed.
- No observed buyer rate becomes binding price.
- No outbound/payment/revenue authority changes.
- No Supabase fallback.

## Diagnostics
The runtime snapshot should expose:
- `selection_scope=qualified_v2_supply`;
- `qualified_supply_rows_scanned`;
- `prospects_scanned`;
- `identity_links_available`;
- existing supply gate diagnostics.

Low-confidence recovery remains owned by Qualification v2 and is not duplicated here.

## Completion
Complete only when:
1. tests prove the cohort is qualification-driven rather than recency-driven;
2. existing inventory/allocation regressions pass;
3. independent worktree verification passes;
4. scheduled LIVE VERIFY shows qualified/identity-ready supply if such evidence exists;
5. no authority or threshold is widened.
