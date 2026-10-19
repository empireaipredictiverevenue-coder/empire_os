# EmpireOS — First-Party Buyer Evidence to Quant Brain Loop

19 October 2026 | Feature branch: feature/predictive-decision-control-20261018

## Goal

The next working edge of EmpireOS's scientific Predictive Revenue pathway is:
actual canonical public market research -> ONE exact Opportunity Factory
candidate -> independently verified first-party buyer/offer evidence ->
canonical economics packet -> prospective forecast -> future terminal
commercial outcome -> Economic Memory / prequential calibration.

This release implements the **first internal evidence-acquisition handoff**.
It does NOT claim the later steps are complete, or simulate buyer responses.

## Actual canonical data at this checkpoint

Four fresh read-only production source snapshots join by exact
opportunity_key and prove 11 existing market-research candidate records;
the corresponding 11 Quant Brain packets are UNAVAILABLE because all
11 have 11 absent quantitative inputs. The first ranked source candidate
in the current evidence pathways is roofing. The leading missing factor
is genuine buyer-intent observation, NOT public search/permit counts.
No verified buyer purchase, order, payment or recognised gross profit can
be inferred from these 11 sources.

## Code changes

- `empire_os/revenue_buyer_evidence_handoff.py` creates one deterministic
  first-party buyer-evidence research request from
  `review_evidence_pathways_runtime` (which joins existing Radar,
  Opportunity Factory, routed blockers and Quant).
- Strict OBSERVE, source schema, fresh timestamp, exact authority,
  tenant-global-only and cross-stage identity checks are inherited from
  the pathway review. The task's stable SHA-256 fingerprint covers the
  selected opaque opportunity reference, exact first missing factor,
  Quant missing factors, blocker groups and contradictions. It never
  exports raw buyer/lead identity or email.
- Eleven Quant Brain required factors use a typed evidence-custody map.
  Examples: conditional revenue requires written buyer-specific terms;
  costs require independent expense/fulfilment records; success
  probability requires time-safe verified terminal outcome history;
  uncertainty/confidence require empirically validated statistics,
  NOT an agent's arbitrary guess.
- Only one opportunity is prepared. An optional **explicit**
  operator flag enqueues one internal £0 zero-model-token
  `business_development` review into the existing ASTRA
  `DepartmentWorkQueue`, with native deterministic job IDs and replay
  deduplication. Default is READ-ONLY.
- `empire_os/department_worker.py` now implements the exact specialist
  target directly (avoids another `specialist_adapter_required`).
  It rechecks the current source and task contracts. A stale or
  altered snapshot is BLOCKED rather than treated as completed research.
- A worker DONE receipt means **desk-triage of a research requirement**;
  it does not attest anyone checked the buyer's mailbox, spoke with a
  customer, negotiated terms, verified a postcode buybox, generated a
  forecast or received payment.
- `predictive_decision_control.py` attaches one read-only
  `commercial_evidence_request` to the existing Founder Console API.
  The existing private Founder UI displays the first blocked commercial
  fact, the required authoritative source and outstanding Quant
  requirements. No new dashboard/service.
- `scripts/review_first_party_buyer_evidence_20261019.py` is a one-shot
  operator entrypoint. It is offline/read-only by default; it does not
  connect Gmail, refresh CRM, mutate production, invoke Ling/OpenManus,
  send outbound, grant lead activation or move funds.

## Reproducible operator commands

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

# Inspect one evidence request against current canonical read-only snapshots.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_first_party_buyer_evidence_20261019

# AFTER owner/deployment approval ONLY, one real internal existing-queue task.
# This mutates the ASTRA department queue, but NOT CRM/EmpireDB or outbound.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_first_party_buyer_evidence_20261019 \
  --enqueue-founder-approved-internal-review
```

Regression:
```bash
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_revenue_buyer_evidence_handoff.py \
  tests/test_revenue_evidence_pathways.py \
  tests/test_source_mining_specialist_adapter.py \
  tests/test_department_worker.py \
  tests/test_predictive_decision_control.py tests/test_founder_dashboard.py
```

## Scientific falsification and learning requirements

- Research checklist explicitly rejects independent-looking public data
  (search volumes, source permits, email sends, tender documents and agent
  drafts) as buyer purchase intent or independent sale labels.
- Old research tasks are versioned by exact opportunity evidence state;
  newer source evidence can produce a new task without overwriting the
  previous historical receipt.
- First-party observation must be provenance-linked from the existing
  authoritative CRM/mailbox AND specifically to the product/location
  and buyer terms. The global Founder Console intentionally never
  exposes private contact or tenant records.
- Do not fit a conversion probability or expected gross profit from the
  completeness of a research checklist. The existing `quant_decision_packet`
  requires explicit evidence-backed inputs, and `economic_memory`,
  `predictive_calibration` and `lead_shadow_calibration_benchmark`
  already enforce tenant, outcome lineage and prospective time order.
- Statistical value-of-information and a model's calibrated
  likelihood require actual measured reference cohorts. A heuristic
  research ranking is NOT value-of-information in monetary terms.

## Still outstanding

The feature branch does not itself query existing CRM for a specific
first-party buying signal, nor does it validate a buyer buybox/price,
fulfilment or costs. Those should be resolved by an authorised
tenant-scoped private CRM/buyer actor reading real records; any verified
commercial observation can subsequently be attached to the existing
source normalization/Quant contracts. No private/public dataset mixing.

No production deployment, CRM or EmpireDB schema change, email, financial
activation, scheduled monitor, OpenManus/Ling model invocation or model
weight training has been authorised or performed by this release.

Release coordination is required with the owning ASTRA worker and Founder
Console agents, especially because the canonical production worker currently
does not contain the new specialist branch.
