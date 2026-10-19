# Empire AI — Scientific Predictive Revenue Brain / Evidence Pathways V1

19 October 2026 | Owner: existing Source Intelligence, Opportunity Factory,
Quant Brain, ASTRA and Economic Memory. Feature branch only.

## Why this addition

The earlier source-mining worker fix addressed specialist dispatch, but the
brain still lacked a **joined, explainable way to see where a current
opportunity's data-to-economics reasoning breaks down**. Counts of permit
events, website clicks, public tenders and search queries are not enough to
claim buyer intent, conversion probability or revenue.

The word "neural pathway" is a product analogy. This implementation is a
**typed directed evidence lineage graph**, NOT a trained neural network,
artificial biological neuron, novel AGI architecture or causal inference
engine. Its role is to prevent incorrect evidence propagation.

## Pathway and scientific controls

Existing producer joins, with exact same original `opportunity_key`:

```
Existing Opportunity Radar market research
    -> Existing Opportunity Factory intake and evidence sources
    -> Existing canonical blocker/department evidence router
    -> Existing Quant Brain economics evidence
    -X-> Independently verified economic outcomes / Economic Memory
```

The final economic-outcome edge is **intentionally unverified** until an
original pre-outcome prediction can be matched to authentic buyer commercial
terms, accepted offer, payment settlement, fulfilment, realised gross
profit and the corresponding protected Economic Memory receipt.

Four existing snapshots are read from `/srv/empire_os/runtime`:
- `opportunity_radar/latest.json`;
- `opportunity_factory/intake_latest.json`;
- `opportunity_factory/evidence_routes_latest.json`;
- `opportunity_factory/quant_review_latest.json`.

The reader enforces source schema, OBSERVE execution authority, UTC freshness
(maximum six hours), cross-source time skew (maximum two hours), finite
bounded sizes (at most 250 records and 2 MB per file), unique exact keys,
matching sets of opportunity IDs across stages, and zero tenant-scoped rows
in the founder-global view. Any mismatch holds the **whole** graph, rather
than suppressing a row and falsely claiming complete coverage.

The graph audits:
- Every Opportunity Factory blocker must exactly match the authoritative
  `opportunity_evidence_router.ROUTES` contract. Unknown or mutated
  routing claims are held.
- Quant decision rows must refer to the same opportunity, agree with
  Factory readiness, disclose missing required economics fields and never
  report actual revenue. A hypothetical `prediction_ref` cannot be attached
  to an unavailable Quant packet.
- Normalised planning scores and public-source observations do not satisfy
  first-party buyer intent. A source's buyer-demand claim alongside a
  missing buyer-intent factor is flagged as a contradiction requiring
  independent review.
- Correlated versions of the same underlying public tender are not
  separate contracts; source mining has an existing OCDS process-level dedupe.
- Pathway edges are marked `IDENTITY_JOIN_ONLY` until their destination
  evidence is ready. None is marked suitable for ML training. Edge to
  Economic Memory remains `UNVERIFIED_OUTCOME`.
- For each opportunity the output shows the first missing evidence
  requirement, relevant existing research department and missing Quant
  factors. Any rank is explicitly a **transparent internal triage heuristic**
  (weighted missing-factor/blocker counts), not a calibrated conversion
  probability, causal effect, expected value of information or revenue
  prediction.

Scientific background / why: temporal validation prevents look-ahead
leakage; independent source verification prevents circular evidence;
deduplicating correlated source releases prevents pseudoreplication;
explicit unknown values prevent fabricated denominator/base-rate
estimates; an immutable prospective prediction and held-out future
terminal outcomes are necessary before prequential Brier/log-loss
calibration has empirical meaning.

The **existing Scientific Agent** research protocol continues to prescribe
source and counterevidence checks. The optional free Ling 3.1 and OpenManus
research workflows remain disconnected from execution until actual healthy
model/service capability is verified. A model-generated explanation alone
can never authenticate a source or economic settlement.

## Current live source inspection (read-only on 19 October)

A genuine, single-pass review using the currently available four production
OBSERVE snapshot files returned:
- 11 identical keyed candidates across all four source stages;
- 0 complete Quant economics decision packets;
- all observed candidates still missing buyer-intent evidence and 11
  required Quant fields each;
- prioritized owner for first blocked step: business_development;
- sample review niches include roofing, predictive_revenue_enterprise
  and HVAC. These are **market-research candidate records**, not customers,
  signed commercial opportunities, earned revenue or model forecasts.

As upstream source data changes, the output will change and stale or
cross-source inconsistent snapshots will be held.

## Files and interfaces

- `empire_os/revenue_evidence_pathways.py`: pure read-only graph join,
  freshness/authority enforcement and missing-fact triage.
- `empire_os/predictive_decision_control.py`: adds
  `decision["evidence_pathways"]` to EXISTING Founder Console output.
- `apps/search-command-centre/src/lib/founder-api.ts`: typed review shape.
- `apps/search-command-centre/src/app/founder/page.tsx`: existing private
  Founder Console evidence-brain path view with signal, analysis, economic
  and outcome stages, missing factors and contradictions.
- `scripts/review_revenue_evidence_pathways_20261019.py`: manual one-shot
  CLI for exact current source snapshots. No API/network/DB calls.
- `tests/test_revenue_evidence_pathways.py`: isolated typed joins,
  stale/duplicate/tampered data, private/tenant exclusion, contradiction
  detection and no fabricated training or money claims.

To inspect a fresh source snapshot with no mutations:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_revenue_evidence_pathways_20261019 --top 5
```

### Next useful scientific/revenue integration (NOT claimed completed)

1. Join a **real first-party verified buyer's** product, coverage and signed
   commercial price/terms to ONE specific opportunity in the authoritative
   CRM/buyer system. Keep raw personal data inside its proper tenant scope.
2. Link original offer cost, variable fulfilment cost and conditional
   economic assumptions with independent evidence and timestamps. No fake
   probability, discounting model or fabricated conversion sample.
3. With properly historical terminal-outcome observations, run model
   calibration (Brier vs genuine historical base rate) and holdout tests;
   register prospective predictions BEFORE future outcomes.
4. Reconcile actual payment/fulfilment and realised gross profit through
   the existing Economic Memory, not a public-source proxy.
5. Coordinate backend/frontend release with the owner; no production
   deployment, finance/CRM migration, new hosted model or outbound is
   authorised by this evidence-brain feature.

## Verification / safety

The new evidence-brain module and existing integration tests pass, along
with the pre-existing worker/source/scientific routes. No production DB
writes, new services, browser scraping, paid inference, emails, funds or
model-weight changes were made.
