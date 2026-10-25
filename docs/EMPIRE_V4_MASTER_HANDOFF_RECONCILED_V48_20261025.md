# EMPIRE AI V4 — Enterprise Predictive Cloud master handoff & V4.8 continuation

**Date:** 25 October 2026
**Original build:** EmpireOS / PRIME / ASTRA / Predictive Cloud / canonical EmpireDB PostgreSQL / one Smart CRM
**Research worktree:** `/home/ubuntu/empire_worktrees/prime_universal_evidence_fusion_20261024`
**Release state:** V4.8 fixture RESEARCH / OBSERVE; **nothing in this handoff authorises production deployment, trading, ad spend, outbound, payments or DB migration**.

## 1. Mission and execution loop

Empire AI Predictive Cloud is a cross-sector system to sense changes in **physical conditions, capital markets and supply/demand**, reason about testable opportunities, prioritise economically valuable actions and learn from real outcomes. Intended sectors cover construction, weather/storm, insurance, logistics, commodities, ecommerce, home services, legal, enterprise SaaS, media and trading research. No single sector defines the engine.

**Design goal:** licensed source -> immutable evidence/provenance -> source and tenant authorisation -> causal hypothesis -> scenario distribution and downside -> bounded opportunity/decision -> independently approved commercial action -> real fulfilment and settlement -> economic memory -> measured update. This is a target commercial loop, **not a claim of completed revenue**.

## 2. Claims reconciled to actual code

| Master handoff claim | Engineering status / correction |
|---|---|
| NOAA/NWS, GDELT, SEC, Kalshi/Polymarket, Sentinel satellite/spatial | **Proposed source classes / individually evaluated adapters.** Original NWS bridge handles offline reviewed evidence contracts; no claim these feeds are presently licensed, connected, continuously ingested or producing revenue. Each must pass rights, availability, source freshness, event provenance, rate limits, use restrictions and retained-revision checks. |
| Causal do-calculus `P(Y\|do(X))` | **Research objective, not proof of causality.** Requires an explicit causal DAG, identification assumptions, confounder tests, experimental/quasi-experimental counterfactual checks and outcome calibration. Correlation cannot be eliminated by invoking do-calculus alone. |
| Polymarket/Kalshi and satellites ahead of news | **Hypothesis, not guaranteed lead time.** Validate per-source timestamp and latency; avoid unsupported satellite cadence/coverage claims. Market price contains risk premium, spreads, participant bias and regulatory/geographic constraints. |
| PostgreSQL + pgvector/HNSW | **Target vector architecture.** Canonical EmpireDB PostgreSQL is confirmed; extension/index installation, compatible embedding dimensions, access rights, benchmarks and current production availability remain unproven in this handoff. Do not silently provision a separate vector database or Supabase. |
| Redis Streams sub-millisecond edge delivery | **Local Redis 8 / Unix-socket actual tests done.** Performance at scale, p50/p95/p99, consumer group end-to-end timing and Redis Cloud deployment are unverified. Streams + PEL plus EmpireDB dedupe are not exactly-once delivery. |
| PyTorch PPO policy | **Proposed offline optimisation subsystem**, not verified active production model. A model reward is not settlement, risk, causal truth, spend authority or suitable bound for each sector. No automated production budget or trading execution. |
| Monte Carlo P10/P50/P90 | **Target risk contract.** Must use auditable distribution/calibration, assumptions, confidence horizons, stress losses and reproducible seeded samples, not fabricate deterministic promises. |
| Minimum 2.5x ROAS | **Candidate action policy, not guarantee.** A forecast above 2.5x is insufficient without validated cost, capacity, quality, uncertainty and real conversion evidence. Hard deterministic owner gates supersede PPO; paid traffic presently OFF. |
| Zero-knowledge proofs | **Specified but not implemented.** A future ZK proof might verify a private computation, licensed membership predicate or aggregate without revealing its witness; it does not prove the original source fact true or grant legal rights. V4.7 Ed25519 signatures are NOT zero-knowledge proofs. |

## 3. Implemented isolated Predictive Cloud research milestones

