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

## Quantum-inspired and external provider lanes

Empire quantum-inspired and quantum-simulation lanes are owned by EmpireOS and run without provider SDKs or network services.

Current owned lanes:
- Empire Annealing: bounded simulated annealing over the safe QUBO subset.
- Empire Parallel Tempering: replica-exchange Monte Carlo for harder QUBO landscapes.
- Empire QAOA Simulator: bounded p=1 statevector simulation using the Python standard library only.
- Safe QUBO compiler: only proven constraint shapes are encoded.

All quantum-style results are benchmark evidence with qpu_called=false, third_party_runtime_dependency=false and quantum_advantage_claimed=false.

## First scalable classical adapter

Empire Branch-and-Bound is the scalable classical binary-linear solver. It uses deterministic ordering, objective bounds, partial-constraint pruning and explicit node/time budgets.

Safe independent partitions may execute Empire Branch-and-Bound in parallel. Cross-partition constraints fail closed into global-coordinator-required state.

OR-Tools is optional market-reference tooling only and is not a production runtime dependency or fallback.

## Initial solver policy

1. Small bounded binary problems: Empire exact reference.
2. Larger binary-linear problems: Empire Branch-and-Bound.
3. Safe monotone fallback: Empire greedy.
4. Safe QUBO research: Empire Annealing and Parallel Tempering.
5. Small safe QUBOs: Empire QAOA statevector simulator.
6. Benchmark Arena compares identical problem fingerprints.
7. Solver memory recommends only after repeated feasibility and quality evidence.
8. Recommendation never expands business execution authority.

## Open-source intake direction

Open-source and commercial tools are research and competitive-reference inputs only. Empire may study permissively licensed algorithms, patterns and benchmarks, but production solver ownership remains EmpireOS.

Optional market-reference packages are isolated from normal execution and do not feed production Solver Policy. No third-party solver service, credential, provider SDK or network solver call is permitted in the Empire production optimization path.

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

## Queue-safe compute jobs

The compute-job protocol turns an AVAILABLE fabric plan into immutable,
deterministic, tenant-scoped work packets. It supports one root job or
independent shards only when decomposition proves no cross-shard constraints.
Each job carries its parent/problem fingerprints, solver, time/cost budgets,
recommendation-only flag and execution_authority=none. Reconciliation validates
the combined assignment against the original parent constraints before any
result can be treated as usable optimization evidence.

## Solver fallback policy

The owned runtime uses:
- Empire exact binary reference;
- Empire Branch-and-Bound;
- Empire greedy only for the proven-safe monotone subset;
- Empire Annealing and Parallel Tempering on the safe QUBO subset;
- Empire QAOA Simulator for bounded small-QUBO experiments.

Third-party market references never become automatic fallback or routing.

## Benchmark Arena and solver memory

Benchmark Arena automatically compares eligible Empire-owned solvers on the same immutable fingerprint: exact, Branch-and-Bound, Annealing, Parallel Tempering and QAOA Simulator.

Solver Performance Memory aggregates repeated evidence by workload shape. Solver Policy may issue recommendation-only advice when the workload shape matches and the lane is available.

The automatic business optimization heartbeat invokes Benchmark Arena only on bounded safe problems; market references are excluded by default.

## External QPU boundary

No external QPU/provider service is part of the current architecture.

The future hardware boundary is an Empire-owned interface concept: capabilities, submit, sample, measure and calibration. Today its implementations are local software simulation and quantum-inspired compute.

Provider credentials, cloud-QPU submissions and external solver spending are disabled.

## Current production-truth boundary

This V2 foundation is an OBSERVE/recommendation system. Local optimization
solvers may execute mathematical compute, but no commercial allocation,
outreach, publishing, payment, accounting, infrastructure mutation or other
business side effect follows from a solver result without the existing
domain-specific authority gates.

## External QPU provider sequence

The current sequence is fully Empire-owned:

1. canonical Empire Optimization IR;
2. exact classical reference;
3. Empire Branch-and-Bound and safe sharding;
4. safe QUBO compiler;
5. Empire Annealing;
6. Empire Parallel Tempering;
7. Empire QAOA statevector simulator;
8. Benchmark Arena and Solver Performance Memory;
9. future Empire-controlled QPU backend.

No third-party provider appears in the production sequence.

## IR integrity boundary

Every canonical optimization IR is fingerprinted over its semantic workload,
variables, objective, constraints, evidence, budgets and representations. The
fabric recomputes the fingerprint before routing, and low-level solver/QUBO/
shard/QPU boundaries fail closed when a packet was mutated after construction.
Variable and constraint counts plus truth/authority invariants are validated
separately so metadata tampering cannot convert prediction into execution.

## Third-party provider state

The earlier bounded external-provider experiment is superseded by the founder rule that the production optimization stack is Empire-owned.

D-Wave cloud/provider SDK components were removed from the active venv. Third-party solver services, credentials and network calls are disabled. Local permissive tools may remain only in the isolated market-reference extra for competitive benchmarking and do not feed production routing.

Current quantum-style runtime is Empire Annealing, Empire Parallel Tempering and Empire QAOA Simulator, all with qpu_called=false and execution_authority=none.
