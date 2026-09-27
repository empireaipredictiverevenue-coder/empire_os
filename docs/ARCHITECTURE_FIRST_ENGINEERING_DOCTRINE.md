# EmpireOS Architecture-First Engineering Doctrine

Date: 2026-09-25
Status: CANONICAL / REQUIRED

## Rule

**Architecture first. Implementation second. Verification before promotion.**

No new agent, tool, product, integration, workflow, service, data path, execution
capability or major feature is to be added to EmpireOS as an isolated implementation.

Before build work starts, the change must have an explicit architecture contract.

This doctrine is intended to prevent:
- duplicate subsystems;
- conflicting agents;
- hidden authority expansion;
- disconnected data stores;
- model/tool sprawl;
- brittle integrations;
- production drift from Blueprint V6;
- checklist work being implemented without system convergence.

## Required architecture contract

Every material change must define, at minimum:

1. **Purpose**
   - business problem;
   - expected commercial or operational value;
   - why an existing capability cannot already solve it.

2. **Canonical placement**
   - EmpireOS layer;
   - owning department;
   - Control Fabric component;
   - upstream dependencies;
   - downstream consumers.

3. **Truth and data contract**
   - canonical source of truth;
   - inputs and provenance;
   - outputs and schemas;
   - OBSERVED / INFERRED / FORECAST / SCENARIO / VERIFIED OUTCOME class;
   - persistence location;
   - tenant boundary where applicable.

4. **Authority contract**
   - observe / internal_write / governed_external / founder_gate;
   - explicitly forbidden actions;
   - whether it can mutate production;
   - whether it can send outbound;
   - whether it can accept terms;
   - whether it can move funds;
   - whether it can recognize revenue;
   - whether it can expand authority.

5. **Execution model**
   - synchronous / queued / event-driven / scheduled / durable workflow;
   - idempotency and dedupe;
   - concurrency ownership;
   - retry policy;
   - timeout and backpressure behavior.

6. **Agent/tool ownership**
   - Astra responsibility;
   - Needle routing role;
   - builder lane: Hermes / Pi / Empire Coder / deterministic code;
   - verifier lane: Swarm V6 / focused tests / Promptfoo;
   - specialist models such as Laya only where evidence permits;
   - no two mutating builders may own the same files/domain lease simultaneously.

7. **Safety and failure behavior**
   - fail-open vs fail-closed decision;
   - degradation path;
   - circuit breaker / kill switch;
   - rollback;
   - protected-path constraints;
   - external dependency loss behavior.

8. **Observability**
   - trace/events;
   - health;
   - latency;
   - cost where applicable;
   - error state;
   - evidence refs;
   - Founder Console surface.

9. **Verification and promotion**
   - unit/focused tests;
   - integration tests;
   - model/eval tests where applicable;
   - live runtime verification;
   - canonical-data verification;
   - shadow period where applicable;
   - promotion criteria;
   - explicit DONE evidence.

10. **Commercial fit**
    - effect on first revenue / recurring revenue / margin / capacity / retention;
    - product/offer relationship where applicable;
    - no fabricated economics.

## Change classes

### A. Architecture change
Required for:
- new agents;
- new external tools/frameworks;
- new services;
- new data stores;
- new queues/workflow engines;
- new commercial/payment paths;
- new authority;
- new products;
- new tenant/security boundaries.

Requires a full architecture contract before implementation.

### B. Architecture delta
Used for:
- bounded extension to an existing canonical component;
- focused API/read surface;
- small internal adapter;
- narrow bug fix that changes behavior but not system ownership.

Must still record:
- owner/component;
- changed interface;
- authority impact;
- tests;
- rollback;
- DONE evidence.

This prevents architecture-first discipline from becoming a delivery bottleneck.

### C. Pure corrective maintenance
For a bug that restores already-documented behavior without changing architecture.

May proceed immediately, but must:
- preserve current authority;
- use explicit paths;
- run focused tests;
- verify the runtime result;
- update the checklist if the fix closes an item.

## Canonical build flow

FOUNDER / BUSINESS PRIORITY
→ MASTER EXECUTION LEDGER
→ ARCHITECTURE CONTRACT / DELTA
→ ASTRA PRIORITIZATION
→ NEEDLE ROUTING
→ MUTATING BUILDER LEASE
→ HERMES / PI / EMPIRE CODER / DETERMINISTIC IMPLEMENTATION
→ SWARM V6 + TESTS
→ PROMPTFOO / MODEL EVAL WHERE APPLICABLE
→ OTEL / LANGFUSE OBSERVABILITY
→ PROPOSAL / SAFE MERGE
→ LIVE RUNTIME VERIFICATION
→ CANONICAL DATA / FOUNDER SURFACE VERIFICATION
→ CHECKLIST DONE EVIDENCE
→ CORTEX / ECONOMIC MEMORY FEEDBACK

## Builder isolation rule

Mutating implementation agents are workers, not authorities.

- Hermes: governed isolated worktree builder.
- Pi Agent: sandboxed secondary coding worker.
- Empire Coder: queued bounded implementation worker.
- Space Agent: workspace/UI builder only.
- Agent Reach: read/search sensor only.
- Swarm V6: independent verifier; no production mutation.
- Needle: routing; no business authority.
- Laya: evidence-backed bounded specialist only.
- Astra: coordinator; authority remains bounded by Control Fabric.

Only one mutating worker may own a given module/file/domain lease at a time.

## Production truth rule

A design, file, test, model output, proposal branch or passing CI run is not
production completion.

DONE remains:

**architecture + code + tests + live runtime + canonical data + Founder surface,
where applicable.**

Forecasts, scores, plans, proposals, sends and payment requests remain non-revenue.
Only governed verified commercial evidence can establish actual revenue state.

## Anti-drift rule

Blueprint V6, the Master Architecture, the live runtime and canonical data remain
production truth.

External tools are replaceable implementation capabilities. They never become
the authority layer simply because they are powerful or convenient.


## Founder verification rule

**Every EmpireOS change must be checked before it is called complete.**

This is a standing founder requirement and part of the production Definition of
Done. It applies to fixes, features, self-healing changes, infrastructure,
agents, data paths, commercial systems and UI changes.

The mandatory verification sequence is:

1. inspect the complete scoped diff and confirm only intended files changed;
2. run syntax / compile / static validation appropriate to the changed stack;
3. run focused tests for the changed behavior;
4. run adjacent regression tests for existing behavior that could be affected;
5. test the negative / failure / recovery path, not only the happy path;
6. verify authority invariants: no accidental outbound, funds, terms, revenue,
   database mutation or authority expansion;
7. verify dependency-loss behavior and self-healing / degradation behavior when
   the change touches an external dependency;
8. independently verify the live runtime after deployment;
9. verify canonical data / Founder surface when applicable;
10. confirm the tracked worktree is clean and the deployed HEAD is the intended
    commit.

A passing unit test alone is not DONE. A successful build alone is not DONE. A
commit or push alone is not DONE. A service being active alone is not DONE.

If any verification step fails, promotion stops at that failure point. The
failure is repaired forward, the affected verification set is rerun, and live
verification is repeated before the change may be marked complete.

For recovery and self-healing changes specifically, the verifier must prove:

- the original failure is detected;
- the recovery action is bounded and reversible;
- the recovery path cannot bypass a deliberate safety circuit;
- the recovery path survives the dependency failure it is intended to cover;
- the watchdog responsible for recovery remains alive during that failure;
- last-known-good local state is not replaced by empty/error state;
- normal behavior resumes when the dependency becomes healthy;
- founder-gated actions remain founder-gated.

This rule is permanent unless the founder explicitly changes it.