- **V4.1 Redis**: bounded tenant-scoped feature vector/TTL, monotonic revision Lua on one Redis key, Redis Stream advisory messages; real local Redis 8 server with TCP port 0 tested.
- **V4.2**: PREPARED migration 064 with durable HELD EmpireDB event revision watermark and append-only outbox, synthetic tenant IDs and withheld publication.
- **V4.3**: read-only owner-only held outbox snapshot and tenant/revision/source-digest validation.
- **V4.4**: PREPARED migration 065, tenant+event idempotent advisory receipt; no ACK or external action.
- **V4.5**: actual Redis consumer-group `XREADGROUP`/`XAUTOCLAIM`/`XACK` with disposable PostgreSQL HELD receipt; consumer crash before/after commit.
- **V4.6**: local AOF Redis graceful shutdown and SIGKILL/restart, recovered Stream/PEL and canonical held dedupe in PostgreSQL. Not Redis Cloud/multi-region.
- **V4.7**: real Ed25519 *fictional signer* dual source/tenant signature verification with owner-supplied fixture roots, revocation and held canonical DB revision check; no production key registry.
- **V4.8**: reuses existing `SignedCrmTenantVerifier`, original `EmpireDbCrmMembershipReader`, PREPARED original CRM041 `empire_crm_read_member`, and PREPARED held064 event readback. In one disposable PG18 cluster (two fixture DBs), active signed CRM tenant principal plus source/tenant signed event must match. Expired/revoked/other tenant/tampered token and withdrawn event cannot promote. A temporary generated SCRAM credential is used solely for the fixture login; no production credential or schema touched.

Research commits and tests are on the dedicated clean research branch and may be ahead of its remote. A commit is not a production release.

## 4. Correct runtime governance and owners

Canonical source rights and CRM sessions **must be independently authenticated**: signed-source signatures, signed CRM tokens and source digests are each necessary at most, not sufficient. Source owner must prove permitted uses and timestamp custody; the CRM identity owner must verify active tenant membership using native dedicated DB roles. Any revocation, deletion, role disable, expired entitlement, source revision regression or missing identity fails closed.

The Redis hot path is a **projection/cache/notification candidate** only. The original EmpireDB controls outbox identity, event revision, per-tenant scoping, receipt idempotence and withdrawals. No event in Redis, even with a valid signature, becomes spend, communication, trade, contract or payment authority. ASTRA and PRIME receive read-only proposals only after independent original owner review.

## 5. Causal + trading + profit engine sequencing

**Stage A — observe.** Record source snapshots with evidence, effective times, rights and provenance. Separate market probabilities, news assertions, physical evidence, price movement and commercial buyer demand. Use no asserted verified facts without independent support.

**Stage B — test.** Construct causal DAG and counterfactual scenario for each hypothesis; quantify uncertainty with P10/P50/P90 and calibration against historical outcomes; report data leakage, confounders and missing counterfactual identifiability. Prediction-market data is one feature, not a self-proving true probability.

**Stage C — shadow decision.** Compute expected net contribution with acquisition, fulfilment, capacity, fees, refund/chargeback, delayed settlement and downside risk. Record policy version, model version and approval gate. PPO can propose offline actions only; deterministic risk budgets, 2.5x candidate thresholds and operational kill switches gate any later execution.

**Stage D — governed economic action.** Real business offers, outreach, ad spend, trading/orders, payments and legally binding terms each have separate explicit approval and jurisdiction/provider checks. Current founder policy: no paid traffic; direct BSC USDT payments remain financially disabled. Only settled verified economic receipts may update realised revenue.

**Stage E — learn.** Maintain hindsight/forecast separation, causal outcome attribution, immutable audit lineage, risk-adjusted performance and human-review escalation for policy changes. Never train on self-generated fictional returns as if settled cash.

## 6. Security, reliability and acceptance outstanding

- Real production-grade authenticated source registry, licensed ingestion and revocation feed.
- Independent pinned keys/HSM or approved secret store, issuance, rotation, revocation, provenance and audit; no caller-supplied trust roots.
- Dedicated read-only production roles verified by EmpireDB/CRM owners; no bypass from source/CRM claims.
- Redis Cloud private endpoint/TLS/ACLs, migration and cost gate, consumer retry/backpressure, corruption and AOF loss resilience; end-to-end latency benchmarks.
- Responsible trading model research: market-data quality/market rules, fraud/manipulation resistance, empirical backtests out of sample, risk and drawdown, unfilled-order/margin/liquidation handling, hard limits. No real trades.
- Calibrated causal/risk model and settlement truth; production financial authority remains off.
- Investigate ZK only if there is a concrete privacy requirement, threat model, witness/circuit proof system, verifier cost and trusted setup decision.

**Production truth first. Keep one original build. One EmpireDB, one Smart CRM, ASTRA/PRIME integrated. Never infer live profitability from fixture results.**
