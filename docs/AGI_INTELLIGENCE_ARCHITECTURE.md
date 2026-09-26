# Empire AI — Agentic General Intelligence Architecture

Date: 2026-09-20
Status: CANONICAL COGNITIVE / AGENTIC ARCHITECTURE
Claim discipline: Empire does not claim proven human-level AGI or ASI.

"AGI" inside Empire is an engineering label for the general-purpose agentic
intelligence stack. The system must earn capability through measurable
performance, evidence, outcome calibration and safe tool use rather than
through naming.

## 1. Objective

Build a general-purpose commercial intelligence system capable of:

**perceive -> understand -> remember -> model -> reason -> plan -> simulate ->
delegate -> verify -> govern -> execute -> observe outcome -> learn.**

Astra is the top operating coordinator. Specialist agents are capabilities
inside the system, not independent sources of authority.

## 2. Core Rule

Intelligence and authority are separate.

A model may:
- observe
- retrieve
- reason
- propose
- simulate
- critique
- forecast
- recommend

A model does not automatically gain permission to:
- send outreach
- spend money
- change pricing
- move funds
- allocate inventory
- alter production infrastructure
- modify model weights
- create commercial truth

Authority comes from policy + evidence + explicit runtime roles.

## 3. Layer 0 — Evidence / Reality Grounding

Inputs come from the Empire Data Plane and canonical systems:
- Intelligence Fabric
- Revenue CRM
- Conversation OS
- Search/Growth
- buyer/capacity/corridor records
- market/permit/storm/satellite intelligence
- BSC payment verification
- fulfilment/outcomes
- source health
- infrastructure telemetry

Every observation has:
- canonical ID where available
- source/provenance
- observed_at
- freshness
- confidence
- evidence refs
- unknown fields left unknown

No agent may convert missing evidence into invented state.

## 4. Layer 1 — Perception

Perception converts raw/canonical observations into bounded task context.

Responsibilities:
- retrieve relevant entities
- retrieve recent events/signals
- normalize units/time/geography
- identify missing/stale evidence
- detect conflicts
- identify source-health issues
- produce a compact evidence packet

Perception does not choose actions.

## 5. Layer 2 — World Model

The world model includes two grounded real-world intelligence sublayers:

### Volumetric Intelligence
Represents where things are and how they occupy 3D space:
- point clouds, meshes, voxel fields, Gaussian splats and depth maps;
- property/building/site geometry;
- terrain and spatial context;
- digital-twin geometry;
- spatial change over time;
- explicit coordinate-frame and provenance metadata.

### Natural Physical Intelligence
Represents measured or evidence-backed physical state and plausible consequence:
- storm/roof/material condition;
- heat/thermal loss and HVAC load;
- flood/water exposure;
- structural/load state;
- solar exposure;
- motion and surface change;
- asset degradation and maintenance condition.

Rules:
- physical measurements are observations, not guesses;
- absent measurements remain UNKNOWN;
- inferred consequences are labeled modeled_only;
- physics/spatial reasoning grants no execution authority;
- all derived opportunities retain source evidence refs and confidence where available.

Empire's commercial world model represents:
- companies
- people/buying committees
- markets
- territories
- corridors
- buyers
- products/offers
- campaigns/content
- conversations
- payments
- outcomes
- infrastructure/resources
- causal/experimental relationships

The world model supports:
- current state
- historical state
- change detection
- hypothetical state
- uncertainty/conflict
- provenance traversal

It is temporal and evidence-backed.

## 6. Layer 3 — Memory System

Memory is not one vector database.

### Working Memory
Task-local bounded context:
- goal
- active constraints
- evidence
- candidate options
- current plan
- tool results

Short-lived and aggressively compacted.

### Episodic Memory
What happened:
- decision packet
- action/exposure
- result
- payment/outcome
- success/failure
- timestamps
- evidence

### Semantic Memory
Stable knowledge:
- entities
- relationships
- market facts
- product definitions
- policies
- source reliability

### Procedural Memory
How to perform repeatable workflows:
- playbooks
- tool contracts
- approved sequences
- validation rules
- runbooks

### Outcome-Conditioned Memory
Only verified outcomes may promote a tactic into trusted commercial memory.

Synthetic/simulated examples never become real-outcome memory.

## 7. Layer 4 — Goal / Utility System

Goals must be explicit and bounded.

The mathematical decision layer beneath this utility system is defined in
`QUANTITATIVE_INTELLIGENCE_ARCHITECTURE.md`. LLM reasoning proposes and
interprets options; the Quant Brain computes probability, uncertainty,
expected economics, downside, calibration, value of information and portfolio
risk from explicit evidence.

Primary business objective:
**maximize expected long-run realized gross profit subject to risk,
customer value, legal/compliance, capital, capacity and authority constraints.**

Supporting objectives:
- MRR growth
- retention/expansion
- buyer satisfaction
- source/data quality
- forecast calibration
- lower acquisition cost
- lower time-to-revenue
- operational reliability

The utility layer may not rewrite its own hard constraints.

