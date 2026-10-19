# Empire AI flagship — Quant Brain point-in-time market feature pipeline

19 October 2026 | Branch: feature/predictive-decision-control-20261018
Owner: Predictive Intelligence / Quant Brain + Scientific Agent

## Why this is important

The flagship's knowledge graph gives ASTRA contextual market understanding
before the first buyer conversation. However, a public conversation about
roofing marketing cannot prove an actual buyer order or the probability that
a qualified lead will turn into paid and fulfilled revenue.

To make predictive models scientifically auditable, we need to freeze
exactly what the system genuinely knew BEFORE any forecast was made,
then evaluate it against later independently verified outcomes. This new
pipeline performs the first half safely.

## Implemented components

`empire_os/flagship_predictive_market_features.py`
- Accepts the existing `flagship_market_knowledge_graph.v1` only in
  OBSERVE with no payments, external execution, tenant-data retrieval,
  training, buyer-conversation claims or ROI claims.
- Requires a trusted timezone-aware issuance timestamp and captured
  graph timestamp no older than six hours; graph built AFTER a proposed
  forecast issue is rejected. This prevents retrospective look-ahead.
- Verifies graph node/edge counts, unique IDs, provenance hashes,
  limited edge types, expected node-to-node relationships, duplicate
  public observations and source/theme chronology.
- Extracts research-only features for six existing declared markets:
  roofing, solar, HVAC, agency, B2B, law. This is an initial slice,
  not a restriction on the full flagship market universe.
- Per-market: declared source venue count; distinct attributable public
  discussions; 0-2, 3-6, 7-13-day recency buckets; observed problem
  theme counts; deterministic source lineage SHA-256. Exactly one
  source post may carry several problem themes—those do NOT become
  independent buyer observations.
- No-market-observation is **NOT** interpreted as zero market demand.
  Reddit/community sources have selection and source-coverage biases.
- Explicit fields state no verified label, buying intent, sample
  independence, forecasting probability, revenue forecast, model
  training, commercial action or external causal attribution.

`review_market_feature_prediction_gap`
- Links directly to the existing `empire_os.quant_brain.quant_decision_packet`
  with EMPTY commercial/economics inputs, precisely because they have
  not yet been verified from first-party buyer evidence.
- Returns the exact missing Quant fields: probability_success,
  conditional_revenue_cents, fixed_cost_cents, success_cost_cents,
  revenue_low_cents, revenue_high_cents, success_cost_low_cents,
  success_cost_high_cents, uncertainty, time_to_revenue_days and confidence.
- Market source observations are CONTEXT; they can never silently
  substitute for the missing commercial inputs.
- Outputs six market status rows and strictly held Quant packets,
  source lineage and the next grounded evidence action.
- Does not start Monte Carlo or create speculative probabilities.

`empire_os/flagship_predictive_feature_custody.py`
- Explicit local feature-worktree-only, private original feature
  snapshot preservation, SHA-256 content addressing and readback.
- `0600` receipt, `0700` new directory, exclusive create, fsync,
  idempotent duplicate, no overwrites, unsafe links/permissions held,
  corrupt readback held. No source raw body/author or buyer contact
  stored in the packet.
- This is **NOT** a signed immutable time server, an authenticated
  EmpireDB registry, canonical commercial prediction registration,
  fulfilment proof or Economic Memory outcome.
- Filesystem administrators could rewrite/delete history. A signed or
  database-anchored event is required before enterprise calibration
  or customer-facing claim.

`scripts/review_flagship_predictive_market_features_20261019.py`
- Defaults to SOURCE REVIEW ONLY.
- Explicit `--capture-original-feature-snapshot` writes one
  private feature packet to the dedicated isolated owner worktree,
  with deterministic readback. Never runs in other agents' worktrees.
- No network collection, no customer data, no LLM call, no paid API,
  no EmpireDB writes, no email, no model mutation or funds.

`empire_os/predictive_decision_control.py` and
`apps/search-command-centre`: existing Founder-only read API and
UI now display market feature counts, Quant held-packet count and
top problem themes, while preserving all original forecasting status
boundaries. UI source is NOT deployed.

## First real source-observation checkpoint

Actual existing canonical source snapshots from 19 October 2026:

- 6 market cohorts prepared; 2 market cohorts with currently
  attributable recent public discussion (dependent on review time).
- 0 Quant-ready economic packets; 0 customer conversion probabilities.
- The explicit first original feature packet was saved to the
  feature worktree's private
  `runtime/scientific_evaluation/market_features/` folder.
- The original 0600 receipt was READ BACK successfully.
- Private original feature SHA:
  `9ce582abc423450c103b657f8be8d632bb11c4a7c253f765224a5de198ad6537`.
- The SHA covers descriptive aggregate market evidence, source
  timestamps and explicit absence of outcome proof—not a forecast.
- Production issuer activation, original-conversion-registry
  authentication, paid customer results and model training remain OFF.

This packet is timestamped BEFORE future buyer evidence, so later work
can compare against a genuinely prior observation. Its self-reported
timestamp is NOT externally anchored; a future independent time
attestation is necessary for high-trust evaluation.

## Model science and product milestones

1. Continue market coverage beyond the six initial verticals and
   establish time-ordered daily feature snapshots through an
   approved durable first-party source capture pipeline. Preserve
   original ingestion timestamp, license and exact source as known
   BEFORE issue. Do not backfill later posts into earlier forecasts.
2. Add independent source coverage and measurements from GSC,
   first-party website actions, lawful industry/procurement sources,
   competitive intelligence and property/storm exposure sources,
   each in its own timestamped and licensed domain.
3. Verify ONE buyer's exact offer, territory, price, unit economics,
   consent, delivery capacity, and genuine acceptance. No simulated
   data may substitute for the original commercial receipt.
4. Use the staged original conversion registry under authenticated
   EmpireDB control (not activated by this feature work) for real
   tenant-scoped prospective prediction receipts. Model version,
   decision/ref, input lineage and horizon must be preserved BEFORE
   outcome occurs.
5. Join later verified terminal sale/payment/fulfilment outcomes
   using Economic Memory and `lead_shadow_calibration_benchmark`,
   with tenant isolation, availability-before-prediction,
   non-overlapping time holdouts, Brier/accuracy versus historical
   base-rate and uncertainty calibration.
6. Compare out-of-sample performance of knowledge-graph-enhanced
   forecasts against the original model WITHOUT these features.
   Repeated-post bias, sparse verticals, seasonal and geography shifts,
   class imbalance and concept drift must be measured; a ranking gain
   on a tiny synthetic dataset is not deployable proof.
7. Only then promote independently verified forecasts, with version
   pinning, rollback, customer-readable source explanations and
   residual uncertainty. No agent may self-promote model weights or
   claim causal revenue effects.

The knowledge graph is NOT a training corpus; approved saved
ChatGPT examples remain separate deidentified lessons and cannot
be counted as commercial labels. No previously saved conversation
was automatically imported into this wave.

## Verification commands

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_flagship_predictive_market_features.py \
  tests/test_flagship_predictive_feature_custody.py \
  tests/test_flagship_market_knowledge_graph.py \
  tests/test_predictive_formula_evidence_review.py \
  tests/test_predictive_learning_readiness.py \
  tests/test_founder_dashboard.py

# Pure preview: no writes:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_predictive_market_features_20261019

# Only when explicitly requesting a single original feature capture:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_flagship_predictive_market_features_20261019 \
  --capture-original-feature-snapshot
```

Release truth: feature branch only. No production deployment, DB
schema/permissions, public customer portal, payment, customer outbound,
model credential or autonomous agent capability changes.
