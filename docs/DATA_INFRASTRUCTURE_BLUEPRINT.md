# Empire AI — Data Infrastructure Blueprint

Date: 2026-09-20
Status: CANONICAL DATA-PLANE DESIGN
Authority: architecture + OBSERVE/local-safe engineering only

This document defines the data infrastructure beneath the Empire Intelligence
Fabric, Predictive Revenue, GTM, Search/Growth, Buyer/Seat/Territory products,
Revenue CRM, Conversation OS and Astra.

It does not replace Supabase as canonical operational truth. It defines how
Empire can scale from today's governed PostgreSQL-centered architecture into a
high-throughput, replayable, auditable, multi-modal data platform without
prematurely activating heavy infrastructure.

## 1. Mission

Build a data system capable of:

**ingest the world -> preserve evidence -> validate trust -> resolve identity ->
retain time/history -> create canonical facts/signals -> serve operational,
analytical, search, graph and model workloads -> observe outcomes -> replay ->
learn -> improve profitable-revenue decisions.**

The data platform exists to make Predictive Revenue better.

North-star data property:

**Every revenue decision must be traceable backwards to evidence and forwards to
a verified commercial outcome.**

## 2. Non-Negotiable Data Principles

1. Supabase/PostgreSQL remains canonical operational truth until measured scale
   justifies another operational component.
2. Raw evidence is immutable. Corrections create new versions/events.
3. Every derived record keeps provenance and transformation lineage.
4. Event time and processing time are different fields.
5. Unknown remains unknown. Missing is never silently converted to zero.
6. Crawler/scraper/model output is intelligence, never commercial authority.
7. Entity resolution is explicit, scored and reversible.
8. Schemas are versioned contracts, not accidental JSON shapes.
9. Idempotency is mandatory on ingestion and materialization.
10. Replays/backfills must be deterministic and bounded.
11. Operational, analytical and model-serving workloads are isolated by
    contracts even when they initially share PostgreSQL.
12. PII/contact data is segregated, minimized and access-controlled.
13. Cost is a first-class metric: bytes, calls, storage, compute and model spend.
14. Heavy infrastructure activates only on measured need.
15. Every analytical or model feature must be point-in-time correct to prevent
    leakage from future outcomes.

## 3. Empire Data Plane — Layered Architecture

### Layer 0 — Source Edge

Source families:
- company websites
- public registries
- permits/licences
- weather/storm/event feeds
- satellite/imagery providers
- search/SERP
- Search Console
- public social/community/Reddit
- jobs/hiring
- public records/courts
- market/price/competitor sources
- CRM/conversation/provider events
- GTM/campaign/content telemetry
- partner/affiliate feeds
- BSC payment verification
- fulfilment/outcome systems
- first-party application/product telemetry
- future licensed/commercial data feeds

Every source adapter exposes:
- source_key
- source_type
- source_version
- collection method
- legal/usage metadata
- observed_at/event_time
- fetched_at/processing_time
- request fingerprint
- source URI/reference
- evidence hash
- payload hash
- quality state
- retry/backoff state
- cost metadata

### Layer 1 — Source Mesh / Ingestion Fabric

One logical ingress contract for:
- HTTP APIs
- crawlers
- scrapers
- webhooks
- file imports
- scheduled collectors
- batch loads
- CDC
- partner feeds
- A2A/agent observations

Required properties:
- idempotency key
- source partition
- bounded batch size
- checkpoint/cursor
- rate limiting
- retry policy
- dead-letter/quarantine state
- payload size limits
- content type
- schema version
- trace/correlation id
- source-health telemetry

Initial implementation may be PostgreSQL + local runtime/object storage.
Future transport may use Kafka/Redpanda only after activation thresholds.

### Layer 2 — Immutable Raw Evidence Vault

Empire should preserve the original evidence before normalization.

Logical zones:
- raw/http
- raw/html
- raw/json
- raw/pdf-metadata
- raw/image-metadata
- raw/provider-events
- raw/webhooks
- raw/transcripts
- raw/payment-evidence
- raw/fulfilment-evidence

