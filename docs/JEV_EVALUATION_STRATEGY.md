# Empire AI — Jev Evaluation & Long-Term Integration Strategy

Date: 2026-09-20
Owner: Strategy + R&D + AGI/Quant
Status: EVALUATE / SHADOW ONLY — no provider activation implied

## 1. What Jev Is

Jev from TypeSafe AI is a machine-facing decision model. It consumes a state plus
typed questions and returns structured decisions with probabilities/confidence
rather than generating prose.

Empire should treat Jev as a potential **System-One decision primitive**, not as
a replacement for:
- LLM reasoning
- deterministic code
- Quant Brain mathematics
- policy
- commercial authority
- human review

Canonical division of labour:

**LLM/AGI understands and proposes -> Jev may judge/rank/route -> Quant computes
economics -> deterministic code enforces rules -> policy grants authority ->
execution bus acts.**

## 2. Why It Could Matter to Empire

Empire has thousands of potential small decisions that do not need a full
generative model:

- which specialist agent should receive a task
- whether evidence is strong enough to escalate
- classify buyer intent
- classify reply type
- route a conversation
- choose continue/retry/stop/review
- score source relevance
- triage search/keyword intent
- classify campaign assets
- flag risky or contradictory output
- route a coding task
- prioritize data-quality review
- detect whether a state matches an allowed action class
- decide whether expensive reasoning is warranted

A fast, low-cost typed-decision model could reduce latency/cost and increase
structured consistency for these bounded judgments.

## 3. Best Long-Term Empire Use Cases

### A. Astra Cognitive Router
Candidate questions:
- Which specialist should handle this?
- Does this task need premium reasoning?
- Is evidence sufficient for another planning step?
- Continue / retry / stop / escalate?
- Which verifier path should run?

Jev must never bypass the typed capability registry or policy layer.

### B. Model Router
Use Jev as one signal for:
- deterministic code vs local model vs premium model
- verifier required vs not required
- multimodal required vs not required
- human review required

Quant Brain remains responsible for value/cost calculations.

### C. Outreach / Conversation OS
Potential bounded judgments:
- positive / negative / question / objection / later / unsubscribe
- buyer intent strength
- urgency
- routing to closer vs nurture vs stop
- evidence completeness

No autonomous send/call authority follows from a Jev decision.

### D. Search / SEO / Keyword Strategy
Potential judgments:
- query intent class
- funnel stage
- product fit class
- content/asset type
- citation relevance
- competitor relevance
- doorway/spam-risk screening
- content-refresh triage

Observed search metrics remain sourced from real Search Intelligence data.

### E. Content / Marketing Quality Gate
Potential decisions:
- claim requires proof?
- message fits ICP?
- asset matches funnel stage?
- duplicated angle?
- factual-risk class?
- route to legal/compliance review?

Jev would gate/route; generative models still create the asset.

### F. Data Plane / Intelligence Fabric
Potential judgments:
- source relevance
- record triage
- evidence quality class
- likely entity-match class
- quarantine vs accept-for-review
- schema/content category

Deterministic schema/provenance checks remain code.

### G. R&D / Research Radar
Potential decisions:
- paper/project relevance
- novelty class
- reproduce / watch / ignore
- capability family
- research-priority class

Research conclusions still require evidence/reproduction.

### H. Coder Conveyor
Potential judgments:
- task type
- repo/domain routing
- test class needed
- likely risk class
- diff requires security review?
- continue / retry / escalate

No Jev decision grants shell/deploy permission.

### I. Chief of Staff / Company Ops
Potential judgments:
- interrupt / same-day / weekly / delegated
- department owner
- initiative class
- blocker type
- decision type

Priority economics stay with Quant/company scoring.

### J. Fraud / Abuse / Policy Triage
Potential classifications can support:
- suspicious provider event
- unusual commercial request
- malformed/unsafe tool request
- evidence conflict

Hard policy remains deterministic/external.

## 4. Where Jev Should NOT Be Used

Do not use Jev as the primary engine for:
- open-ended strategic reasoning
- long-form content generation
- coding generation
- legal interpretation
- deterministic accounting
- expected-value mathematics
- cryptographic/payment verification
- schema validation that code can do exactly
- market-share claims
- production permission decisions by itself
- moving funds
- infrastructure changes

