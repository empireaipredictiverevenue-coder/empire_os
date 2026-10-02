# Empire Intelligence Optimization Fabric V2

Status: OBSERVE candidate
Authority: none
Production promotion: false
Database migration: none
External QPU execution: disabled

## Goal

Create one scalable optimization backbone shared by Predictive Revenue, Predictive
Cloud, AGI orchestration and domain systems. Quantum is a specialist solver lane,
not the controller and not a replacement for forecasting.

## Canonical flow

REAL EVIDENCE
  -> PREDICTIVE REVENUE
  -> PREDICTIVE CLOUD SCENARIOS
  -> OPTIMIZATION PROBLEM FACTORY
  -> SOLVER INTELLIGENCE ROUTER
  -> CLASSICAL / QUANTUM-INSPIRED / HYBRID / QPU BENCHMARK LANE
  -> SOLUTION VALIDATION
  -> BENCHMARK LEDGER
  -> AGI SYNTHESIS
  -> AUTHORITY GATE
  -> SEPARATELY AUTHORIZED EXECUTION
  -> VERIFIED OUTCOME
  -> ECONOMIC MEMORY / CORTEX

## V2 contracts

### Optimization Problem Factory

Every eligible domain problem compiles to a provider-neutral IR with:
- deterministic problem fingerprint
- workload type and source schema
- variable type and explicit objective
- hard constraints
- evidence references
- unknown-preserving time/cost budgets
- optional representation capabilities such as CQM and QUBO
- execution_authority=none

No missing economic value, cost, capacity, constraint or evidence may be converted
to zero.

### Scalable decomposition

Large problems may be split only when constraint topology proves partitions are
independent. If constraints span partitions, the plan must report
coordinator_decomposition_required rather than pretending shards are independent.

### Solver Intelligence

The router separates:
- installed runtime
- explicitly Empire-enabled external runtime
- primary classical lane
- optional benchmark lanes
- fallback chain

A QPU is never selected merely because its SDK is installed. External QPU lanes
require an explicit Empire enable flag and remain benchmark-only in this slice.

### Benchmark / Quantum Advantage Ledger

Every comparison binds to the same problem fingerprint and records:
- solver family/provider/hardware class
- objective value
- feasibility
- wall clock
- compute cost where known
- baseline objective/latency/cost
- repeatability evidence

A single benchmark can establish measured comparison evidence but can never set
quantum_advantage_claimed=true. Promotion remains a separate governed decision.

## AGI integration

The existing AGI orchestrator may consume an
empire.intelligence_optimization_fabric.v2 packet through its governed
quantum/optimization specialist slot. It detects solver readiness,
representation eligibility and cross-partition reconciliation requirements. If
no compatible solver is implemented, AGI recommends establishing a solver lane
rather than treating model eligibility as execution readiness.

## Scale model

## Governed optimization runtime

The shared optimization runtime executes only the solver selected by the
governed router and remains recommendation-only. A generic exact-binary
reference is available for small Empire Optimization IR problems and is capped
at 18 variables by default (at most 262,144 exhaustive states). Larger bounded
binary-linear workloads can route to the optional OR-Tools CP-SAT adapter.

When the decomposition contract proves shards independent, CP-SAT shards may
run concurrently and their objective/selected-variable results are reconciled.
When constraints cross partitions, the runtime preserves the global model
rather than dropping constraints for parallelism.

## Safe horizontal execution

The V2 scale layer materializes and runs independent optimization shards only
when the decomposition planner proves that no hard constraint crosses shard
boundaries. Proven-independent shards may execute CP-SAT concurrently with
bounded per-shard workers. Any cross-partition or global constraint returns
coordinator_decomposition_required and is not silently discarded.

Control plane and compute plane remain separate. Problems are immutable,
fingerprinted work packets suitable for queues and horizontally scaled workers.
Large workloads use proven-safe independent shards or a coordinator pattern for
global constraints. Solver backends are replaceable provider adapters.

## First scalable classical adapter

Google OR-Tools CP-SAT is the first optional scalable classical adapter. The
repository records it under the optimization optional dependency group as
ortools>=9.15,<10. The adapter is lazy-loaded and supports binary linear
Empire Optimization IR only in V1. It requires an explicit wall-clock budget,
independently validates returned assignments against the original unscaled
constraints, and never invents compute cost.

Current upstream review on 2026-10-02 found OR-Tools v9.15 with Python 3.14
support and Apache licensing. Qiskit Optimization itself was archived in July
2026; future IBM/Qiskit integration should target the maintained optimization
mapper/addon path after a separate adapter review rather than embedding the
archived package.

## Initial solver policy

1. Small bounded problems: exact classical reference where supported.
2. Larger combinatorial problems: strong classical lane first.
3. Quantum-inspired / CQM / QUBO / QAOA: benchmark candidates only.
4. External QPU: opt-in benchmark lane only.
5. Every candidate must be validated against identical constraints and objective.

## Open-source intake direction

Prefer provider adapters and bounded pattern adoption over ownership inversion.
Strong current candidates include Apache-2.0 OR-Tools for classical
combinatorial optimization and Apache-2.0 quantum SDK ecosystems such as
PennyLane/Amazon Braket integrations where appropriate. Qiskit, D-Wave Ocean
and other current projects require source/license/security review before any
runtime dependency is introduced.

Current adapter intake notes (2026-10-02):
- D-Wave Ocean / dwave-samplers: strong candidate for the first local
  quantum-inspired BQM benchmark lane because it exposes local simulated
  annealing, simulated quantum annealing, tabu and related samplers under
  permissive open-source licensing.
- PennyLane: strong candidate for provider-neutral QAOA / hybrid experiment
  adapters after the common QUBO/Hamiltonian compiler is hardened; current
  upstream packaging includes Python 3.14 support.
- Qiskit: do not adopt the archived qiskit-optimization package. Evaluate the
  maintained qiskit-addon-opt-mapper path plus current runtime/provider APIs
  behind an Empire adapter.
- External QPU runtimes remain benchmark-only and require explicit provider,
  route, time and compute-cost budgets before any remote call.

No external SDK becomes the canonical evidence store or authority plane.

## Worker assignment

Main architecture lane owns this foundational V2 contract and pure-Python
provider-neutral implementation. Search V2 remains delegated to Hermes and must
not be touched here. Digital Avatar/Recall and Founder Dashboard paths remain
out of scope.

## Definition of done for this slice

- common IR compiles existing buyer-allocation and action-portfolio problems
- deterministic fingerprint tested
- unsafe decomposition fails closed
- solver discovery/routing tested without provider credentials
- benchmark records bind to same problem fingerprint and preserve unknown cost
- no quantum-advantage claim
- existing quantum/hybrid/action-portfolio regressions remain green
- no production deployment or authority expansion
