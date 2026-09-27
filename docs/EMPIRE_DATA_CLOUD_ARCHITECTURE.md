# Empire Data Cloud — Architecture Contract v1

Date: 2026-09-27
Status: FOUNDATION BUILD — NOT YET PRODUCTION CANONICAL

## Mission

Empire Data Cloud is the sovereign data infrastructure layer for EmpireOS and a future standalone developer platform.

It must support Predictive Cloud, Predictive Revenue, Intelligence Fabric, Cortex, Digital Twins, agent memory, search, vectors, events, audit history and SaaS tenancy without binding EmpireOS to a third-party database vendor.

The existing Supabase project remains production truth until migration is independently verified and explicitly approved.

## Canonical architecture

```
EmpireOS
  |
Empire Data Fabric
  |-- transactional
  |-- events / evidence
  |-- vectors / memory
  |-- realtime
  |-- analytics
  |-- data APIs
  |
Empire Data Cloud
  |
PgBouncer / private network
  |
PostgreSQL HA / replicas / DR
  |
WAL / PITR / encrypted off-node backup
```

## Non-negotiable boundary

EmpireOS business modules MUST depend on the Empire Data Fabric contract, never directly on a vendor SDK, vendor REST endpoint or vendor-specific runtime behaviour.

Backends are replaceable infrastructure. Business logic is not.

## Platform planes

### Data Plane
Canonical transactions, tenant-aware queries, immutable evidence/events, vectors, search, realtime subscriptions, read scaling and object references.

### Intelligence Plane
Cortex memory, predictive features, Digital Twins, scoring, forecasting, entity graphs, semantic retrieval and outcome learning.

Predictions remain predictions. Storage never converts inference into observed fact, buyer intent, payment or recognized revenue.

### Agent Plane
Agents never receive unrestricted database credentials. Each agent receives scoped identity, tenant scope, explicit capabilities, rate/transaction budgets, audit identity, expiry/revocation and Control Fabric authority.

### Control Plane
Projects, tenants, database instances, regions, service identities, keys, quotas, backups, restore/PITR, replicas, migrations, observability, usage metering and billing.

The control plane must not become a single point of failure for already-running data-plane workloads.

## API product boundary

Reserved versioned surfaces:

- /data/v1/
- /graphql/v1/
- /rpc/v1/
- /vector/v1/
- /events/v1/
- /auth/v1/
- /storage/v1/
- /functions/v1/
- /ai/v1/
- /platform/v1/
- /mcp/v1/

All external exposure is fail-closed during foundation work.

## Infrastructure target

- PostgreSQL 18 current supported minor
- PgBouncer pooling
- Patroni-compatible HA orchestration
- pgvector
- WAL archiving and point-in-time recovery
- encrypted off-node backups
- private database networking
- primary + HA replica + geographically separate DR capability
- optional read replicas for dashboards, analytics and AI context
- observability for replication lag, locks, slow queries, storage, connection pressure, backup freshness and restore readiness

The first migration milestone may use one production node, but the application contract must already support the HA target without an application rewrite.

## Multi-tenancy

Isolation tiers:

1. shared cluster with enforced tenant isolation;
2. dedicated database/schema allocation where needed;
3. dedicated cluster/private deployment for enterprise or residency-sensitive customers.

Tenant identity comes from authenticated platform context, never arbitrary request payloads.

## Truth and provenance

Consequential data should preserve source identity, tenant, observed time, temporal validity, evidence refs, derivation identity, model/version, confidence where applicable and immutable event identity.

OBSERVED != INFERRED != FORECAST != SCENARIO != VERIFIED OUTCOME.

## Security

- database ports private only
- least-privilege service roles
- migration credentials separated from application identities
- no shared god-mode service credential
- cross-tenant access fail-closed
- secrets never enter Git
- destructive operations remain founder-gated

## Reliability

Empire Reliability Agent remains orchestration owner:

OBSERVE -> DIAGNOSE -> PLAN -> ACT -> VERIFY -> RECORD -> REPEAT

Autonomous recovery remains bounded and reversible and never implies destructive schema mutation, cross-tenant access, live outbound, binding terms, fund movement, revenue recognition or authority expansion.

## Economic intelligence

Every workload should eventually be measurable by tenant, project, API key/service identity, query family, storage class, compute/IO, vector usage, event volume and agent/model activity.

The platform should detect pathological workloads before they become uncontrolled cost.

## Portability

PostgreSQL-first and deliberately exportable: logical export, schema export, deterministic migrations, event export, backup restore and approved private PostgreSQL connectivity.

## Supabase migration state machine

DISCOVER -> SHADOW -> COPY -> VERIFY -> DUAL_READ_COMPARE -> CUTOVER_READY -> FOUNDER_APPROVED_CUTOVER -> EMPIREDB_CANONICAL -> SUPABASE_RETIRED

Rules:

- Supabase remains canonical until explicit cutover approval.
- Partial or dry-run copies never become production truth.
- Row counts alone are insufficient verification.
- Commercial/payment evidence requires independent integrity checks.
- Rollback remains available until post-cutover verification completes.
- Existing Supabase containment must not be bypassed to force migration traffic.

## Build sequence

1. Contract and dependency discovery.
2. EmpireDB single-node production foundation.
3. Verified schema/data migration and shadow reads.
4. HA/DR and restore drills.
5. Developer platform: Data API, projects, keys, MCP, SDK/OpenAPI, metering.
6. Intelligence-native platform: vectors, predictive APIs, Digital Twins, governed agent transactions and outcome learning.

## Definition of done for canonical migration

EmpireDB is not canonical until:

- application boundary is vendor-neutral
- schema and data migration are verified
- no unclassified direct Supabase production dependency remains
- backup restore is proven
- recovery/failover path is tested
- tenant/security boundaries are tested
- production reads and writes are verified
- payment/commercial evidence integrity is verified
- Founder Console exposes data-plane health/topology
- Reliability Agent observes the data plane
- rollback exists
- founder explicitly approves canonical cutover