Design:
- content-addressed objects using cryptographic hashes
- immutable object versions
- compression
- source/date partitioning
- checksum verification
- retention class
- legal/privacy class
- pointer stored in canonical provenance records
- never overwrite evidence in place

Recommended progression:
1. filesystem/object abstraction for local/dev
2. S3-compatible object storage when durable raw volume requires it
3. lifecycle/tiering policies as volume grows

Do not store binary/image/document payloads repeatedly in core PostgreSQL tables.

### Layer 3 — Data Contract + Schema Registry

Every event/record type receives:
- namespace
- schema name
- schema version
- owner
- compatibility mode
- required/optional fields
- semantic definitions
- units/currency/timezone
- privacy classification
- allowed source types
- idempotency semantics
- retention
- downstream consumers

Examples:
- empire.source.observation.v1
- empire.company.web_snapshot.v1
- empire.permit.observation.v1
- empire.storm.event.v1
- empire.satellite.observation.v1
- empire.search.serp_observation.v1
- empire.conversation.event.v1
- empire.buyer.capacity_observation.v1
- empire.payment.bsc_verification.v1
- empire.commercial.outcome.v1

Compatibility policy:
- additive nullable fields may be backward compatible
- semantic reinterpretation requires a new version
- removed/renamed required fields require a new version
- units/currency changes require explicit versioning

### Layer 4 — Trust / Quality Firewall

No observation moves directly from collection into a trusted decision surface.

Checks:
- parse/schema validity
- source allowlist/status
- provenance completeness
- timestamp validity
- future-date rejection
- duplicate/replay detection
- content hash consistency
- domain/source integrity
- entity candidate quality
- impossible numeric values
- unit consistency
- required evidence references
- freshness
- corroboration requirements
- PII policy
- tamper/conflict detection

States:
RAW -> VALIDATED -> QUARANTINED | ACCEPTED -> MATERIALIZED

No source-health failure may silently generate clean-looking zeroes.

### Layer 5 — Identity + Temporal Intelligence Graph

Existing Empire Intelligence Fabric remains the canonical intelligence graph.

Core nodes:
- business entity
- person
- role/employment
- contact point
- property/location
- territory
- corridor
- buyer
- product/offer
- campaign
- content asset
- conversation
- opportunity
- permit
- storm/event
- asset/warehouse
- payment
- fulfilment
- outcome

Core edges:
- works_at
- owns/operates
- located_in
- serves_territory
- competes_with
- mentioned_by
- cites
- generated_from
- triggered_by
- matched_to
- allocated_to
- contacted_via
- converted_to
- paid_for
- fulfilled_by
- caused/associated_with
- supersedes
- derived_from

Temporal semantics:
- first_seen_at
- last_seen_at
- valid_from
- valid_to
- observed_at
- superseded_at
- confidence history
- source history

The graph may remain relational PostgreSQL while scale is moderate.
A separate graph engine is optional and should only be introduced if measured
graph traversal workloads exceed the relational design.

### Layer 6 — Canonical Operational Store

Supabase/PostgreSQL owns:
- canonical IDs
- commercial states
- buyers
- seats
- territories
- corridors
- capacity
- products
- opportunities
- governed outbound intents
- conversations
- approvals
- payments
- fulfilment
- recognized revenue
- outcomes
- Intelligence Fabric facts/signals/scores
- control/governance records

Rules:
- small authoritative records, not giant raw blobs
- append-only where auditability matters
- row-level security / least privilege
- separated reader/writer/runtime roles
- no public mutation authority on consequential tables
- versioned forward-only migrations

### Layer 7 — Change/Event Log

Empire needs a logical event backbone even before Kafka exists.

Canonical event envelope:
- event_id
- event_type
- aggregate_type
- aggregate_id
- tenant_id where applicable
- schema_version
- source
- observed_at
- emitted_at
- correlation_id
- causation_id
- idempotency_key
- evidence_refs
- payload_hash
- payload
- privacy_class

Use cases:
- materializers
- analytics
- feature updates
- search indexing
- notifications
- model feedback
- audit
- replay/backfill

Initial transport:
- append-only PostgreSQL event/outbox tables
- bounded pollers/materializers

