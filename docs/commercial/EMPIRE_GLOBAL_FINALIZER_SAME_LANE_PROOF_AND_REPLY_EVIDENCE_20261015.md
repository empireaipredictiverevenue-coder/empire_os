# EmpireOS Global Finalizer — Same-Lane Proof and Conversation Evidence

**Date:** 15 October 2026. No new server, service, timer, customer feed or outbound.

## Source of the failure

The old `scripts/finalize_runtime_control_bindings.py` refused to examine
Campaign, Agent Task and Opportunity evidence unless the unrelated
`conversations_replies` lane was 11/11 VERIFIED_RUNTIME.
This was an incorrect source-of-template dependency, not an
appropriate requirement for those three independently governed lanes.

## Changes

- Removed mandatory 11/11 Conversations & Replies template check.
- For each independent target, use only the EXISTING canonical control
  in the SAME lane, never a copied conversation record.
- Require original control name/lane and approved `UNVERIFIED`/
  `HOLD` status. Missing, ambiguous or mislabelled controls fail closed.
- Preserve original control confidence; do not invent 0.90/HIGH.
- Validate runtime observer proof with the existing promotion validator:
  correct lane, explicit OBSERVE, current timestamp and no
  consequential authority. Additional outcomes and quarantine source
  evidence must independently be current and OBSERVE-only.
- Keep canonical binding lock, compare-and-swap write, durability audit
  and exact remaining-control checks. A failed review cannot write.
- This release does NOT grant customer delivery, revenue recognition,
  payment, outbound or production authority.

## Remaining actual evidence gaps

The opportunity observer and final resolver artifacts were timestamped
2026-10-07, beyond the existing 7-day proof freshness window at the time
of this review. The quarantine evidence is currently
`INCOMPLETE_RUNTIME_EVALUATION`. They must NOT be relabelled fresh
merely because a finalizer happens to run on 15 October.

The current Conversations & Replies lane is 5/11 canonical
`VERIFIED_RUNTIME`. Unverified: canonical identity, conflict detection,
entity classification, evidence lineage, outcome linkage, output quality.
Its read-only linkage plan documents zero actual joined reply rows, no
verified provider originality, no authenticated sender/tenant identity
and no verified buyer intent. The current conversation collector reports
5 admitted candidate rows but zero canonical messages.
These are genuine limits, not a cue to fabricate inbound activity.

## Test coverage

Disposable source/canonical fixture includes a target-lane promotion
while the entire conversation lane remains unverified; no external
requests or production binding writes. Negative cases cover old
opportunity proof, missing same-lane control, wrong lane identity,
consequential outbound flag, missing outcome/quarantine proof.
Failure cases retain byte-identical original canonical bindings.

## Next integration step

Refresh opportunity evidence only from genuinely current source inputs
under its existing source owner, not by altering generated timestamps.
Expose the independent Conversations & Replies provenance/identity
blockers through the existing Founder Ops status.
Do not bypass gates to make the department-cycle service green.
