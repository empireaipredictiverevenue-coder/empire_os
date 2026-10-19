# EmpireOS — close source-mining ASTRA specialist adapter gap

19 October 2026 | Branch: feature/predictive-decision-control-20261018

## Production truth uncovered

A read-only inspection of the existing ASTRA `DepartmentWorkQueue`
found SIX earlier founder-directed source-mining assignments in
`runtime/departments/work/blocked`. All had
`error=specialist_adapter_required`, not completed source research.
The earlier enqueue operations succeeded, but workers could not execute
the requested specialist target components.

Six blocked jobs:
- Four existing canonical stream mining reviews: market intelligence x2,
  business development x1, data/Quant x1.
- Two official-source readiness sweeps: business development x1, market
  intelligence x1.

On 19 October, the source fingerprints for all four mining reviews had
changed, because canonical source snapshots continued to evolve.
Acquisition signals grew from 64 to 110 records; existing Opportunity
Factory candidates grew from 8 to 11. Quant still showed 0/11 complete
economic decision packets. Treat counts as source observations and candidate
records; none proves customers, signed terms, paid orders or profit.

The two official-source metadata task contracts still matched the feature
branch catalogue in a read-only re-evaluation, but those tasks remain
blocked in **production** until the owning service adopts the new code.

## What has been built

- `empire_os/source_mining_specialist_adapter.py`: deterministic, typed
  specialist adapter for the TWO existing target components:
  `existing_source_intelligence_and_opportunity_factory` and
  `existing_source_intelligence_and_sensor_mesh`.
- The existing `department_worker.py` now selects that adapter before
  its generic `specialist_adapter_required` fallback, after normal zero
  external-spend budget reservation.
- Strictly checks tenant/authority boundaries, exact specialist
  ownership/action, current canonical source fingerprint, work-item
  budget, official-source documentation references and pending
  first-party evidence. Malformed, stale or changed requests are BLOCKED.
- An admitted task produces a bounded **internal desk triage result**, with
  official source readiness or current stream counts, known scientific
  validation controls, evidence provenance and the next independent
  field-research requirement.
- A completed *desk triage* is explicitly NOT a completed independent
  scientific experiment, commercial decision, prospect qualification,
  model prediction, deal, email or revenue receipt.
- Existing queue's native immutable work ID, lease and DONE/BLOCKED state
  are retained. No second worker, data bus, CRM, database or schedule.
- Ling 3.1 and OpenManus are not invoked by this adapter; the former is
  still listed as free but unavailable through live Zen inference. Its
  model router status remains disabled. The scientific validation rubric
  runs as pure deterministic source evidence checks, not an LLM guess.

## Verified in isolated integration tests

- End-to-end four source-mining jobs: 4 true internal desk triages, 0
  fabricated buyer/outcome claims, no private contact disclosure.
- End-to-end two official-source catalogue reviews using existing
  worker and queue.
- A forged source fingerprint is blocked, not falsely completed.
- An updated source signal after queueing keeps the original task BLOCKED
  as audit history. A fresh source fingerprint queues a new deterministic
  assignment, which can complete only against the new source evidence;
  replay creates no duplicate.
- Stale and tenant-scoped/unauthorized actions rejected.
- Wider affected regression: 175 Python tests passed, plus ordinary
  non-fatal anyio deprecation warning.

## Deployment / source owner handoff

This is **feature-branch only**, with NO production worker restart or
permission change. The first production step after coordinated review is
not to auto-unblock all six old tasks: four have stale source fingerprints.

Owner release sequencing:
1. Merge the additive specialist adapter and tests into canonical
   `/srv/empire_os` under the owning department-worker maintainer.
2. Verify worker service route and rollback, with no changed external
   authority or additional spend.
3. Preserve four original stale blocked receipts; re-run existing
   `build_revenue_stream_mining()` and idempotent
   `enqueue_existing_department_mining()` to create new work tied to
   current source snapshots.
4. Reissue (or explicitly reopen) the two official-source readiness
   jobs only once the matching specialist adapter is deployed.
5. Run a bounded existing worker cycle and check DONE result objects,
   receipts, no model API call and zero outbound/finance.
6. Send remaining independent market/terms/source research to the
   appropriate existing teams. Do not claim a paying buyer without
   first-party buyer terms or verified opportunity economics.

## Scientific / commercial next priority

We have enough source counts to see the current bottleneck: 11 canonical
Opportunity Factory candidates, zero complete Quant economics packets,
and no confirmed buyer demand inferred from this source sweep. The next
high-value step is closing actual commercial-term and source-economics
gaps for ONE real target buyer/offer, not adding a fourth general-purpose
model or restarting the data platform.

Control separation: public-source observations -> verified canonical
source evidence -> buyer and economics facts -> original pre-outcome
prediction -> independently verified terminal payment and fulfilment ->
Economic Memory and prequential calibration.