Scale transport:
- Kafka/Redpanda when throughput/backlog/consumer fanout proves it is needed.

### Layer 8 — Analytical Plane / Lakehouse

Operational PostgreSQL should not become the infinite analytics warehouse.

Progression:
- current: indexed Postgres projections + bounded exports
- next: Parquet snapshots on object storage + DuckDB/Polars for offline analysis
- scale: ClickHouse for high-volume event/time-series analytics
- later: warehouse/lakehouse tooling only if workloads justify it

Analytical datasets:
- account/entity snapshots
- signal sequences
- market/corridor time series
- search/content observations
- campaign/channel observations
- conversation outcomes
- buyer capacity history
- payment/fulfilment/outcome facts
- prediction vs actual
- gross-profit attribution
- experiment exposure/outcomes
- infrastructure/source telemetry

Every analytical table carries snapshot time and source lineage.

### Layer 9 — Search / Retrieval Plane

Different retrieval workloads require different indexes.

Structured lookup:
- PostgreSQL B-tree/GIN/GiST

Full text:
- PostgreSQL FTS initially
- dedicated search engine only after measured need

Semantic retrieval:
- embeddings stored behind a versioned embedding contract
- pgvector is sufficient initially when enabled/justified
- embedding model/version must be recorded
- re-embedding creates a new version; never silently replaces history

Agent retrieval:
- retrieval by canonical entity + time + evidence
- provenance returned with every fact
- never give agents raw untrusted source content without trust boundaries

### Layer 10 — Geospatial + Time-Series Plane

Empire is heavily geographic and temporal.

Geospatial workloads:
- territories
- permit density
- storms
- satellite zones
- buyer coverage
- corridor heatmaps
- property/business locations
- radius/geofence queries

Recommended:
- PostGIS when geospatial query complexity/volume justifies activation
- canonical geography IDs and normalized coordinate precision policy

Time-series workloads:
- source health
- signals
- market demand
- search
- capacity
- campaign performance
- forecasts
- outcomes
- infra telemetry

Use indexed PostgreSQL initially; ClickHouse/Timescale-class tooling only when
measured retention/query latency warrants it.

### Layer 11 — Feature + Model Data Plane

Predictive Revenue requires point-in-time-correct features.

Feature contract:
- feature_key
- entity_type/id
- observed_at
- feature_time
- materialized_at
- value
- source_refs
- transformation_version
- feature_version
- freshness SLA
- privacy class

Features include:
- signal recency/frequency
- buyer quality/capacity
- territory demand
- corridor economics
- search/AI visibility
- permit/storm/event activity
- conversation engagement
- historical outcomes
- churn/renewal
- revenue/cost/gross profit

Critical:
- training datasets must be generated "as known at the time"
- future outcomes may not leak into historical features
- model registry records data snapshot + feature versions + code version
- online/offline feature definitions must match

A dedicated feature-store product is optional; contracts matter before tooling.

### Layer 12 — Revenue Truth / Outcome Store

The strongest data in Empire is closed-loop commercial truth.

Record:
- prediction
- decision packet
- action/exposure
- buyer
- agreement
- payment verification
- fulfilment
- outcome
- recognized revenue
- cost
- gross profit
- repeat purchase/churn
- timestamps/provenance

This dataset becomes the proprietary training/evaluation moat.

## 4. "Beyond" — Empire World Model

The long-term destination is a live commercial world model.

For every company/market/territory/corridor Empire should be able to answer:

- What is true now?
- What changed?
- What source proved it?
- How confident are we?
- What was true at any prior point?
- What is likely to happen next?
- Which commercial action has the highest expected gross profit?
- What happened when Empire tried similar actions before?
- Which source/feature/model contributed to the prediction?
- Which verified outcome proved or disproved it?

World Model components:
- Temporal Entity Graph
- Event/Change Graph
- Market Digital Twins
- Buyer Digital Twins
- Territory/Corridor Twins
- Campaign/Content Twins
- Revenue Outcome Graph
- Causal/Experiment Graph
- Model/Feature Lineage Graph

This is the layer that makes Astra more than an automation agent.

