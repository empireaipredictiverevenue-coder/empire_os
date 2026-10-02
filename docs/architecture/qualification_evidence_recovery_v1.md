# Qualification Evidence Recovery v1 — Architecture Contract

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Qualification / Data Intelligence

## Purpose
Wire the existing `evidence_enrichment_planner` into the canonical Lead Scoring v2
qualification cycle so previously-scored low-confidence prospects can recover when
new real evidence becomes available.

The current defect is structural: `fetch_pending_prospects()` excludes any prospect
that already has a v2 qualification, so a row below `MIN_DECISION_CONFIDENCE=0.50`
can remain stale forever even when bounded enrichment is available later.

## Canonical loop

existing v2 qualification below 0.50
  -> load canonical prospect
  -> build `plan_evidence_enrichment(...)`
  -> if no bounded available action can reach target: record HOLD/deferred state
  -> otherwise run existing `enrich_prospect_for_scoring(...)`
  -> optionally promote only verifier-accepted first-party website
  -> run existing identity resolution rules
  -> build existing v2 payload
  -> compare evidence fingerprint / confidence against previous state
  -> UPSERT only if evidence materially changed
  -> record recovery metadata in `result_payload`
  -> stop retrying unchanged evidence

## Non-goals
- no lower confidence threshold;
- no synthetic evidence;
- no new scorer;
- no new identity algorithm;
- no outbound;
- no buyer allocation;
- no price/payment/revenue action;
- no repeated unchanged enrichment loop.

## Candidate selection
Select existing canonical v2 qualification rows where:
- scoring_engine=`empire_os.lead_scoring`;
- scoring_version=`v2`;
- `evidence_confidence < MIN_DECISION_CONFIDENCE` OR status=`insufficient_evidence`;
- prospect still exists;
- recovery has not already been attempted against the same evidence fingerprint.

Candidate ordering:
1. highest current evidence confidence first;
2. newest scoring timestamp second;
3. deterministic prospect id tie-break.

This maximizes the chance of converting near-threshold real prospects first.

## Evidence fingerprint
A deterministic fingerprint is built only from fields that affect v2 evidence:
- canonical prospect identity fields used by scoring/completeness;
- acquisition source/url/evidence identity;
- current verified first-party website;
- enrichment evidence source/url/accepted facts;
- previous evidence confidence and observed/unknown dimensions.

The fingerprint itself is metadata, not commercial evidence.

## Anti-loop rule
After a recovery attempt, persist in qualification `result_payload`:
- recovery_attempted=true;
- recovery_attempted_at;
- recovery_input_fingerprint;
- recovery_previous_confidence;
- recovery_new_confidence;
- recovery_changed=true/false;
- selected evidence-plan actions;
- recovery_reason.

If the same fingerprint is seen again and the previous attempt produced no material
change, the row is skipped until its canonical inputs change.

## Identity rule
Recovery may use the existing `resolve_identity(...)` path only. Identity remains
fail-closed. A qualification `entity_id` does not substitute for an active
`prospect_entity_links` row when downstream allocation requires that link.

## Production integration
Add one bounded recovery stage to `scripts/run_qualification_cycle.py` after normal
new-prospect qualification and before Omega projection.

Booster bounds remain explicit. Suggested initial recovery limit: 10 per booster run.
Normal 15-minute qualification cycle may use a smaller limit.

## Files
- `empire_os/qualification_data_repository.py`
- `empire_os/qualification_worker_v2.py`
- `scripts/run_qualification_cycle.py`
- focused recovery tests

## Verification
- low-confidence existing v2 row is selected;
- high-confidence row is not selected;
- unchanged fingerprint is skipped;
- changed evidence may rescore/update;
- threshold remains 0.50;
- failed enrichment never increases confidence;
- no synthetic data;
- no outbound/allocation/payment/revenue authority;
- existing qualification/identity/Omega tests remain green;
- LIVE VERIFY shows bounded recovery attempts, not an endless loop.
