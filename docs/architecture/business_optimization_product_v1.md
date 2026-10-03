# Empire Decision Optimization — Whole-Business Product V1

Status: OBSERVE candidate
Runtime ownership: Empire-owned
Execution authority: none
Third-party solver/service dependency: none

## Product

Empire Decision Optimization is the whole-business product surface above the
shared Empire Optimization Fabric. It converts evidence-backed business
decisions into one canonical immutable optimization IR and routes them through
the same Empire-owned solver, benchmark, sharding and learning infrastructure.

## Supported domains

- lead allocation
- buyer allocation
- pricing
- sales territories
- marketing budgets
- staff capacity
- fulfilment
- inventory
- scheduling
- capital allocation
- market expansion
- portfolio strategy

## Shared flow

Domain evidence
-> candidate decisions
-> explicit objective
-> explicit resource limits / hard constraints
-> canonical Optimization IR
-> fingerprint integrity gate
-> safe decomposition
-> Empire solver routing
-> exact / branch-and-bound / greedy / annealing
-> Benchmark Arena
-> solver intelligence
-> Predictive Cloud / AGI recommendation
-> existing domain authority gate
-> separately authorized execution
-> observed outcome
-> Economic Memory

## Truth rules

A missing objective, evidence reference, or usage value for a bounded resource
is never converted to zero. If any supplied candidate is incomplete, the
candidate universe fails closed.

An optimized result is optimal only for the normalized supplied candidate set
and explicit objective/constraints. Empire does not claim a global business
optimum.

## Authority rules

Optimization never grants the authority protected by the business domain.
Examples:

- pricing recommendations do not mutate price;
- capital recommendations do not move funds;
- fulfilment recommendations do not create or execute orders;
- inventory recommendations do not reserve inventory;
- staffing recommendations do not change employment or schedules;
- marketing recommendations do not spend budget;
- buyer/lead recommendations do not route or contact parties.

Those actions remain behind their existing EmpireOS authority gates.

## Product architecture

One solver fabric is reused across all domains. New business domains should add
a compiler or evidence bridge into the canonical IR, not another optimization
engine.