## 5. Multi-Modal Intelligence

Empire must support evidence beyond text:
- HTML/text
- JSON/API
- PDFs/documents
- images
- satellite imagery
- maps/geospatial
- call audio metadata/transcripts
- video metadata
- structured payments
- time series

Rules:
- preserve original object/hash
- derive metadata/embeddings separately
- record extractor/model version
- never allow a derived caption/OCR/classification to replace original evidence
- confidence and provenance remain attached

## 6. Data Lineage Graph

Every derived commercial signal should answer:

source object
-> parser
-> schema version
-> quality checks
-> normalized observation
-> entity resolution
-> fact/signal/feature
-> score/forecast
-> decision packet
-> campaign/outreach/action
-> payment/outcome
-> revenue/gross profit.

Lineage records:
- run_id
- transformation_key/version
- input refs/hashes
- output refs/hashes
- code commit
- started/completed timestamp
- status
- row/object counts
- rejected/quarantined counts
- compute/cost

## 7. Replay / Backfill / Time Travel

Every ingestion/materialization pipeline should be replayable.

Capabilities:
- replay one event
- replay source/date partition
- rebuild one entity
- rebuild one corridor
- rebuild one model feature window
- bounded historical backfill
- dry-run diff before apply
- checkpoint/resume
- idempotent duplicate protection

Historical rebuild must not overwrite commercial truth.

## 8. Data Quality / Trust Scorecard

Per source:
- availability
- freshness
- latency
- completeness
- schema-valid %
- duplicate %
- quarantine %
- conflict %
- entity-match %
- verified-contact %
- cost per accepted record
- commercial outcome contribution

Per dataset:
- row/object count
- freshness
- null/unknown profile
- distribution drift
- referential integrity
- lineage completeness
- point-in-time correctness
- retention compliance

Data quality is visible to Astra.

## 9. Privacy / Security Data Architecture

Separate classes:
- PUBLIC
- INTERNAL
- COMMERCIAL
- PII
- PAYMENT_EVIDENCE
- SECRET

Controls:
- least-privilege service roles
- tenant scoping
- column/data minimization
- PII vault/segregation
- encryption at rest/in transit
- secrets outside data payloads
- append-only access/audit events
- retention/deletion policy
- purpose limitation
- suppression/DNC propagation
- export controls
- redaction for agent/model contexts

Never put raw secrets, API keys or wallet private material into event payloads.

## 10. Data Product Layer

Empire data infrastructure itself becomes monetizable.

Products:
- Market Intelligence API
- Company Intelligence API
- Buyer Intelligence API
- Permit API/feed
- Storm/Event API/feed
- Satellite/Industrial observations
- Territory/Corridor API
- Search/AI Visibility API
- Competitor Intelligence API
- Revenue Benchmark API
- Signal Feed
- Data Enrichment API
- Webhooks / event subscriptions
- White-label intelligence feeds
- Agent/MCP/A2A data capabilities

Every product exposes source/freshness/confidence semantics rather than a
black-box number.

## 11. Agent-Native Data Plane

Agents receive governed capabilities, not unrestricted database access.

Agent surfaces:
- entity.search
- entity.timeline
- market.search
- signal.search
- evidence.fetch
- opportunity.search
- buyer.capacity.read
- corridor.economics.read
- forecast.read
- outcome.read
- lineage.trace
- source.health

Mutation capabilities remain role-separated and approval-gated.

Every agent answer should be able to return:
- canonical entity IDs
- evidence refs
- observed_at
- confidence
- source freshness
- unknown fields

## 12. Data Observability Control Tower

One operator view:
- source health
- ingestion lag
- event backlog
- materializer lag
- schema failures
- quarantine counts
- lineage failures
- freshness SLA breaches
- storage growth
- query latency
- DB load
- model feature freshness
- cost per source
- cost per accepted entity
- data-to-revenue contribution

Astra should rank data incidents by expected commercial impact.

## 13. Self-Healing Data Operations

Safe automation:
- retry transient failures
- resume from checkpoints
- quarantine poison records
- disable a failing source adapter after threshold
- alert on schema drift
- rebuild derived caches/indexes
- recompute read-only projections