## 8. Layer 5 — Deliberative Planner

Planner responsibilities:
- decompose objective
- create candidate strategies
- identify dependencies
- estimate value/cost/time/risk
- ask for missing evidence
- choose reversible first steps
- produce a bounded plan

Planning output must contain:
- goal
- assumptions
- evidence refs
- options considered
- selected option
- expected economics
- dependencies
- blockers
- rollback/stop conditions
- required authority

Do not persist private chain-of-thought.
Persist concise decision rationale, evidence and alternatives.

## 9. Layer 6 — Model Router / Cognitive Compute

Use the cheapest capable model for each job.

Task classes:
- deterministic rules/calculation
- local small model
- local coding/reasoning model
- specialist external model
- premium reasoning model
- multimodal model
- verifier model

Routing criteria:
- task complexity
- expected commercial value
- latency
- privacy
- cost
- required modality
- historical model performance
- confidence
- verification need

A premium model is justified by expected decision value, not prestige.

## 10. Layer 7 — Specialist Agent Mesh

Specialists include:
- market intelligence
- data acquisition
- company/person intelligence
- Search/SEO/AEO/GEO
- content
- GTM
- outreach
- sales/closer
- buyer intelligence
- permits
- storm/satellite
- warehouse/industrial
- predictive/revenue
- experiment/causal
- capital
- finance
- legal/compliance
- security
- software engineering
- infrastructure

Specialists:
- receive scoped tasks
- receive bounded data
- return structured artifacts
- have no authority beyond their declared capability
- cannot silently call unrelated tools

## 11. Layer 8 — Multi-Agent Deliberation / Council

Use councils only where diversity adds value.

Valid uses:
- strategy alternatives
- high-value commercial reviews
- conflicting evidence
- architectural decisions
- risk review
- offer/campaign critique

Council pattern:
1. independent proposals
2. evidence normalization
3. disagreement extraction
4. verifier review
5. decision synthesis

Do not use majority vote as truth.
Evidence quality, calibration and domain authority matter more than vote count.

Legacy heuristic council code must not be treated as an autonomous production
ship authority.

## 12. Layer 9 — Critic / Verifier

Important decisions receive independent verification.

Verifier checks:
- evidence support
- factual consistency
- calculations
- policy
- authority
- freshness
- source conflicts
- prediction vs fact separation
- hallucination/invention
- irreversible action risk

Where practical the verifier should use:
- a different model/provider, or
- deterministic validation, or
- an independent evidence retrieval path

A failed verifier blocks execution readiness.

## 13. Layer 10 — Simulator / Counterfactual Engine

Before consequential action:
- simulate options
- compare expected economics
- stress capacity
- test downside
- estimate uncertainty
- model counterfactuals
- use historical analogues

Simulation is permanently labelled:
- simulation_only=true
- actual_revenue=false
- execution_authority=none

## 14. Layer 11 — Policy / Constitutional Control Plane

Hard constraints live outside model prompts.

Policy evaluates:
- identity/role
- requested capability
- data classification
- evidence requirements
- monetary exposure
- external side effects
- reversibility
- approval state
- customer/tenant scope
- rate/volume limits

Authority modes:
- OBSERVE
- ASSIST
- GUARDED_EXECUTE
- future bounded autonomous authority

Consequential actions require explicit capability grants.

## 15. Layer 12 — Execution Bus

All side effects use typed tools/capabilities through the execution bus.

Examples:
- content draft
- page preview
- approved publish
- approved email
- approved voice call
- campaign mutation
- seat allocation
- BSC settlement
- infrastructure change

The execution bus enforces:
- capability allowlist
- idempotency
- approval
- rate/amount limits
- audit log
- rollback where possible
- result evidence

Agents do not get unrestricted shell/database/provider credentials.

## 16. Layer 13 — Observer / Runtime Safety

Observer watches:
- agent health
- tool errors
- drift
- source quality
- stuck loops
- token/model cost
- repeated retries
- unusual action volume
- stale world state
- policy violations

Observer can:
- stop/pause a workflow
- quarantine a task
- downgrade to OBSERVE
- request operator review

It cannot fabricate recovery evidence.

## 17. Layer 14 — Learning / Meta-Learning

Learning loop:

prediction
-> decision
-> approved action/exposure
-> verified outcome
-> realized revenue/cost/gross profit
-> calibration
-> model/tactic review
-> controlled update.

Learning classes:
- prompt/playbook learning
- retrieval/ranking learning
- forecast calibration
- offer/channel learning
- source reliability
- buyer/corridor quality
- model routing performance
- later model fine-tuning when dataset size/quality justify it

No self-modifying production model weights from unverified outcomes.

Changes move through:
PROPOSED -> EVALUATED -> SHADOW -> APPROVED -> DEPLOYED -> MONITORED.

## 18. Layer 15 — Self-Improvement

Safe self-improvement:
- detect weak performance
- propose better prompts/playbooks
- propose new tools
- generate test cases
- run evaluations
- compare against baseline
- recommend promotion

