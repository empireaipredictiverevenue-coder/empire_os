# Empire Research + Jev-compatible local triage — owner handoff

**21 October 2026 — development-only, OBSERVE, not a model promotion or live service release.**

The implementation is `empire_os/research/jev_source_triage.py`. It reuses
`TypedDecisionRequest`, `TypedDecisionResult` and the **existing** Laya
HTTP sidecar on the loopback interface. It does not deploy Jev's original
hosted model, add another agent/orchestrator, call a paid external inference
API, or replace Empire Research / Vane / OpenManus.

## Existing product composition

Original source discovery and rights verification remain under Empire Research.
The deterministic status triage first classifies each source as HOLD,
REINSPECT_SOURCE, RIGHTS_REVIEW or EDITORIAL_REVIEW. A local typed-decision
provider may then suggest a *different human review queue*, but its proposal
never changes the deterministic source gate, grants editorial approval,
authenticates a buyer, creates an outbound action or authorises funds.

The adapter validates **all** ledger records before any model interaction.
Requests contain only fixed source-shape enums and numeric anchor counts:
sector, country, observation status, document kind and two false authority
flags. No title, URL, page content, name, email, property address, tenant,
prospect ID, commercial confidential data or evidence snippet is sent.

This is a separate, operator-invoked research-review adapter, not a live
Founder API route, production service mutation or approved user workflow.

## Actual shadow evidence

The pinned receipt
`RESEARCH_JEV_LOCAL_SHADOW_TRIAGE_20261021.json`
records observations against the **15-source, four-sector UK/US** Research
ledger, not buyer-labelled holdouts.

- Deterministic triage: 8 editorial reviews, 1 rights review, 2 reinspections,
  4 access holds; 30-run median approximately 0.289 ms for the 15-record
  pass on this server.
- Local Laya: two shadow choices returned with approximately 2.93 s and
  2.24 s model-reported latency; both differed from deterministic review and
  were escalated, with **zero source admissions**.
- Shadow provider outcomes are advisory, and these two unlabelled comparisons
  cannot establish accuracy, calibration or performance improvement.
- Latency measurements are small-sample engineering observations, **not** a
  representative Jev benchmarking study. Running every source through the
  Laya sidecar would slow this task; the deterministic path remains the default.

## Gated owner integration and follow-up

Research owner may review this feature branch and selectively attach this
source-triage output to the **existing** authenticated Founder Research review
interface. Source and rights owners must independently approve any original
page admission or reused excerpt. The existing Jev evidence-gap bridge
(`empire_os/jev_gtm_research_bridge.py`) should be reused for future
decision-specific public evidence gaps; it should not be duplicated here.

Before further rollout, collect independently labelled real examples and
negative/contradictory cases, evaluate accuracy and p95 latency against
deterministic and local model baselines, run a small genuine shadow holdout,
and obtain existing owner signoff for any optional callback integration.
There is no automatic switch of provider authority or production routing.

**Current gates:** 0 approved new sources; 0 validated buyer intents;
0 outbound; 0 customer publication; 0 finance/DB writes; no new background
jobs, timers or model-service deployments.