If a problem has an exact deterministic rule, use code.

If a problem needs deep synthesis/reasoning, use the appropriate reasoning model.

## 5. Proposed Empire Architecture

State packet
-> deterministic prechecks
-> Jev bounded decision layer where appropriate
-> confidence threshold
-> low-confidence route to verifier/reasoning/human
-> Quant/policy checks
-> typed execution bus.

Jev outputs should be wrapped in an Empire decision record:
- provider/model/version
- question schema version
- state hash/ref
- decision
- probability distribution
- confidence
- threshold
- route taken
- latency
- cost
- evaluation version
- downstream outcome

## 6. Confidence / Escalation Policy

Never use a single universal confidence threshold.

Thresholds must be calibrated by task.

Example:
- low-risk routing may tolerate lower confidence
- external communication routing requires stronger calibration
- security/compliance triage requires fail-closed review
- commercial/financial actions cannot be authorized by Jev alone

Thresholds must be learned from private Empire evals.

## 7. Private Evaluation Programme

Before any production routing:

### Phase 1 — Offline Eval
Create frozen Empire datasets for:
- agent routing
- reply classification
- keyword intent
- evidence quality
- coder-task classification
- model routing
- content quality gating

Compare:
- deterministic baseline
- current small/fast LLM
- current premium model
- Jev

Measure:
- accuracy / macro F1 where relevant
- calibration / Brier score
- false-positive/false-negative cost
- latency
- cost
- abstention/escalation quality
- stability across repeated calls
- operational failure rate

### Phase 2 — Shadow
Jev makes decisions but current production logic still controls the workflow.

Record:
- agreement/disagreement
- confidence
- downstream observed outcome

### Phase 3 — Bounded Assist
Allow Jev to route only low-risk internal workflows.

### Phase 4 — Guarded Production
Only after:
- sufficient private eval evidence
- calibration thresholds
- fallback path
- provider health
- cost controls
- privacy/legal review
- rollback
- monitoring

## 8. Vendor / Dependency Strategy

Jev should be an interchangeable decision-provider capability.

Do not hard-code TypeSafe into the cognitive architecture.

Empire capability:
**typed_decision.evaluate**

Potential implementations:
- Jev
- small local classifier/model
- frontier model structured output
- deterministic rules

Model Router selects based on:
- quality
- calibration
- cost
- latency
- privacy
- provider health
- task risk.

## 9. Data / Privacy Review

Before sending any Empire state:
- minimize state
- strip secrets
- classify PII/commercial sensitivity
- use canonical evidence refs where raw text is unnecessary
- respect tenant boundaries
- record provider
- review retention/training terms
- maintain fail-closed behavior if provider unavailable

## 10. Quant Integration

Jev probabilities can become input evidence for Quant Brain only after
task-specific calibration.

Never assume returned confidence is commercially calibrated.

Quant can measure:
- Brier score
- calibration buckets
- expected misclassification cost
- threshold optimization
- provider/model comparison
- economic value of routing decision

## 11. R&D Questions

R&D should answer:
1. On which Empire decisions does Jev beat deterministic rules?
2. On which does it beat small LLMs?
3. Where does it fail?
4. Are probabilities calibrated on our distribution?
5. How stable is it under state wording/ordering changes?
6. How well does it abstain/escalate?
7. What is real end-to-end latency?
8. What is real cost including retries/fallbacks?
9. Does it reduce premium-model calls?
10. Does it improve downstream commercial/operational outcomes?

## 12. Long-Term Role

If private Empire evidence supports it, Jev could become a high-frequency
decision fabric between the world model and the slower reasoning layers:

**world state -> thousands of cheap bounded judgments -> only uncertain/high-
value cases reach expensive reasoning -> policy-controlled execution.**

This is especially valuable as Empire grows to many agents, sources, buyers,
campaigns, markets and products.

The strategic advantage would not be "using Jev."

The advantage would be:
**Empire's proprietary state + task-specific decision schemas + calibrated
thresholds + outcome feedback + interchangeable decision providers.**
