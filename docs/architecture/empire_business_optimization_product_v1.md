# Empire Business Optimization Product V1

## Product

Empire Business Optimization Engine is one shared optimization product over the
Empire-owned Intelligence Optimization Fabric.

It is not twelve separate optimizers. Every workload compiles observed,
evidence-backed choices and constraints into the same immutable Optimization IR,
uses the same solver router, and returns recommendation-only evidence.

## Workloads

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

## Contract

Each candidate option carries a stable option key, business entity, objective
value, evidence references, optional target, resource usage, partition key, and
metadata.

The compiler supports:

- one-of / at-most-one / minimum selection by entity;
- explicit resource minimum, maximum, and exact limits;
- custom selection groups;
- dependencies;
- conflicts;
- required and forbidden choices;
- maximize or minimize objectives;
- tenant context;
- bounded solve time;
- horizontal partition keys.

Missing evidence or economics stays UNKNOWN and is blocked rather than silently
converted to zero.

## Shared runtime

Business workload
-> Empire Business Optimization compiler
-> immutable Empire Optimization IR
-> integrity fingerprint
-> Solver Intelligence
-> Empire exact / branch-and-bound / greedy
-> Empire annealing / parallel tempering / QAOA simulator where eligible
-> optional proven-independent sharding
-> Benchmark Arena / Solver Performance Memory
-> recommendation

Predictive Cloud and AGI may consume the resulting recommendation packet.

## Authority

The engine does not allocate leads or buyers, change prices, spend marketing
budget, assign staff, fulfil orders, move inventory, schedule jobs, allocate
capital, enter markets, or change a strategic portfolio.

Every result is recommendation-only with execution_authority=none. Existing
governed business workflows retain their own approval and action gates.

## Productization

The same engine is suitable for an Empire SaaS/API surface because workload
semantics are separated from solver internals. Multi-tenant context is carried
in the canonical problem packet; no tenant is allowed to alter another
tenant's evidence or solver state.

Third-party solver services are prohibited from the Empire runtime. External
tools may be used only as explicit market-reference benchmarks.

## Continuous automation

The existing empire-department-cycle.timer runs every two minutes and is the automation heartbeat for the product.

Each heartbeat watches canonical runtime evidence for all 12 workloads, requires an active evidence-backed optimization policy, maps observed objectives and resource constraints into a request, atomically claims queued work, compiles immutable Optimization IR, routes only Empire-owned solvers, benchmarks safe bounded problems, archives processed events, records changed recommendations and performs no business action.

Portfolio strategy and market expansion have specialized Opportunity Factory/Radar adapters. The remaining domains use the generic policy-mapped runtime-evidence adapter so they can bind to canonical runtime producers without creating another optimizer.

Missing budgets, capacity, economics or evidence remain blockers. The system never creates synthetic economics to make automation run.

## Automation authority

Automation means computation and recommendation are continuous. It does not mean sensitive business authority is bypassed. Pricing mutation, spend, staffing, fulfilment, inventory reservation, buyer/lead routing, capital movement and market launch remain behind their existing EmpireOS gates.