Not safe by default:
- rewriting production policy
- widening permissions
- deploying arbitrary code
- creating credentials
- moving money
- declaring its own evaluation passed

The system may improve its intelligence without automatically expanding its
authority.

## 19. Layer 16 — Evaluation System

Every cognitive layer must be measurable.

Evaluation domains:
- retrieval precision/recall
- entity-resolution accuracy
- factual grounding
- forecast calibration
- recommendation value
- plan success
- verifier catch rate
- tool success
- cost
- latency
- safety/policy compliance
- outcome/gross-profit lift

Evaluation sets:
- frozen regression cases
- live shadow cases
- adversarial cases
- source-conflict cases
- missing-data cases
- high-value commercial cases
- postmortems

## 20. Layer 17 — Agent Identity / Trust

Every agent/runtime has:
- agent ID
- role
- version
- model/provider
- capabilities
- tenant/data scope
- authority mode
- public key/signature where A2A applies
- execution history
- evaluation history

A2A trust does not imply commercial authority.

## 21. Layer 18 — Cognitive Audit / Decision Ledger

Persist:
- goal
- task ID
- world-state/evidence refs
- memory refs
- model/router choice
- proposed options
- concise rationale
- selected plan
- verifier result
- policy result
- tool/action refs
- outcome refs
- cost/latency
- calibration

Do not persist private chain-of-thought.
Store decision-relevant, auditable summaries.

## 22. Astra's Role

Astra is not one giant model.

Astra is the executive/cognitive coordinator that:
- receives operating goals
- reads the world model
- retrieves memory
- prioritizes work
- selects planner/specialists/models
- requests simulations
- invokes verifier
- checks policy/authority
- dispatches approved capabilities
- observes outcomes
- triggers learning review

This avoids a brittle "one super-agent does everything" architecture.

## 23. Relationship to Existing Empire Components

Canonical:
- Data Plane -> grounding/evidence
- Intelligence Fabric -> world model
- Predictive Cloud -> forecasting/economics
- Experiment/Causal -> causal review
- Digital Twin -> simulation
- Astra -> coordinator
- Revenue OS -> decision/outcome integration
- Conversation OS -> channel history
- Revenue CRM -> commercial state
- Execution Bus -> side effects
- Enterprise controls -> policy/reliability

Legacy:
- files named agi_* may remain for compatibility, but naming alone gives them no
  higher trust or authority.
- legacy "ASI" reflection is not treated as superintelligence.
- synthetic intelligence is simulation/test material only and never production
  commercial truth.

## 24. Correct Cognitive Cycle

1. RECEIVE GOAL
2. CLASSIFY RISK/AUTHORITY
3. PERCEIVE CANONICAL WORLD STATE
4. CHECK SOURCE FRESHNESS
5. RETRIEVE RELEVANT MEMORY
6. IDENTIFY UNKNOWN/MISSING EVIDENCE
7. PLAN MULTIPLE OPTIONS
8. ESTIMATE ECONOMICS/RISK
9. SIMULATE WHEN WARRANTED
10. CONSULT SPECIALISTS
11. VERIFY
12. POLICY/AUTHORITY CHECK
13. HUMAN APPROVAL IF REQUIRED
14. EXECUTE TYPED CAPABILITY
15. VERIFY EXECUTION RESULT
16. OBSERVE COMMERCIAL OUTCOME
17. CALIBRATE
18. PROPOSE LEARNING/IMPROVEMENT

## 25. Immediate Engineering Slices

### Slice A — Cognitive Packet
Typed goal/world-state/memory/plan/verification/policy packet.

### Slice B — AGI Readiness
Assess grounding, world model, memory, planning, verification, policy,
execution and outcome-learning completeness.

### Slice C — Memory Router
Working/episodic/semantic/procedural/outcome memory contracts.

### Slice D — Planner
Multiple-option plan with dependencies, economics, reversibility and authority.

### Slice E — Verifier
Independent evidence/policy verification packet.

### Slice F — Model Router
Capability/cost/value/privacy-aware model selection.

### Slice G — Tool Capability Registry
Typed tool permissions and side-effect classification.

### Slice H — Evaluation Harness
Frozen/shadow/adversarial evaluations with promotion gates.

### Slice I — Learning Registry
Outcome-linked proposed improvement -> evaluation -> shadow -> promotion.

### Slice J — Cognitive Control Tower
Astra view of tasks, models, plans, verifiers, costs, failures and outcomes.

## 26. Success Definition

Empire is becoming more generally intelligent when it demonstrates measurable
improvements across diverse tasks while remaining grounded, efficient and safe.

We do not define AGI by:
- number of agents
- number of LLM calls
- self-referential "ASI" labels
- autonomous loops
- synthetic examples
- persuasive demos

We define progress by:
- transfer across tasks
- robust reasoning
- grounded decisions
- planning quality
- tool competence
- calibrated uncertainty
- memory usefulness
- adaptation from verified outcomes
- causal learning
- generalization
- reliable commercial results
- safe authority control.