Gated operations:
- schema migrations
- destructive retention
- source credential rotation
- production role changes
- new provider activation
- bulk historical mutations

## 14. Cost-Aware Data Governor

Every source/pipeline may record:
- API cost
- proxy cost
- model cost
- bytes transferred
- storage bytes
- compute duration
- accepted records
- qualified entities
- downstream revenue/outcomes

Metrics:
- cost / raw record
- cost / accepted record
- cost / resolved entity
- cost / qualified opportunity
- cost / recognized revenue
- gross profit contribution by source

Sources with no value can be reduced/paused after evidence review.

## 15. Infrastructure Activation Ladder

### Stage A — Current / Near-Term
Use:
- Supabase/PostgreSQL
- append-only event/outbox contracts
- bounded pollers/materializers
- current Search/Intelligence Fabric
- runtime files only for non-canonical operational artifacts
- Parquet/DuckDB for offline analytics when helpful

### Stage B — Durable Raw/Data Lake
Activate S3-compatible object storage when:
- raw evidence volume materially grows
- replay/audit needs require durable object retention
- binary/multimodal evidence becomes routine

### Stage C — Queue/Event Backbone
Activate Redis/queue or Kafka/Redpanda when measured evidence shows:
- sustained backlog
- multiple independent consumers
- operational PostgreSQL polling load
- replay/fanout requirements
- latency SLA unmet by current outbox/poller

### Stage D — Analytical Engine
Activate ClickHouse when:
- event/time-series data becomes large
- dashboards/aggregation pressure impacts Postgres
- retention/query latency targets cannot be met economically in Postgres

### Stage E — Dedicated Search
Activate OpenSearch/another search engine when:
- indexed document volume/query patterns exceed PostgreSQL FTS economically
- advanced faceting/ranking/near-real-time indexing requires separation

### Stage F — Dedicated Graph
Activate a graph engine only if:
- multi-hop graph traversals dominate workloads
- relational recursive queries/indexing cannot satisfy measured latency/cost

### Stage G — Distributed/Multi-Region
Activate Kubernetes/multi-region/data replication when:
- availability/load/compliance requirements justify operational complexity

No stage is activated simply because it is fashionable.

## 16. Production Readiness Gates

Before activating a new data component require:
- real workload evidence
- measurable bottleneck
- owner
- data contract
- backup/restore
- security model
- observability
- failure/replay strategy
- cost forecast
- migration/rollback plan
- load test
- least privilege
- secrets plan
- incident runbook

## 17. First Build Slices

### Slice 1 — Data Plane Contract / Readiness
OBSERVE-only component registry and readiness evaluator.

### Slice 2 — Canonical Event Envelope
Local/tested event model + append-only staged persistence.

### Slice 3 — Lineage
Transformation run/input/output lineage contract.

### Slice 4 — Immutable Raw Pointer Contract
Evidence object metadata/hash/ref without forcing object-store activation.

### Slice 5 — Data Quality
Source/dataset quality observations and readiness.

### Slice 6 — Replay Planner
Dry-run replay/backfill plans with zero mutation authority.

### Slice 7 — Point-in-Time Feature Contract
Feature values with source/time/version/freshness and leakage checks.

### Slice 8 — Data Cost Attribution
Source/pipeline cost -> accepted records -> commercial outcome contribution.

### Slice 9 — Data Control Tower
Read-only API/dashboard feeding Astra operational evidence.

## 18. What This Gives Empire

This architecture enables:
- internet-scale source collection without losing evidence
- historical market replay
- company/person/market timelines
- high-quality proprietary training data
- revenue attribution back to original sources
- auditable model predictions
- replayable GTM decisions
- reliable AI/agent retrieval
- sellable data feeds/APIs
- multi-modal intelligence
- better buyer/territory/corridor predictions
- self-improving Predictive Revenue models
- infrastructure that scales only when economics justify it

The strategic asset is not the database.

The strategic asset is:

**a proprietary, temporal, provenance-backed commercial world model linked to
verified revenue and gross-profit outcomes.**
